from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest, UserCreateRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def list_users(current_user: CurrentUser, db: DB):
    require_role(current_user.role, Role.viewer)
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Admin-only: create a local user account."""
    require_role(current_user.role, Role.admin)

    from argon2 import PasswordHasher
    from sqlalchemy import select as _select
    from app.models.user import User

    # Check for existing username/email
    existing = await db.execute(_select(User).where(
        (User.username == body.username) | (User.email == body.email)
    ))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "about:blank", "title": "Conflict", "status": 409, "detail": "Username or email already exists."}
        )

    ph = PasswordHasher()
    new_user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name or body.username,
        role=body.role or "viewer",
        is_active=True,
        hashed_password=ph.hash(body.password),
        must_change_password=body.must_change_password if body.must_change_password is not None else True,
    )
    db.add(new_user)
    await db.flush()

    await audit_svc.log(
        db, action="user.create", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(new_user.id),
        after_state={"username": new_user.username, "email": new_user.email, "role": new_user.role},
        request_id=request.headers.get("x-request-id"),
    )

    return new_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, current_user: CurrentUser, db: DB):
    if str(current_user.id) != str(user_id):
        require_role(current_user.role, Role.lead)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID, body: UserUpdateRequest,
    request: Request, current_user: CurrentUser, db: DB,
):
    is_self = str(current_user.id) == str(user_id)
    if not is_self:
        require_role(current_user.role, Role.admin)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before = {"full_name": user.full_name, "email": user.email, "role": user.role, "is_active": user.is_active}

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        require_role(current_user.role, Role.admin)
        user.role = body.role
    if body.is_active is not None:
        require_role(current_user.role, Role.admin)
        user.is_active = body.is_active

    after = {"full_name": user.full_name, "email": user.email, "role": user.role, "is_active": user.is_active}
    await audit_svc.log(
        db, action="user.update", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(user.id),
        before_state=before, after_state=after,
        request_id=request.headers.get("x-request-id"),
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, request: Request, current_user: CurrentUser, db: DB):
    require_role(current_user.role, Role.admin)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    await db.delete(user)
    await audit_svc.log(
        db, action="user.delete", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(user_id),
        before_state={"username": user.username, "email": user.email},
        request_id=request.headers.get("x-request-id"),
    )
