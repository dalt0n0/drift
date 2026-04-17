"""
Role-based access control.

Role hierarchy (highest → lowest):
  admin > lead > senior > tester > junior
"""
from enum import IntEnum
from fastapi import HTTPException, status


class Role(IntEnum):
    junior = 1
    tester = 2
    senior = 3
    lead = 4
    admin = 5


ROLE_LEVELS: dict[str, int] = {r.name: r.value for r in Role}


def require_role(user_role: str, minimum: str) -> None:
    """Raise 403 if user_role < minimum required role."""
    user_level = ROLE_LEVELS.get(user_role, 0)
    min_level = ROLE_LEVELS.get(minimum, 999)
    if user_level < min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires '{minimum}' role or higher",
        )


def can_delete_finding(user_role: str) -> bool:
    return ROLE_LEVELS.get(user_role, 0) >= Role.lead


def can_manage_vault(user_role: str) -> bool:
    return ROLE_LEVELS.get(user_role, 0) >= Role.tester


def can_publish_report(user_role: str) -> bool:
    return ROLE_LEVELS.get(user_role, 0) >= Role.lead


def can_manage_users(user_role: str) -> bool:
    return ROLE_LEVELS.get(user_role, 0) >= Role.admin


def can_manage_integrations(user_role: str) -> bool:
    return ROLE_LEVELS.get(user_role, 0) >= Role.lead
