"""
Audit logging helper — call from routers for all sensitive actions.
"""
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def log(
    db: AsyncSession,
    *,
    action: str,
    user: User | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_data: dict | None = None,
    response_status: int | None = None,
) -> None:
    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        ip_address=ip_address,
        user_agent=user_agent,
        request_data=_sanitize(request_data),
        response_status=response_status,
    )
    db.add(entry)
    # Don't commit here — caller commits as part of the request transaction


def _sanitize(data: dict | None) -> dict | None:
    """Strip known sensitive keys before storing in audit log."""
    if not data:
        return None
    REDACT = {"password", "secret", "token", "key", "mfa_code", "current_password", "new_password"}
    return {k: "***" if k.lower() in REDACT else v for k, v in data.items()}


def get_client_ip(request: Any) -> str | None:
    """Extract real IP from X-Forwarded-For (nginx sets this) or direct."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", None)
