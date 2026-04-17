import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.models.activity import Activity

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def global_activity(limit: int = 50, user: CurrentUser = None, db: DB = None) -> list[dict]:
    result = await db.execute(
        select(Activity).order_by(Activity.created_at.desc()).limit(min(limit, 200))
    )
    return [_row(a) for a in result.scalars()]


@router.get("/engagements/{engagement_id}/activity")
async def engagement_activity(
    engagement_id: uuid.UUID,
    limit: int = 50,
    user: CurrentUser = None,
    db: DB = None,
) -> list[dict]:
    result = await db.execute(
        select(Activity)
        .where(Activity.engagement_id == engagement_id)
        .order_by(Activity.created_at.desc())
        .limit(min(limit, 200))
    )
    return [_row(a) for a in result.scalars()]


def _row(a: Activity) -> dict:
    return {
        "id": str(a.id),
        "engagement_id": str(a.engagement_id) if a.engagement_id else None,
        "user_id": str(a.user_id) if a.user_id else None,
        "actor": a.actor,
        "action": a.action,
        "subject": a.subject,
        "subject_type": a.subject_type,
        "detail": a.detail,
        "severity": a.severity,
        "when": a.created_at,
    }
