import uuid

from fastapi import APIRouter, status
from sqlalchemy import select, update

from app.core.deps import CurrentUser, DB
from app.core.permissions import require_role
from app.models.notification import Notification, NotificationRule
from pydantic import BaseModel

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: CurrentUser = None,
    db: DB = None,
) -> list[dict]:
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read == False)
    q = q.order_by(Notification.created_at.desc()).limit(min(limit, 100))
    result = await db.execute(q)
    return [
        {
            "id": str(n.id), "kind": n.kind, "title": n.title,
            "meta": n.meta, "link": n.link, "read": n.read,
            "when": n.created_at,
        }
        for n in result.scalars()
    ]


@router.patch("/notifications/{notification_id}/read", status_code=204)
async def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(read=True)
    )
    await db.commit()


@router.patch("/notifications/read-all", status_code=204)
async def mark_all_read(user: CurrentUser, db: DB) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read == False)
        .values(read=True)
    )
    await db.commit()


# ── Notification rules ─────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    trigger_event: str
    channels: list[str]
    target_description: str = ""
    active: bool = True


class RuleUpdate(BaseModel):
    channels: list[str] | None = None
    target_description: str | None = None
    active: bool | None = None


@router.get("/notification-rules")
async def list_rules(user: CurrentUser, db: DB) -> list[dict]:
    require_role(user.role, "lead")
    result = await db.execute(select(NotificationRule).order_by(NotificationRule.created_at))
    return [
        {
            "id": str(r.id), "trigger_event": r.trigger_event,
            "channels": r.channels, "target_description": r.target_description,
            "active": r.active,
        }
        for r in result.scalars()
    ]


@router.post("/notification-rules", status_code=201)
async def create_rule(body: RuleCreate, user: CurrentUser, db: DB) -> dict:
    require_role(user.role, "lead")
    r = NotificationRule(**body.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return {"id": str(r.id), **body.model_dump()}


@router.patch("/notification-rules/{rule_id}", status_code=204)
async def update_rule(rule_id: uuid.UUID, body: RuleUpdate, user: CurrentUser, db: DB) -> None:
    require_role(user.role, "lead")
    result = await db.execute(select(NotificationRule).where(NotificationRule.id == rule_id))
    r = result.scalar_one_or_none()
    if r:
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(r, k, v)
        await db.commit()


@router.delete("/notification-rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    require_role(user.role, "lead")
    result = await db.execute(select(NotificationRule).where(NotificationRule.id == rule_id))
    r = result.scalar_one_or_none()
    if r:
        await db.delete(r)
        await db.commit()
