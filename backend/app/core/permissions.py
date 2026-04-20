from __future__ import annotations

from enum import IntEnum

from fastapi import HTTPException, status


class Role(IntEnum):
    client_readonly = 1
    viewer = 2
    tester = 3
    lead = 4
    admin = 5


ROLE_LABELS = {
    Role.client_readonly: "client_readonly",
    Role.viewer: "viewer",
    Role.tester: "tester",
    Role.lead: "lead",
    Role.admin: "admin",
}

LABEL_TO_ROLE: dict[str, Role] = {v: k for k, v in ROLE_LABELS.items()}


def role_from_str(label: str) -> Role:
    try:
        return LABEL_TO_ROLE[label.lower()]
    except KeyError:
        raise ValueError(f"Unknown role: {label!r}")


def require_role(user_role: str, minimum: Role) -> None:
    """Raise HTTP 403 if user_role is below minimum."""
    try:
        actual = role_from_str(user_role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    if actual < minimum:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role '{minimum.name}' or higher",
        )
