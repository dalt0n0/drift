import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.core.permissions import can_manage_vault, require_role
from app.core.crypto import encrypt, decrypt
from app.core import audit
from app.models.vault import VaultItem, VaultAccessLog
from app.models.target import Target
from app.schemas.vault import (
    VaultItemCreate, VaultItemUpdate, VaultItemOut,
    VaultItemSecret, VaultAccessLogOut,
)

router = APIRouter(prefix="/vault", tags=["vault"])


async def _item_out(item: VaultItem, db) -> VaultItemOut:
    out = VaultItemOut.model_validate(item)
    # Decrypt username for list display (not secret)
    if item.username_encrypted:
        try:
            out.username = decrypt(item.username_encrypted)
        except Exception:
            out.username = "***"
    # Last access time
    log_result = await db.execute(
        select(VaultAccessLog.created_at)
        .where(VaultAccessLog.item_id == item.id)
        .order_by(VaultAccessLog.created_at.desc()).limit(1)
    )
    out.last_accessed = log_result.scalar_one_or_none()
    # Target host
    if item.target_id:
        tgt = await db.execute(select(Target.host).where(Target.id == item.target_id))
        out.target_host = tgt.scalar_one_or_none()
    return out


@router.get("", response_model=list[VaultItemOut])
async def list_vault(
    engagement_id: uuid.UUID | None = None,
    type: str | None = None,
    user: CurrentUser = None,
    db: DB = None,
) -> list[VaultItemOut]:
    if not can_manage_vault(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    q = select(VaultItem)
    if engagement_id:
        q = q.where(VaultItem.engagement_id == engagement_id)
    if type:
        q = q.where(VaultItem.type == type)
    q = q.order_by(VaultItem.updated_at.desc())
    result = await db.execute(q)
    return [await _item_out(item, db) for item in result.scalars()]


@router.post("", response_model=VaultItemOut, status_code=201)
async def create_vault_item(
    body: VaultItemCreate,
    request: Request,
    user: CurrentUser = None,
    db: DB = None,
) -> VaultItemOut:
    if not can_manage_vault(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    item = VaultItem(
        name=body.name,
        type=body.type,
        username_encrypted=encrypt(body.username) if body.username else None,
        secret_encrypted=encrypt(body.secret),
        notes_encrypted=encrypt(body.notes) if body.notes else None,
        engagement_id=body.engagement_id,
        target_id=body.target_id,
        owner_id=user.id,
        tags=body.tags,
        sensitive=body.sensitive,
        expires_at=body.expires_at,
    )
    db.add(item)
    await db.flush()
    db.add(VaultAccessLog(
        item_id=item.id, user_id=user.id,
        action="created", ip_address=audit.get_client_ip(request),
    ))
    await audit.log(db, action="vault.create", user=user, resource_type="vault", resource_id=str(item.id),
                    request_data={"name": body.name, "type": body.type})
    await db.commit()
    await db.refresh(item)
    return await _item_out(item, db)


@router.get("/{item_id}", response_model=VaultItemOut)
async def get_vault_item(item_id: uuid.UUID, user: CurrentUser, db: DB) -> VaultItemOut:
    if not can_manage_vault(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(select(VaultItem).where(VaultItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return await _item_out(item, db)


@router.post("/{item_id}/reveal", response_model=VaultItemSecret)
async def reveal_secret(
    item_id: uuid.UUID,
    request: Request,
    user: CurrentUser = None,
    db: DB = None,
) -> VaultItemSecret:
    """Decrypt and return secret — every call is logged."""
    if not can_manage_vault(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(select(VaultItem).where(VaultItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")

    try:
        secret = decrypt(item.secret_encrypted)
        username = decrypt(item.username_encrypted) if item.username_encrypted else None
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt secret")

    db.add(VaultAccessLog(
        item_id=item_id, user_id=user.id,
        action="revealed", ip_address=audit.get_client_ip(request),
    ))
    await audit.log(db, action="vault.reveal", user=user, resource_type="vault", resource_id=str(item_id),
                    ip_address=audit.get_client_ip(request))
    await db.commit()
    return VaultItemSecret(secret=secret, username=username)


@router.patch("/{item_id}", response_model=VaultItemOut)
async def update_vault_item(
    item_id: uuid.UUID,
    body: VaultItemUpdate,
    request: Request,
    user: CurrentUser = None,
    db: DB = None,
) -> VaultItemOut:
    if not can_manage_vault(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(select(VaultItem).where(VaultItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")

    updates = body.model_dump(exclude_none=True)
    if "username" in updates:
        item.username_encrypted = encrypt(updates.pop("username"))
    if "notes" in updates:
        item.notes_encrypted = encrypt(updates.pop("notes"))
    for field, value in updates.items():
        setattr(item, field, value)

    db.add(VaultAccessLog(
        item_id=item_id, user_id=user.id,
        action="updated", ip_address=audit.get_client_ip(request),
    ))
    await audit.log(db, action="vault.update", user=user, resource_type="vault", resource_id=str(item_id))
    await db.commit()
    await db.refresh(item)
    return await _item_out(item, db)


@router.post("/{item_id}/rotate", response_model=VaultItemOut)
async def rotate_secret(
    item_id: uuid.UUID,
    body: dict,  # {"new_secret": "..."}
    request: Request,
    user: CurrentUser = None,
    db: DB = None,
) -> VaultItemOut:
    require_role(user.role, "tester")
    result = await db.execute(select(VaultItem).where(VaultItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")

    new_secret = body.get("new_secret", "")
    if not new_secret:
        raise HTTPException(status_code=400, detail="new_secret required")

    item.secret_encrypted = encrypt(new_secret)
    db.add(VaultAccessLog(
        item_id=item_id, user_id=user.id,
        action="rotated", ip_address=audit.get_client_ip(request),
    ))
    await audit.log(db, action="vault.rotate", user=user, resource_type="vault", resource_id=str(item_id))
    await db.commit()
    await db.refresh(item)
    return await _item_out(item, db)


@router.delete("/{item_id}", status_code=204)
async def delete_vault_item(
    item_id: uuid.UUID,
    request: Request,
    user: CurrentUser = None,
    db: DB = None,
) -> None:
    require_role(user.role, "lead")
    result = await db.execute(select(VaultItem).where(VaultItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    db.add(VaultAccessLog(
        item_id=item_id, user_id=user.id,
        action="deleted", ip_address=audit.get_client_ip(request),
    ))
    await audit.log(db, action="vault.delete", user=user, resource_type="vault", resource_id=str(item_id))
    await db.delete(item)
    await db.commit()


@router.get("/{item_id}/log", response_model=list[VaultAccessLogOut])
async def get_access_log(item_id: uuid.UUID, user: CurrentUser, db: DB) -> list[VaultAccessLogOut]:
    require_role(user.role, "lead")
    result = await db.execute(
        select(VaultAccessLog).where(VaultAccessLog.item_id == item_id)
        .order_by(VaultAccessLog.created_at.desc()).limit(100)
    )
    return [VaultAccessLogOut.model_validate(l) for l in result.scalars()]
