"""Audit log router: searchable, filterable, paginated, exportable (admin only)."""
from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import verify_chain
from app.core.deps import get_db
from app.core.permissions import Role, require_role
from app.models.audit import AuditEntry
from app.schemas.audit import AuditEntryResponse, AuditListResponse, IntegrityCheckResponse

log = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("", response_model=AuditListResponse)
async def list_audit_entries(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    from_time: Optional[datetime] = Query(None),
    to_time: Optional[datetime] = Query(None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    export_format: Optional[str] = Query(None, pattern="^(json|csv)$"),
):
    """List audit log entries with filtering, pagination, and export."""
    filters = []

    if actor_id:
        filters.append(AuditEntry.actor_id == actor_id)
    if action:
        filters.append(AuditEntry.action.ilike(f"%{action}%"))
    if resource_type:
        filters.append(AuditEntry.resource_type == resource_type)
    if resource_id:
        filters.append(AuditEntry.resource_id == resource_id)
    if outcome:
        filters.append(AuditEntry.outcome == outcome)
    if from_time:
        filters.append(AuditEntry.timestamp >= from_time)
    if to_time:
        filters.append(AuditEntry.timestamp <= to_time)

    base_query = select(AuditEntry)
    count_query = select(func.count(AuditEntry.id))

    if filters:
        base_query = base_query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(AuditEntry.timestamp.desc()).offset(offset).limit(page_size)
    )
    entries = result.scalars().all()

    # CSV export
    if export_format == "csv":
        output = io.StringIO()
        fieldnames = [
            "id", "timestamp", "actor_id", "actor_ip", "user_agent",
            "action", "resource_type", "resource_id", "outcome",
            "request_id", "session_id", "chain_hash",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({
                "id": str(entry.id),
                "timestamp": entry.timestamp.isoformat(),
                "actor_id": str(entry.actor_id) if entry.actor_id else "",
                "actor_ip": entry.actor_ip or "",
                "user_agent": entry.user_agent or "",
                "action": entry.action,
                "resource_type": entry.resource_type or "",
                "resource_id": entry.resource_id or "",
                "outcome": entry.outcome,
                "request_id": entry.request_id or "",
                "session_id": entry.session_id or "",
                "chain_hash": entry.chain_hash,
            })
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
        )

    return AuditListResponse(
        items=[AuditEntryResponse.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/integrity", response_model=IntegrityCheckResponse)
async def check_chain_integrity(
    db: AsyncSession = Depends(get_db),
):
    """Verify the audit log hash chain integrity."""
    is_valid, message = await verify_chain(db)
    return IntegrityCheckResponse(
        timestamp=datetime.now(timezone.utc),
        valid=is_valid,
        message=message,
    )


@router.get("/{entry_id}", response_model=AuditEntryResponse)
async def get_audit_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific audit log entry by ID."""
    from fastapi import HTTPException, status

    result = await db.execute(select(AuditEntry).where(AuditEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://drift.dev/problems/not-found",
                "title": "Not Found",
                "status": 404,
                "detail": "Audit entry not found.",
            },
        )
    return AuditEntryResponse.model_validate(entry)
