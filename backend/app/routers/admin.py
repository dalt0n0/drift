"""Admin router: admin-only user management and system operations."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.core.security import hash_password
from app.models.session import RefreshToken
from app.models.user import User
from app.schemas.user import AdminUserUpdateRequest, UserListResponse, UserResponse

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
async def admin_list_users(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    """Admin: list all users with full details."""
    require_role(current_user.role, Role.admin)

    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def admin_get_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Admin: get any user by ID."""
    require_role(current_user.role, Role.admin)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "User not found.",
            },
        )
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: uuid.UUID,
    request: Request,
    body: AdminUserUpdateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Admin: update any user's fields including role."""
    require_role(current_user.role, Role.admin)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "User not found.",
            },
        )

    before_state = {
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.email is not None:
        user.email = str(body.email)
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.hashed_password = hash_password(body.password)
        user.password_changed_at = datetime.now(timezone.utc)

    user.updated_at = datetime.now(timezone.utc)
    db.add(user)

    after_state = {
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }

    await audit_svc.log(
        db,
        action="admin.user_update",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="user",
        resource_id=str(user.id),
        before_state=before_state,
        after_state=after_state,
        request_id=request.headers.get("x-request-id"),
        outcome="success",
    )

    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Admin: deactivate (soft-delete) a user."""
    require_role(current_user.role, Role.admin)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "User not found.",
            },
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "about:blank",
                "title": "Bad Request",
                "status": 400,
                "detail": "Cannot deactivate your own account.",
            },
        )

    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)

    # Revoke all sessions
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    )
    tokens = result.scalars().all()
    now = datetime.now(timezone.utc)
    for token in tokens:
        token.is_revoked = True
        token.revoked_at = now
        db.add(token)

    await audit_svc.log(
        db,
        action="admin.user_deactivate",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="user",
        resource_id=str(user.id),
        before_state={"username": user.username, "is_active": True},
        after_state={"username": user.username, "is_active": False},
        request_id=request.headers.get("x-request-id"),
        outcome="success",
    )


@router.post("/audit/verify-chain")
async def verify_audit_chain(
    current_user: CurrentUser,
    db: DB,
):
    """Admin: trigger audit chain integrity verification."""
    require_role(current_user.role, Role.admin)
    result = await audit_svc.run_daily_integrity_check(db)
    return result


@router.get("/health")
async def admin_health(current_user: CurrentUser):
    """Admin: detailed system health check."""
    require_role(current_user.role, Role.admin)
    return {
        "status": "healthy",
        "checks": {
            "api": "ok",
        },
    }
