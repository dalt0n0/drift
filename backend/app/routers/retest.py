import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.core import audit
from app.models.finding import Finding
from app.models.retest import Retest, RetestHistory
from app.models.activity import Activity
from app.schemas.retest import RetestCreate, RetestUpdate, RetestOut

router = APIRouter(tags=["retest"])


@router.get("/findings/{finding_id}/retest", response_model=RetestOut | None)
async def get_retest(finding_id: uuid.UUID, user: CurrentUser, db: DB) -> RetestOut | None:
    result = await db.execute(
        select(Retest).where(Retest.finding_id == finding_id)
        .order_by(Retest.created_at.desc()).limit(1)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        return None

    history_result = await db.execute(
        select(RetestHistory).where(RetestHistory.retest_id == rt.id)
        .order_by(RetestHistory.created_at.desc())
    )
    out = RetestOut.model_validate(rt)
    out.history = [h for h in history_result.scalars()]
    return out


@router.post("/findings/{finding_id}/retest", response_model=RetestOut, status_code=201)
async def create_retest(
    finding_id: uuid.UUID,
    body: RetestCreate,
    user: CurrentUser,
    db: DB,
) -> RetestOut:
    f_result = await db.execute(select(Finding).where(Finding.id == finding_id))
    f = f_result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    rt = Retest(
        finding_id=finding_id,
        tester_id=user.id,
        status="pending",
        fix_claim=body.fix_claim,
        fix_claim_by=body.fix_claim_by,
        notes=body.notes,
        evidence_requested=body.evidence_requested,
        repro_script=body.repro_script,
        due_by=body.due_by,
    )
    db.add(rt)
    await db.flush()

    db.add(RetestHistory(
        retest_id=rt.id, tester_id=user.id,
        status="pending", notes="Retest created",
    ))
    db.add(Activity(
        engagement_id=f.engagement_id, user_id=user.id,
        actor=user.username, action="created retest",
        subject=f.code, subject_type="finding",
    ))
    await audit.log(db, action="retest.create", user=user, resource_type="finding", resource_id=str(finding_id))
    await db.commit()
    await db.refresh(rt)
    return RetestOut.model_validate(rt)


@router.patch("/findings/{finding_id}/retest/{retest_id}", response_model=RetestOut)
async def update_retest(
    finding_id: uuid.UUID,
    retest_id: uuid.UUID,
    body: RetestUpdate,
    user: CurrentUser,
    db: DB,
) -> RetestOut:
    result = await db.execute(
        select(Retest).where(Retest.id == retest_id, Retest.finding_id == finding_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail="Retest not found")

    old_status = rt.status
    updates = body.model_dump(exclude_none=True)

    for field, value in updates.items():
        setattr(rt, field, value)

    new_status = rt.status
    if new_status != old_status:
        if new_status == "in-progress":
            rt.started_at = datetime.now(tz=timezone.utc)
        elif new_status in {"passed", "failed", "n/a"}:
            rt.completed_at = datetime.now(tz=timezone.utc)

        db.add(RetestHistory(
            retest_id=rt.id, tester_id=user.id,
            status=new_status, notes=body.notes or f"Status changed to {new_status}",
        ))

        f_result = await db.execute(select(Finding).where(Finding.id == finding_id))
        f = f_result.scalar_one_or_none()
        if f:
            db.add(Activity(
                engagement_id=f.engagement_id, user_id=user.id,
                actor=user.username, action=f"retest {new_status}",
                subject=f.code, subject_type="finding",
            ))
            # Auto-resolve finding if retest passed
            if new_status == "passed":
                f.status = "resolved"

    await audit.log(db, action="retest.update", user=user, resource_type="retest", resource_id=str(rt.id),
                    request_data={"old_status": old_status, "new_status": new_status})
    await db.commit()
    await db.refresh(rt)
    return RetestOut.model_validate(rt)
