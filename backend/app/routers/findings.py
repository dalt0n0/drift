import os
import uuid
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.deps import CurrentUser, DB
from app.core.permissions import require_role, can_delete_finding
from app.core import audit
from app.models.engagement import Engagement
from app.models.finding import Finding, FindingEvidence, FindingComment
from app.models.retest import Retest
from app.models.target import Target
from app.models.activity import Activity
from app.schemas.finding import (
    FindingCreate, FindingUpdate, FindingOut,
    EvidenceOut, CommentCreate, CommentOut,
)
from app.services.notifications import dispatch_finding_notification

router = APIRouter(tags=["findings"])

# Allowed MIME types for evidence uploads
ALLOWED_MIMES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "text/plain", "text/html",
    "application/pdf",
    "application/json",
    "application/octet-stream",
}


async def _next_finding_code(db, engagement_id: uuid.UUID) -> str:
    result = await db.execute(
        select(func.count()).select_from(Finding).where(Finding.engagement_id == engagement_id)
    )
    count = result.scalar_one()
    return f"F-{1000 + count + 1}"


async def _finding_out(f: Finding, db) -> FindingOut:
    # Counts
    ev_count = await db.execute(
        select(func.count()).select_from(FindingEvidence).where(FindingEvidence.finding_id == f.id)
    )
    cm_count = await db.execute(
        select(func.count()).select_from(FindingComment).where(FindingComment.finding_id == f.id)
    )
    # Latest retest status
    rt_result = await db.execute(
        select(Retest.status).where(Retest.finding_id == f.id).order_by(Retest.created_at.desc()).limit(1)
    )
    retest_status = rt_result.scalar_one_or_none()

    # Target host
    target_host = None
    if f.target_id:
        tgt = await db.execute(select(Target.host).where(Target.id == f.target_id))
        target_host = tgt.scalar_one_or_none()

    out = FindingOut.model_validate(f)
    out.evidence_count = ev_count.scalar_one()
    out.comment_count = cm_count.scalar_one()
    out.retest_status = retest_status
    out.target_host = target_host
    return out


@router.get("/engagements/{engagement_id}/findings", response_model=list[FindingOut])
async def list_findings(
    engagement_id: uuid.UUID,
    severity: str | None = None,
    status: str | None = None,
    user: CurrentUser = None,
    db: DB = None,
) -> list[FindingOut]:
    q = select(Finding).where(Finding.engagement_id == engagement_id)
    if severity:
        q = q.where(Finding.severity == severity)
    if status:
        q = q.where(Finding.status == status)
    q = q.order_by(Finding.created_at.desc())
    result = await db.execute(q)
    findings = result.scalars().all()
    return [await _finding_out(f, db) for f in findings]


@router.post("/engagements/{engagement_id}/findings", response_model=FindingOut, status_code=201)
async def create_finding(
    engagement_id: uuid.UUID,
    body: FindingCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser = None,
    db: DB = None,
) -> FindingOut:
    eng_result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    if not eng_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Engagement not found")

    code = await _next_finding_code(db, engagement_id)
    refs = [r.model_dump() for r in body.references] if body.references else []

    f = Finding(
        code=code,
        engagement_id=engagement_id,
        reporter_id=user.id,
        assignee_id=body.assignee_id or user.id,
        title=body.title,
        severity=body.severity,
        cvss=body.cvss,
        status=body.status,
        target_id=body.target_id,
        category=body.category,
        cwe=body.cwe,
        tags=body.tags,
        confidence=body.confidence,
        summary=body.summary,
        description=body.description,
        steps=body.steps,
        payload=body.payload,
        impact=body.impact,
        recommendation=body.recommendation,
        references=refs,
    )
    db.add(f)
    await db.flush()

    db.add(Activity(
        engagement_id=engagement_id, user_id=user.id,
        actor=user.username, action="opened finding",
        subject=code, subject_type="finding",
        detail=body.title, severity=body.severity,
    ))
    await audit.log(db, action="finding.create", user=user, resource_type="finding", resource_id=str(f.id))
    await db.commit()
    await db.refresh(f)

    # Async notifications
    background_tasks.add_task(dispatch_finding_notification, f, "created")

    return await _finding_out(f, db)


@router.get("/findings/{finding_id}", response_model=FindingOut)
async def get_finding(finding_id: uuid.UUID, user: CurrentUser, db: DB) -> FindingOut:
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    return await _finding_out(f, db)


@router.patch("/findings/{finding_id}", response_model=FindingOut)
async def update_finding(
    finding_id: uuid.UUID,
    body: FindingUpdate,
    background_tasks: BackgroundTasks,
    user: CurrentUser = None,
    db: DB = None,
) -> FindingOut:
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    updates = body.model_dump(exclude_none=True)
    if "references" in updates:
        updates["references"] = [r.model_dump() if hasattr(r, 'model_dump') else r for r in updates["references"]]
    for field, value in updates.items():
        setattr(f, field, value)

    db.add(Activity(
        engagement_id=f.engagement_id, user_id=user.id,
        actor=user.username, action="updated finding",
        subject=f.code, subject_type="finding",
        severity=f.severity,
    ))
    await audit.log(db, action="finding.update", user=user, resource_type="finding", resource_id=str(f.id),
                    request_data={k: v for k, v in updates.items() if k not in {"payload", "description"}})
    await db.commit()
    await db.refresh(f)
    return await _finding_out(f, db)


@router.delete("/findings/{finding_id}", status_code=204)
async def delete_finding(finding_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    if not can_delete_finding(user.role):
        raise HTTPException(status_code=403, detail="Requires lead role or higher")
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    await audit.log(db, action="finding.delete", user=user, resource_type="finding", resource_id=str(f.id))
    await db.delete(f)
    await db.commit()


# ── Evidence ───────────────────────────────────────────────────────────────────

@router.post("/findings/{finding_id}/evidence", response_model=EvidenceOut, status_code=201)
async def upload_evidence(
    finding_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = None,
    db: DB = None,
) -> EvidenceOut:
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Size check
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    # MIME validation — check actual bytes, not just extension
    import magic  # python-magic
    detected_mime = magic.from_buffer(content[:2048], mime=True)
    if detected_mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=415, detail=f"File type not allowed: {detected_mime}")

    # Classify kind
    kind_map = {
        "image/png": "screenshot", "image/jpeg": "screenshot",
        "image/gif": "screenshot", "image/webp": "screenshot",
        "text/plain": "log", "application/json": "log",
        "text/html": "http",
    }
    kind = kind_map.get(detected_mime, "binary")

    # Safe filename — strip path traversal
    safe_name = Path(file.filename or "upload").name
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-")[:255]

    # Store under uploads/<engagement_id>/<finding_id>/
    store_dir = Path(settings.UPLOAD_DIR) / str(f.engagement_id) / str(finding_id)
    store_dir.mkdir(parents=True, exist_ok=True)
    store_path = store_dir / f"{uuid.uuid4()}_{safe_name}"
    store_path.write_bytes(content)

    ev = FindingEvidence(
        finding_id=finding_id,
        kind=kind,
        filename=safe_name,
        storage_path=str(store_path),
        mime_type=detected_mime,
        size_bytes=len(content),
        uploaded_by=user.id,
    )
    db.add(ev)
    await audit.log(db, action="finding.evidence_upload", user=user,
                    resource_type="finding", resource_id=str(finding_id),
                    request_data={"filename": safe_name, "mime": detected_mime, "size": len(content)})
    await db.commit()
    await db.refresh(ev)
    return EvidenceOut.model_validate(ev)


@router.get("/findings/{finding_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(finding_id: uuid.UUID, user: CurrentUser, db: DB) -> list[EvidenceOut]:
    result = await db.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id == finding_id)
        .order_by(FindingEvidence.created_at)
    )
    return [EvidenceOut.model_validate(e) for e in result.scalars()]


@router.delete("/findings/{finding_id}/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    finding_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
) -> None:
    result = await db.execute(
        select(FindingEvidence).where(
            FindingEvidence.id == evidence_id,
            FindingEvidence.finding_id == finding_id,
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    # Delete file from disk
    try:
        Path(ev.storage_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(ev)
    await db.commit()


# ── Comments ───────────────────────────────────────────────────────────────────

@router.get("/findings/{finding_id}/comments", response_model=list[CommentOut])
async def list_comments(finding_id: uuid.UUID, user: CurrentUser, db: DB) -> list[CommentOut]:
    result = await db.execute(
        select(FindingComment).where(FindingComment.finding_id == finding_id)
        .order_by(FindingComment.created_at)
    )
    return [CommentOut.model_validate(c) for c in result.scalars()]


@router.post("/findings/{finding_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    finding_id: uuid.UUID,
    body: CommentCreate,
    user: CurrentUser,
    db: DB,
) -> CommentOut:
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    c = FindingComment(finding_id=finding_id, user_id=user.id, content=body.content)
    db.add(c)
    db.add(Activity(
        engagement_id=f.engagement_id, user_id=user.id,
        actor=user.username, action="commented on",
        subject=f.code, subject_type="finding",
    ))
    await db.commit()
    await db.refresh(c)
    return CommentOut.model_validate(c)
