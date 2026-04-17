import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.core.permissions import can_publish_report
from app.core import audit
from app.models.engagement import Engagement
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate, ReportOut
from app.services.pdf import generate_report_pdf

router = APIRouter(tags=["reports"])


@router.get("/engagements/{engagement_id}/reports", response_model=list[ReportOut])
async def list_reports(engagement_id: uuid.UUID, user: CurrentUser, db: DB) -> list[ReportOut]:
    result = await db.execute(
        select(Report).where(Report.engagement_id == engagement_id).order_by(Report.updated_at.desc())
    )
    return [ReportOut.model_validate(r) for r in result.scalars()]


@router.post("/engagements/{engagement_id}/reports", response_model=ReportOut, status_code=201)
async def create_report(
    engagement_id: uuid.UUID,
    body: ReportCreate,
    user: CurrentUser,
    db: DB,
) -> ReportOut:
    eng_result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    if not eng_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Engagement not found")

    r = Report(
        engagement_id=engagement_id,
        author_id=user.id,
        title=body.title,
        blocks=body.blocks,
    )
    db.add(r)
    await audit.log(db, action="report.create", user=user, resource_type="report")
    await db.commit()
    await db.refresh(r)
    return ReportOut.model_validate(r)


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(report_id: uuid.UUID, user: CurrentUser, db: DB) -> ReportOut:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportOut.model_validate(r)


@router.patch("/reports/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: uuid.UUID,
    body: ReportUpdate,
    user: CurrentUser,
    db: DB,
) -> ReportOut:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    await db.commit()
    await db.refresh(r)
    return ReportOut.model_validate(r)


@router.post("/reports/{report_id}/publish", response_model=ReportOut)
async def publish_report(report_id: uuid.UUID, user: CurrentUser, db: DB) -> ReportOut:
    if not can_publish_report(user.role):
        raise HTTPException(status_code=403, detail="Requires lead role or higher")
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    r.status = "published"
    await audit.log(db, action="report.publish", user=user, resource_type="report", resource_id=str(r.id))
    await db.commit()
    await db.refresh(r)
    return ReportOut.model_validate(r)


@router.get("/reports/{report_id}/export/pdf")
async def export_pdf(report_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")

    eng_result = await db.execute(select(Engagement).where(Engagement.id == r.engagement_id))
    engagement = eng_result.scalar_one_or_none()

    await audit.log(db, action="report.export_pdf", user=user, resource_type="report", resource_id=str(r.id))
    await db.commit()

    pdf_bytes = generate_report_pdf(r, engagement)
    safe_title = "".join(c for c in r.title if c.isalnum() or c in " -_")[:60]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )
