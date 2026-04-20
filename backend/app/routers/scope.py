"""Scope management router for engagements."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role, role_from_str
from app.models.engagement import Engagement
from app.models.scope import ScopeItem, ScopeValidator, ScopeValidationError
from app.schemas.engagement import (
    ScopeItemBatchRequest,
    ScopeItemCreateRequest,
    ScopeItemResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/scope", tags=["scope"])


async def _get_engagement_with_access(
    engagement_id: uuid.UUID, current_user, db
) -> Engagement:
    """Helper to get engagement with access check."""
    result = await db.execute(
        select(Engagement).where(Engagement.id == engagement_id)
    )
    engagement = result.scalar_one_or_none()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "Engagement not found.",
            },
        )

    user_role = role_from_str(current_user.role)
    if user_role < Role.lead and engagement.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "about:blank",
                "title": "Forbidden",
                "status": 403,
                "detail": "Access denied.",
            },
        )

    return engagement


@router.get("", response_model=list[ScopeItemResponse])
async def list_scope_items(
    engagement_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """List all scope items for an engagement."""
    require_role(current_user.role, Role.tester)
    await _get_engagement_with_access(engagement_id, current_user, db)

    result = await db.execute(
        select(ScopeItem)
        .where(ScopeItem.engagement_id == engagement_id)
        .order_by(ScopeItem.created_at.asc())
    )
    return result.scalars().all()


@router.post("", response_model=ScopeItemResponse, status_code=status.HTTP_201_CREATED)
async def add_scope_item(
    engagement_id: uuid.UUID,
    body: ScopeItemCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Add a scope item to an engagement."""
    require_role(current_user.role, Role.tester)
    await _get_engagement_with_access(engagement_id, current_user, db)

    # Validate against hard-blocks (exclusions bypass validation)
    if not body.is_excluded:
        try:
            ScopeValidator.validate(body.type, body.value)
        except ScopeValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "about:blank",
                    "title": "Scope Validation Failed",
                    "status": 400,
                    "detail": str(e),
                    "blocked_reason": e.blocked_reason,
                },
            )

    scope_item = ScopeItem(
        engagement_id=engagement_id,
        type=body.type,
        value=body.value,
        is_excluded=body.is_excluded,
        notes=body.notes,
    )
    db.add(scope_item)
    await db.flush()

    await audit_svc.log(
        db,
        action="scope.add",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="scope_item",
        resource_id=str(scope_item.id),
        after_state={
            "engagement_id": str(engagement_id),
            "type": body.type,
            "value": body.value,
            "is_excluded": body.is_excluded,
        },
        request_id=request.headers.get("x-request-id"),
    )

    return scope_item


@router.post("/batch", response_model=list[ScopeItemResponse], status_code=status.HTTP_201_CREATED)
async def add_scope_items_batch(
    engagement_id: uuid.UUID,
    body: ScopeItemBatchRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Add multiple scope items at once. Validates all before inserting any."""
    require_role(current_user.role, Role.tester)
    await _get_engagement_with_access(engagement_id, current_user, db)

    # Validate all non-excluded items first
    items_to_validate = [
        {"type": item.type, "value": item.value}
        for item in body.items
        if not item.is_excluded
    ]
    errors = ScopeValidator.validate_batch(items_to_validate)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "about:blank",
                "title": "Scope Validation Failed",
                "status": 400,
                "detail": "One or more scope items failed validation.",
                "errors": errors,
            },
        )

    created = []
    for item in body.items:
        scope_item = ScopeItem(
            engagement_id=engagement_id,
            type=item.type,
            value=item.value,
            is_excluded=item.is_excluded,
            notes=item.notes,
        )
        db.add(scope_item)
        created.append(scope_item)

    await db.flush()

    await audit_svc.log(
        db,
        action="scope.batch_add",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="scope_item",
        resource_id=str(engagement_id),
        after_state={
            "engagement_id": str(engagement_id),
            "count": len(created),
            "items": [{"type": i.type, "value": i.value} for i in created],
        },
        request_id=request.headers.get("x-request-id"),
    )

    return created


@router.delete("/{scope_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scope_item(
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Remove a scope item from an engagement."""
    require_role(current_user.role, Role.tester)
    await _get_engagement_with_access(engagement_id, current_user, db)

    result = await db.execute(
        select(ScopeItem).where(
            ScopeItem.id == scope_item_id,
            ScopeItem.engagement_id == engagement_id,
        )
    )
    scope_item = result.scalar_one_or_none()
    if not scope_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "Scope item not found.",
            },
        )

    await audit_svc.log(
        db,
        action="scope.delete",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="scope_item",
        resource_id=str(scope_item_id),
        before_state={
            "type": scope_item.type,
            "value": scope_item.value,
            "is_excluded": scope_item.is_excluded,
        },
        request_id=request.headers.get("x-request-id"),
    )

    await db.delete(scope_item)
