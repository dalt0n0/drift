"""Plugin/module listing router."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.core.permissions import Role, require_role
from app.plugins.manifest import registry
from app.schemas.engagement import ModuleResponse

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("", response_model=list[ModuleResponse])
async def list_modules(
    current_user: CurrentUser,
    category: str | None = None,
    safe_only: bool = False,
):
    """List all available plugin modules."""
    require_role(current_user.role, Role.tester)

    if safe_only:
        plugins = registry.list_safe_mode()
    elif category:
        plugins = registry.list_by_category(category)
    else:
        plugins = registry.list_all()

    return [
        ModuleResponse(
            name=p.name,
            version=p.version,
            category=p.category,
            is_intrusive=p.is_intrusive,
            safe_mode_allowed=p.safe_mode_allowed,
            timeout_seconds=p.timeout_seconds,
            rate_limit=p.rate_limit,
            inputs=list(p.inputs),
            outputs=list(p.outputs),
            dependencies=list(p.dependencies),
        )
        for p in plugins
    ]
