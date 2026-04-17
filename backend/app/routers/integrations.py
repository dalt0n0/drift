"""
Integrations: Slack, SMTP, Webhook config + Nuclei/Burp/Nmap import.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.core.permissions import can_manage_integrations
from app.core.crypto import encrypt, decrypt
from app.core import audit
from app.models.engagement import Engagement
from app.models.activity import Activity
from app.services.integrations.nuclei import parse_nuclei_xml
from app.services.integrations.burp import parse_burp_xml
from app.services.integrations.nmap import parse_nmap_xml
from app.models.target import Target
from app.models.finding import Finding

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── Integration config (stored encrypted in a simple key-value table) ──────────
# Using a simple in-DB approach via a settings-style model

class IntegrationConfig(BaseModel):
    type: str
    config: dict  # Slack: {"webhook_url": "..."}, SMTP: already in env


@router.get("")
async def list_integrations(user: CurrentUser, db: DB) -> list[dict]:
    """Returns configured integrations (no secrets)."""
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT type, status, last_used FROM integrations ORDER BY type")
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.post("/nuclei/import", status_code=201)
async def import_nuclei(
    engagement_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = None,
    db: DB = None,
) -> dict:
    """Import Nuclei JSON/XML results as findings."""
    if not can_manage_integrations(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    eng_result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    if not eng_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Engagement not found")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        items = parse_nuclei_xml(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    created = 0
    for item in items:
        f = Finding(
            code=f"N-{1000 + created + 1}",
            engagement_id=engagement_id,
            reporter_id=user.id,
            assignee_id=user.id,
            title=item["title"],
            severity=item.get("severity", "info"),
            cvss=0.0,
            status="open",
            category="Nuclei",
            summary=item.get("description", ""),
            description=item.get("description", ""),
            payload=item.get("matched", ""),
            tags=item.get("tags", []),
        )
        db.add(f)
        created += 1

    db.add(Activity(
        engagement_id=engagement_id, user_id=user.id,
        actor=user.username, action="imported Nuclei scan",
        subject=f"{created} findings", subject_type="scan",
    ))
    await audit.log(db, action="integration.nuclei_import", user=user,
                    resource_type="engagement", resource_id=str(engagement_id),
                    request_data={"findings_imported": created})
    await db.commit()
    return {"imported": created}


@router.post("/burp/import", status_code=201)
async def import_burp(
    engagement_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = None,
    db: DB = None,
) -> dict:
    """Import Burp Suite XML export as findings."""
    if not can_manage_integrations(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        items = parse_burp_xml(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(Finding).where(Finding.engagement_id == engagement_id)
    )
    base = count_result.scalar_one()

    created = 0
    for item in items:
        f = Finding(
            code=f"B-{base + created + 1}",
            engagement_id=engagement_id,
            reporter_id=user.id,
            assignee_id=user.id,
            title=item["title"],
            severity=item.get("severity", "info"),
            cvss=_burp_severity_to_cvss(item.get("severity", "info")),
            status="open",
            category="Burp Suite",
            summary=item.get("detail", ""),
            description=item.get("background", ""),
            recommendation=item.get("remediation_background", ""),
            payload=item.get("request", ""),
        )
        db.add(f)
        created += 1

    db.add(Activity(
        engagement_id=engagement_id, user_id=user.id,
        actor=user.username, action="imported Burp scan",
        subject=f"{created} findings", subject_type="scan",
    ))
    await audit.log(db, action="integration.burp_import", user=user,
                    resource_type="engagement", resource_id=str(engagement_id))
    await db.commit()
    return {"imported": created}


@router.post("/nmap/import", status_code=201)
async def import_nmap(
    engagement_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = None,
    db: DB = None,
) -> dict:
    """Import Nmap XML as targets."""
    if not can_manage_integrations(user.role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        hosts = parse_nmap_xml(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    created = 0
    for host in hosts:
        # Skip if host already exists in this engagement
        existing = await db.execute(
            select(Target).where(
                Target.engagement_id == engagement_id,
                Target.ip == host["ip"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        t = Target(
            engagement_id=engagement_id,
            host=host.get("hostname") or host["ip"],
            ip=host["ip"],
            type="Network",
            ports=host.get("ports", []),
            state="active",
        )
        db.add(t)
        created += 1

    db.add(Activity(
        engagement_id=engagement_id, user_id=user.id,
        actor=user.username, action="imported Nmap scan",
        subject=f"{created} new targets", subject_type="scan",
    ))
    await audit.log(db, action="integration.nmap_import", user=user,
                    resource_type="engagement", resource_id=str(engagement_id))
    await db.commit()
    return {"imported": created}


def _burp_severity_to_cvss(severity: str) -> float:
    return {"critical": 9.0, "high": 7.5, "medium": 5.0, "low": 3.0, "info": 0.0}.get(severity.lower(), 0.0)
