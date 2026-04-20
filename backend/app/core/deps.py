from __future__ import annotations

import hashlib
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role, require_role
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import APIKey, User

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DB,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """
    Accepts either:
      - Bearer <JWT access token>
      - Bearer drk_<API key>
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise exc

    token = credentials.credentials

    # ── API key path ───────────────────────────────────────────────────────────
    if token.startswith("drk_"):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(APIKey)
            .where(APIKey.key_hash == key_hash, APIKey.is_active == True)
            .join(APIKey.user)
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise exc
        user = api_key.user
        if not user.is_active:
            raise exc
        # Update last_used_at lazily (fire-and-forget style via flush)
        from datetime import datetime, timezone
        api_key.last_used_at = datetime.now(timezone.utc)
        return user

    # ── JWT path ───────────────────────────────────────────────────────────────
    payload = decode_access_token(token)
    if payload is None:
        raise exc

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise exc

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return user


CurrentUser = Annotated[User, Depends(get_current_active_user)]


def require_min_role(minimum: Role):
    """Returns a FastAPI dependency that enforces a minimum role."""
    async def _check(user: CurrentUser) -> User:
        require_role(user.role, minimum)
        return user
    return Depends(_check)
