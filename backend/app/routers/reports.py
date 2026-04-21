"""Reports router: generate and download engagement reports."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.permissions import Role, require_role
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.scope import ScopeItem
from app.schemas.finding import ReportRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])

_MIME_TYPES = {
    "pdf": "application/pdf",
    "html": "text/html; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "sarif": "application/json; charset=utf-8",
}

_FILE_EXTS = {
    "pdf": "pdf",
    "html": "html",
    "json": "json",
    "csv": "csv",
    "sarif": "sarif.json",
}


@router.post("/engagements/{engagement_id}/reports", tags=["reports"])
async def generate_report(
    engagement_id: uuid.UUID,
    body: ReportRequest,
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Generate and return a report for an engagement.

    - ``report_type``: ``executive``, ``technical``, or ``client``
    - ``format``: ``pdf``, ``html``, ``json``, ``csv``, ``sarif``

    The ``client`` report type is available to ``client_readonly`` role and above.
    All other types require ``tester`` role minimum.
    """
    fmt = body.format
    report_type = body.report_type

    # Authorization: client report available to client_readonly+; others need tester+
    if report_type == "client":
        require_role(current_user.role, Role.client_readonly)
    else:
        require_role(current_user.role, Role.tester)

    engagement = await _get_engagement_or_404(db, engagement_id)
    findings = await _get_findings(db, engagement_id)
    scope_items = await _get_scope(db, engagement_id)

    from app.services import reporting

    try:
        if fmt == "json":
            report_bytes = reporting.generate_json_report(engagement, findings, scope_items)
        elif fmt == "csv":
            report_bytes = reporting.generate_csv_report(engagement, findings)
        elif fmt == "sarif":
            report_bytes = reporting.generate_sarif_report(engagement, findings)
        elif report_type == "executive":
            report_bytes = reporting.generate_executive_report(
                engagement, findings, scope_items, as_pdf=(fmt == "pdf")
            )
        elif report_type == "client":
            report_bytes = reporting.generate_client_report(
                engagement, findings, scope_items, as_pdf=(fmt == "pdf")
            )
        else:  # technical (default)
            report_bytes = reporting.generate_technical_report(
                engagement, findings, scope_items, as_pdf=(fmt == "pdf")
            )
    except Exception as exc:
        logger.error("reports.generate_error", engagement_id=str(engagement_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "about:blank", "title": "Report Error",
                    "status": 500, "detail": f"Report generation failed: {exc}"},
        )

    await audit_svc.log(
        db,
        action="report.generate",
        actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="engagement",
        resource_id=str(engagement_id),
        after_state={"report_type": report_type, "format": fmt, "findings_count": len(findings)},
        request_id=request.headers.get("x-request-id"),
    )
    await db.commit()

    # Store in MinIO asynchronously (non-blocking — don't fail the response if storage fails)
    import asyncio
    asyncio.create_task(
        reporting.store_report_minio(
            report_bytes, str(engagement_id), report_type, _FILE_EXTS[fmt]
        )
    )

    ext = _FILE_EXTS[fmt]
    filename = f"drift_{report_type}_{engagement_id}.{ext}"
    mime = _MIME_TYPES[fmt]

    return Response(
        content=report_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/engagements/{engagement_id}/reports/sbom", tags=["reports"])
async def get_sbom(
    engagement_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Return the application SBOM in CycloneDX JSON format.

    Stub: returns a minimal valid CycloneDX document. Phase 6 will generate
    a full SBOM via Syft.
    """
    require_role(current_user.role, Role.viewer)
    await _get_engagement_or_404(db, engagement_id)

    import json
    from datetime import datetime, timezone

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"vendor": "Drift", "name": "Drift", "version": "0.1.0"}],
            "component": {
                "type": "application",
                "name": "drift",
                "version": "0.1.0",
                "description": "Automated penetration testing platform",
            },
        },
        "components": [],
        "note": "Full SBOM generation via Syft is implemented in Phase 6.",
    }

    return Response(
        content=json.dumps(sbom, indent=2).encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="drift_sbom_{engagement_id}.cdx.json"'},
    )


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


async def _get_findings(db: DB, engagement_id: uuid.UUID) -> list[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.engagement_id == engagement_id)
        .where(Finding.status != "false_positive")
        .order_by(Finding.severity, Finding.created_at)
    )
    return list(result.scalars().all())


async def _get_scope(db: DB, engagement_id: uuid.UUID) -> list[ScopeItem]:
    result = await db.execute(
        select(ScopeItem).where(ScopeItem.engagement_id == engagement_id)
    )
    return list(result.scalars().all())
