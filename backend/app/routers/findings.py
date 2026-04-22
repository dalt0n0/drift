"""Findings CRUD router with CVE enrichment and CVSS calculation."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.core import audit as audit_svc
from app.core import attack as attack_svc
from app.core import cvss as cvss_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.schemas.finding import (
    CVEEnrichRequest,
    CVEEnrichResponse,
    CVSSCalculateRequest,
    CVSSCalculateResponse,
    FindingCreateRequest,
    FindingListResponse,
    FindingResponse,
    FindingUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["findings"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/engagements/{engagement_id}/findings",
    response_model=FindingListResponse,
    tags=["findings"],
)
async def list_findings(
    engagement_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: str | None = Query(None),
    status: str | None = Query(None, alias="status"),
    tool: str | None = Query(None),
    cisa_kev: bool | None = Query(None),
):
    """List findings for an engagement with filtering and pagination."""
    require_role(current_user.role, Role.viewer)
    await _get_engagement_or_404(db, engagement_id)

    q = select(Finding).where(Finding.engagement_id == engagement_id)

    if severity:
        q = q.where(Finding.severity == severity)
    if status:
        q = q.where(Finding.status == status)
    if tool:
        q = q.where(Finding.discovered_by == tool)
    if cisa_kev is not None:
        q = q.where(Finding.cisa_kev == cisa_kev)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    q = q.order_by(Finding.severity, Finding.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    # Compute by_severity for full result set (not just page)
    sev_q = select(Finding.severity, func.count()).where(
        Finding.engagement_id == engagement_id
    ).group_by(Finding.severity)
    sev_rows = (await db.execute(sev_q)).all()
    by_severity = {s: c for s, c in sev_rows}

    return FindingListResponse(
        findings=[FindingResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        pages=max(1, math.ceil(total / page_size)),
        by_severity=by_severity,
    )


@router.post(
    "/engagements/{engagement_id}/findings",
    response_model=FindingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["findings"],
)
async def create_finding(
    engagement_id: uuid.UUID,
    body: FindingCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Create a finding manually. Tools also write findings via this path."""
    require_role(current_user.role, Role.tester)
    await _get_engagement_or_404(db, engagement_id)

    # Auto-tag ATT&CK techniques if not provided
    attack_ids = body.attack_technique_ids
    if not attack_ids:
        attack_ids = attack_svc.tag_finding(body.title, body.description, body.discovered_by)

    finding = Finding(
        engagement_id=engagement_id,
        run_id=body.run_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        cvss_score=body.cvss_score,
        cvss_vector=body.cvss_vector,
        epss_score=body.epss_score,
        epss_percentile=body.epss_percentile,
        cve_ids=body.cve_ids or [],
        cisa_kev=body.cisa_kev,
        attack_technique_ids=attack_ids,
        affected_target=body.affected_target,
        evidence=body.evidence or {},
        status="open",
        discovered_by=body.discovered_by,
        notes=body.notes,
        deduplicated_from=[],
    )
    db.add(finding)
    await db.flush()

    await audit_svc.log(
        db,
        action="finding.create",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="finding",
        resource_id=str(finding.id),
        after_state={
            "title": finding.title,
            "severity": finding.severity,
            "engagement_id": str(engagement_id),
        },
        request_id=request.headers.get("x-request-id"),
    )
    await db.commit()
    await db.refresh(finding)
    return FindingResponse.model_validate(finding)


@router.get(
    "/findings/{finding_id}",
    response_model=FindingResponse,
    tags=["findings"],
)
async def get_finding(
    finding_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.viewer)
    finding = await _get_finding_or_404(db, finding_id)
    return FindingResponse.model_validate(finding)


@router.patch(
    "/findings/{finding_id}",
    response_model=FindingResponse,
    tags=["findings"],
)
async def update_finding(
    finding_id: uuid.UUID,
    body: FindingUpdateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.tester)
    finding = await _get_finding_or_404(db, finding_id)

    before_state = {"severity": finding.severity, "status": finding.status}
    changed = body.model_dump(exclude_none=True)

    for field, value in changed.items():
        setattr(finding, field, value)
    finding.updated_at = datetime.now(timezone.utc)

    await audit_svc.log(
        db,
        action="finding.update",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="finding",
        resource_id=str(finding.id),
        before_state=before_state,
        after_state=changed,
        request_id=request.headers.get("x-request-id"),
    )
    await db.commit()
    await db.refresh(finding)
    return FindingResponse.model_validate(finding)


@router.delete(
    "/findings/{finding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["findings"],
)
async def delete_finding(
    finding_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    require_role(current_user.role, Role.tester)
    finding = await _get_finding_or_404(db, finding_id)

    await audit_svc.log(
        db,
        action="finding.delete",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="finding",
        resource_id=str(finding.id),
        before_state={"title": finding.title, "severity": finding.severity},
        request_id=request.headers.get("x-request-id"),
    )
    await db.delete(finding)
    await db.commit()


# ---------------------------------------------------------------------------
# CVE Enrichment
# ---------------------------------------------------------------------------

@router.post(
    "/findings/enrich-cves",
    response_model=CVEEnrichResponse,
    tags=["findings"],
)
async def enrich_cves(
    body: CVEEnrichRequest,
    current_user: CurrentUser,
    _db: DB,
):
    """Fetch NVD + EPSS + CISA KEV data for a list of CVE IDs."""
    require_role(current_user.role, Role.tester)
    from app.services.correlation import enrich_cves_batch, fetch_epss, fetch_cisa_kev
    import asyncio

    nvd, epss, kev = await asyncio.gather(
        enrich_cves_batch(body.cve_ids),
        fetch_epss(body.cve_ids),
        fetch_cisa_kev(),
    )

    results: dict = {}
    for cve_id in body.cve_ids:
        entry = nvd.get(cve_id, {})
        entry["epss"] = epss.get(cve_id, {})
        entry["cisa_kev"] = kev.get(cve_id, False)
        results[cve_id] = entry

    return CVEEnrichResponse(results=results)


# ---------------------------------------------------------------------------
# CVSS Calculator
# ---------------------------------------------------------------------------

@router.post(
    "/findings/calculate-cvss",
    response_model=CVSSCalculateResponse,
    tags=["findings"],
)
async def calculate_cvss(
    body: CVSSCalculateRequest,
    current_user: CurrentUser,
    _db: DB,
):
    """Calculate CVSS 3.1 base score from a vector string."""
    require_role(current_user.role, Role.viewer)
    try:
        result = cvss_svc.calculate(body.vector)
    except cvss_svc.CVSSParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "about:blank", "title": "Invalid CVSS Vector",
                    "status": 422, "detail": str(exc)},
        )
    return CVSSCalculateResponse(**result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_engagement_or_404(db: DB, engagement_id: uuid.UUID) -> Engagement:
    row = await db.get(Engagement, engagement_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "about:blank", "title": "Not Found",
                    "status": 404, "detail": "Engagement not found"},
        )
    return row


async def _get_finding_or_404(db: DB, finding_id: uuid.UUID) -> Finding:
    row = await db.get(Finding, finding_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "about:blank", "title": "Not Found",
                    "status": 404, "detail": "Finding not found"},
        )
    return row
