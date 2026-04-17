import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Request
from sqlalchemy import select, func

from app.core.deps import CurrentUser, DB
from app.core.permissions import require_role
from app.core import audit
from app.models.target import Target
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.activity import Activity
from app.schemas.target import TargetCreate, TargetUpdate, TargetOut

router = APIRouter(tags=["targets"])


async def _target_out(t: Target, db) -> TargetOut:
    count_result = await db.execute(
        select(func.count()).select_from(Finding).where(Finding.target_id == t.id)
    )
    finding_count = count_result.scalar_one()
    out = TargetOut.model_validate(t)
    out.finding_count = finding_count
    return out


@router.get("/engagements/{engagement_id}/targets", response_model=list[TargetOut], tags=["targets"])
async def list_targets(engagement_id: uuid.UUID, user: CurrentUser, db: DB) -> list[TargetOut]:
    result = await db.execute(
        select(Target).where(Target.engagement_id == engagement_id).order_by(Target.host)
    )
    targets = result.scalars().all()
    return [await _target_out(t, db) for t in targets]


@router.post("/engagements/{engagement_id}/targets", response_model=TargetOut, status_code=201, tags=["targets"])
async def create_target(
    engagement_id: uuid.UUID,
    body: TargetCreate,
    user: CurrentUser,
    db: DB,
) -> TargetOut:
    eng_result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    if not eng_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Engagement not found")

    t = Target(engagement_id=engagement_id, **body.model_dump())
    db.add(t)
    await db.flush()
    db.add(Activity(
        engagement_id=engagement_id, user_id=user.id,
        actor=user.username, action="added target",
        subject=t.host, subject_type="target",
    ))
    await audit.log(db, action="target.create", user=user, resource_type="target", resource_id=str(t.id))
    await db.commit()
    await db.refresh(t)
    return await _target_out(t, db)


@router.get("/targets/{target_id}", response_model=TargetOut)
async def get_target(target_id: uuid.UUID, user: CurrentUser, db: DB) -> TargetOut:
    result = await db.execute(select(Target).where(Target.id == target_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    return await _target_out(t, db)


@router.patch("/targets/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: uuid.UUID,
    body: TargetUpdate,
    user: CurrentUser,
    db: DB,
) -> TargetOut:
    result = await db.execute(select(Target).where(Target.id == target_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(t, field, value)

    await audit.log(db, action="target.update", user=user, resource_type="target", resource_id=str(t.id))
    await db.commit()
    await db.refresh(t)
    return await _target_out(t, db)


@router.delete("/targets/{target_id}", status_code=204)
async def delete_target(target_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    require_role(user.role, "lead")
    result = await db.execute(select(Target).where(Target.id == target_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    await audit.log(db, action="target.delete", user=user, resource_type="target", resource_id=str(t.id))
    await db.delete(t)
    await db.commit()


@router.post("/targets/{target_id}/scan", status_code=202)
async def trigger_scan(target_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    """Mark last_scan timestamp — actual scan integration handled by integrations router."""
    result = await db.execute(select(Target).where(Target.id == target_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    t.last_scan = datetime.now(tz=timezone.utc)
    db.add(Activity(
        engagement_id=t.engagement_id, user_id=user.id,
        actor=user.username, action="triggered scan",
        subject=t.host, subject_type="target",
    ))
    await db.commit()
    return {"status": "scan_queued", "target": t.host}
