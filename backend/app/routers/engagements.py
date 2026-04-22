"""Engagement CRUD router with authorization upload and confirmation."""
from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, status
from sqlalchemy import func, select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.engagement import Engagement, EngagementStatus
from app.schemas.engagement import (
    EngagementCreateRequest,
    EngagementListResponse,
    EngagementResponse,
    EngagementUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    body: EngagementCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Create a new engagement."""
    require_role(current_user.role, Role.tester)

    engagement = Engagement(
        title=body.title,
        client_name=body.client_name,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        owner_id=current_user.id,
        status=EngagementStatus.draft.value,
    )
    db.add(engagement)
    await db.flush()

    await audit_svc.log(
        db,
        action="engagement.create",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="engagement",
        resource_id=str(engagement.id),
        after_state={"title": engagement.title, "client_name": engagement.client_name},
        request_id=request.headers.get("x-request-id"),
    )

    return engagement


@router.get("", response_model=EngagementListResponse)
async def list_engagements(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
):
    """List engagements visible to the current user."""
    require_role(current_user.role, Role.tester)

    query = select(Engagement)
    count_query = select(func.count(Engagement.id))

    # Non-admins only see their own engagements
    from app.core.permissions import role_from_str
    user_role = role_from_str(current_user.role)
    if user_role < Role.lead:
        query = query.where(Engagement.owner_id == current_user.id)
        count_query = count_query.where(Engagement.owner_id == current_user.id)

    if status_filter:
        query = query.where(Engagement.status == status_filter)
        count_query = count_query.where(Engagement.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Engagement.created_at.desc()).offset(offset).limit(page_size)
    )
    engagements = result.scalars().all()

    return EngagementListResponse(
        items=[EngagementResponse.model_validate(e) for e in engagements],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Get a single engagement by ID."""
    require_role(current_user.role, Role.tester)

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

    # Access check: tester can only view own engagements
    from app.core.permissions import role_from_str
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


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def update_engagement(
    engagement_id: uuid.UUID,
    body: EngagementUpdateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Update an engagement."""
    require_role(current_user.role, Role.tester)

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

    # Only owner or lead+ can update
    from app.core.permissions import role_from_str
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

    before_state = {
        "title": engagement.title,
        "status": engagement.status,
        "client_name": engagement.client_name,
    }

    if body.title is not None:
        engagement.title = body.title
    if body.client_name is not None:
        engagement.client_name = body.client_name
    if body.description is not None:
        engagement.description = body.description
    if body.status is not None:
        engagement.status = body.status
    if body.start_date is not None:
        engagement.start_date = body.start_date
    if body.end_date is not None:
        engagement.end_date = body.end_date

    engagement.updated_at = datetime.now(timezone.utc)

    after_state = {
        "title": engagement.title,
        "status": engagement.status,
        "client_name": engagement.client_name,
    }

    await audit_svc.log(
        db,
        action="engagement.update",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="engagement",
        resource_id=str(engagement.id),
        before_state=before_state,
        after_state=after_state,
        request_id=request.headers.get("x-request-id"),
    )

    return engagement


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(
    engagement_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Archive (soft-delete) an engagement."""
    require_role(current_user.role, Role.lead)

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

    engagement.status = EngagementStatus.archived.value
    engagement.updated_at = datetime.now(timezone.utc)

    await audit_svc.log(
        db,
        action="engagement.archive",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement",
        resource_id=str(engagement.id),
        after_state={"status": "archived"},
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/{engagement_id}/authorization", response_model=EngagementResponse)
async def upload_authorization(
    engagement_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
):
    """Upload authorization letter for an engagement."""
    require_role(current_user.role, Role.tester)

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

    # Read file and compute hash
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Store path (in production would go to MinIO)
    storage_path = f"artifacts/{engagement_id}/authorization/{file.filename}"

    engagement.authorization_letter_path = storage_path
    engagement.authorization_hash = file_hash
    engagement.updated_at = datetime.now(timezone.utc)

    await audit_svc.log(
        db,
        action="engagement.authorization_uploaded",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement",
        resource_id=str(engagement.id),
        after_state={
            "authorization_hash": file_hash,
            "filename": file.filename,
        },
        request_id=request.headers.get("x-request-id"),
    )

    return engagement


@router.post("/{engagement_id}/authorization/confirm", response_model=EngagementResponse)
async def confirm_authorization(
    engagement_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Confirm the authorization letter has been reviewed and accepted."""
    require_role(current_user.role, Role.lead)

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

    engagement.authorization_confirmed = True
    engagement.updated_at = datetime.now(timezone.utc)

    await audit_svc.log(
        db,
        action="engagement.authorization_confirmed",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement",
        resource_id=str(engagement.id),
        after_state={
            "authorization_confirmed": True,
            "authorization_hash": engagement.authorization_hash,
        },
        request_id=request.headers.get("x-request-id"),
    )

    return engagement
