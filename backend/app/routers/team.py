import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.core.permissions import can_manage_users, require_role
from app.core.security import hash_password
from app.core import audit
from app.models.user import User, APIKey
from app.schemas.user import UserCreate, UserUpdate, UserOut, APIKeyCreate, APIKeyCreated, APIKeyOut
from app.core.security import generate_api_key
from datetime import datetime, timedelta, timezone

router = APIRouter(tags=["team"])


@router.get("/team", response_model=list[UserOut])
async def list_team(user: CurrentUser, db: DB) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.full_name))
    return [UserOut.model_validate(u) for u in result.scalars()]


@router.post("/team", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, user: CurrentUser, db: DB) -> UserOut:
    if not can_manage_users(user.role):
        raise HTTPException(status_code=403, detail="Admin required")

    # Check duplicates
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    new_user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        hashed_password=hash_password(body.password),
    )
    db.add(new_user)
    await audit.log(db, action="user.create", user=user, resource_type="user",
                    request_data={"username": body.username, "role": body.role})
    await db.commit()
    await db.refresh(new_user)
    return UserOut.model_validate(new_user)


@router.get("/team/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, user: CurrentUser, db: DB) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(u)


@router.patch("/team/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, user: CurrentUser, db: DB) -> UserOut:
    # Users can update their own profile; admins can update anyone
    if str(user_id) != str(user.id) and not can_manage_users(user.role):
        raise HTTPException(status_code=403, detail="Forbidden")

    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_none=True)
    # Only admins can change roles
    if "role" in updates and not can_manage_users(user.role):
        del updates["role"]

    for field, value in updates.items():
        setattr(u, field, value)

    await audit.log(db, action="user.update", user=user, resource_type="user", resource_id=str(user_id),
                    request_data={"fields": list(updates.keys())})
    await db.commit()
    await db.refresh(u)
    return UserOut.model_validate(u)


@router.delete("/team/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    if not can_manage_users(user.role):
        raise HTTPException(status_code=403, detail="Admin required")
    if str(user_id) == str(user.id):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    await audit.log(db, action="user.delete", user=user, resource_type="user", resource_id=str(user_id))
    await db.delete(u)
    await db.commit()


# ── API Keys ───────────────────────────────────────────────────────────────────

@router.get("/api-keys", response_model=list[APIKeyOut])
async def list_api_keys(user: CurrentUser, db: DB) -> list[APIKeyOut]:
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
    )
    return [APIKeyOut.model_validate(k) for k in result.scalars()]


@router.post("/api-keys", response_model=APIKeyCreated, status_code=201)
async def create_api_key(body: APIKeyCreate, user: CurrentUser, db: DB) -> APIKeyCreated:
    raw_key, key_hash, key_prefix = generate_api_key()
    expires_at = None
    if body.expires_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=body.expires_days)

    key = APIKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=body.scopes,
        expires_at=expires_at,
    )
    db.add(key)
    await audit.log(db, action="apikey.create", user=user, request_data={"name": body.name})
    await db.commit()
    await db.refresh(key)
    out = APIKeyCreated.model_validate(key)
    out.raw_key = raw_key  # only time the full key is returned
    return out


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    await audit.log(db, action="apikey.delete", user=user, resource_type="apikey", resource_id=str(key_id))
    await db.delete(key)
    await db.commit()
