"""Organizations router: CRUD for client organizations."""
from __future__ import annotations

import math
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.organization import Organization
from app.schemas.engagement import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.tester)
    org = Organization(
        name=body.name,
        description=body.description,
        website=body.website,
        created_by=current_user.id,
    )
    db.add(org)
    await db.flush()
    await audit_svc.log(
        db, action="organization.create", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="organization", resource_id=str(org.id),
        after_state={"name": org.name},
        request_id=request.headers.get("x-request-id"),
    )
    return org


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
):
    require_role(current_user.role, Role.viewer)
    count_result = await db.execute(select(func.count(Organization.id)))
    total = count_result.scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Organization).order_by(Organization.name).offset(offset).limit(page_size)
    )
    orgs = result.scalars().all()
    return OrganizationListResponse(
        items=[OrganizationResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: uuid.UUID, current_user: CurrentUser, db: DB):
    require_role(current_user.role, Role.viewer)
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Organization not found."})
    return org


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.tester)
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Organization not found."})
    if body.name is not None:
        org.name = body.name
    if body.description is not None:
        org.description = body.description
    if body.website is not None:
        org.website = body.website
    await audit_svc.log(
        db, action="organization.update", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="organization", resource_id=str(org_id),
        request_id=request.headers.get("x-request-id"),
    )
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.lead)
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Organization not found."})
    await audit_svc.log(
        db, action="organization.delete", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="organization", resource_id=str(org_id),
        before_state={"name": org.name},
        request_id=request.headers.get("x-request-id"),
    )
    await db.delete(org)
