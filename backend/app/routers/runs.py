"""Engagement run management router."""
from __future__ import annotations

import math
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.run import EngagementRun
from app.schemas.engagement import (
    DryRunResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
)
from app.services.orchestrator import AuthorizationNotConfirmedError, OrchestratorService

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["runs"])


@router.post(
    "/engagements/{engagement_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run(
    engagement_id: uuid.UUID,
    body: RunCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Create a new run for an engagement."""
    require_role(current_user.role, Role.tester)

    orch = OrchestratorService(db)
    try:
        run = await orch.create_run(
            engagement_id=engagement_id,
            triggered_by=current_user.id,
            plugin_names=body.plugin_names,
            safe_mode=body.safe_mode,
        )
    except AuthorizationNotConfirmedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "about:blank",
                "title": "Authorization Required",
                "status": 403,
                "detail": str(e),
            },
        )

    await audit_svc.log(
        db,
        action="run.create",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement_run",
        resource_id=str(run.id),
        after_state={
            "engagement_id": str(engagement_id),
            "safe_mode": body.safe_mode,
            "plugins": body.plugin_names,
        },
        request_id=request.headers.get("x-request-id"),
    )

    return run


@router.get("/engagements/{engagement_id}/runs", response_model=RunListResponse)
async def list_engagement_runs(
    engagement_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all runs for an engagement."""
    require_role(current_user.role, Role.tester)

    query = select(EngagementRun).where(EngagementRun.engagement_id == engagement_id)
    count_query = select(func.count(EngagementRun.id)).where(
        EngagementRun.engagement_id == engagement_id
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(EngagementRun.created_at.desc()).offset(offset).limit(page_size)
    )
    runs = result.scalars().all()

    return RunListResponse(
        items=[RunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post(
    "/engagements/{engagement_id}/runs/dry-run",
    response_model=DryRunResponse,
)
async def dry_run(
    engagement_id: uuid.UUID,
    body: RunCreateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Preview an execution plan without creating a run."""
    require_role(current_user.role, Role.tester)

    orch = OrchestratorService(db)
    result = await orch.dry_run(
        engagement_id=engagement_id,
        plugin_names=body.plugin_names,
        safe_mode=body.safe_mode,
    )

    return DryRunResponse(**result)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Get a specific run by ID."""
    require_role(current_user.role, Role.tester)

    result = await db.execute(
        select(EngagementRun).where(EngagementRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": "Run not found.",
            },
        )

    return run


@router.post("/runs/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Resume a paused or failed run."""
    require_role(current_user.role, Role.tester)

    orch = OrchestratorService(db)
    try:
        run = await orch.resume_run(run_id)
    except AuthorizationNotConfirmedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "about:blank",
                "title": "Authorization Required",
                "status": 403,
                "detail": str(e),
            },
        )

    await audit_svc.log(
        db,
        action="run.resume",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement_run",
        resource_id=str(run.id),
        request_id=request.headers.get("x-request-id"),
    )

    return run


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Cancel a pending or running run."""
    require_role(current_user.role, Role.tester)

    orch = OrchestratorService(db)
    run = await orch.cancel_run(run_id)

    await audit_svc.log(
        db,
        action="run.cancel",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="engagement_run",
        resource_id=str(run.id),
        request_id=request.headers.get("x-request-id"),
    )

    return run
