import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DB
from app.core.permissions import require_role
from app.core import audit
from app.models.engagement import Engagement, EngagementMember
from app.models.finding import Finding
from app.models.target import Target
from app.models.activity import Activity
from app.schemas.engagement import (
    EngagementCreate, EngagementUpdate, EngagementOut, FindingSummary,
)

router = APIRouter(prefix="/engagements", tags=["engagements"])


async def _engagement_out(e: Engagement, db) -> EngagementOut:
    # Count targets
    tgt_count = await db.execute(
        select(func.count()).select_from(Target).where(Target.engagement_id == e.id)
    )
    target_count = tgt_count.scalar_one()

    # Severity counts
    findings_result = await db.execute(
        select(Finding.severity).where(Finding.engagement_id == e.id)
    )
    severities = findings_result.scalars().all()
    fs = FindingSummary(
        crit=sum(1 for s in severities if s == "critical"),
        high=sum(1 for s in severities if s == "high"),
        med=sum(1 for s in severities if s == "medium"),
        low=sum(1 for s in severities if s == "low"),
        info=sum(1 for s in severities if s == "info"),
    )

    # Team user IDs
    members_result = await db.execute(
        select(EngagementMember.user_id).where(EngagementMember.engagement_id == e.id)
    )
    team = [str(uid) for uid in members_result.scalars()]

    out = EngagementOut.model_validate(e)
    out.target_count = target_count
    out.findings = fs
    out.team = team
    return out


@router.get("", response_model=list[EngagementOut])
async def list_engagements(user: CurrentUser, db: DB) -> list[EngagementOut]:
    result = await db.execute(select(Engagement).order_by(Engagement.updated_at.desc()))
    engagements = result.scalars().all()
    return [await _engagement_out(e, db) for e in engagements]


@router.post("", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    body: EngagementCreate,
    user: CurrentUser,
    db: DB,
) -> EngagementOut:
    require_role(user.role, "lead")

    # Check code uniqueness
    exists = await db.execute(select(Engagement).where(Engagement.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Engagement code already exists")

    e = Engagement(
        code=body.code,
        name=body.name,
        client=body.client,
        type=body.type,
        start_date=body.start_date,
        end_date=body.end_date,
        scope_in=body.scope_in,
        scope_out=body.scope_out,
        rules_of_engagement=body.rules_of_engagement,
        lead_id=body.lead_id or user.id,
    )
    db.add(e)
    await db.flush()  # get e.id

    # Add creator as lead member
    member_ids = set(body.member_ids)
    member_ids.add(user.id)
    if body.lead_id:
        member_ids.add(body.lead_id)

    for uid in member_ids:
        db.add(EngagementMember(engagement_id=e.id, user_id=uid, role="lead" if uid == (body.lead_id or user.id) else "tester"))

    db.add(Activity(
        engagement_id=e.id, user_id=user.id,
        actor=user.username, action="created engagement",
        subject=e.name, subject_type="engagement",
    ))
    await audit.log(db, action="engagement.create", user=user, resource_type="engagement", resource_id=str(e.id))
    await db.commit()
    await db.refresh(e)
    return await _engagement_out(e, db)


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_engagement(engagement_id: uuid.UUID, user: CurrentUser, db: DB) -> EngagementOut:
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return await _engagement_out(e, db)


@router.patch("/{engagement_id}", response_model=EngagementOut)
async def update_engagement(
    engagement_id: uuid.UUID,
    body: EngagementUpdate,
    user: CurrentUser,
    db: DB,
) -> EngagementOut:
    require_role(user.role, "lead")
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Engagement not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(e, field, value)

    db.add(Activity(
        engagement_id=e.id, user_id=user.id,
        actor=user.username, action="updated engagement",
        subject=e.name, subject_type="engagement",
    ))
    await audit.log(db, action="engagement.update", user=user, resource_type="engagement", resource_id=str(e.id))
    await db.commit()
    await db.refresh(e)
    return await _engagement_out(e, db)


@router.delete("/{engagement_id}", status_code=204)
async def delete_engagement(engagement_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    require_role(user.role, "admin")
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Engagement not found")
    await audit.log(db, action="engagement.delete", user=user, resource_type="engagement", resource_id=str(e.id))
    await db.delete(e)
    await db.commit()
