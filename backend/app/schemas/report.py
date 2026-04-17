import uuid
from datetime import datetime
from pydantic import BaseModel


class ReportCreate(BaseModel):
    title: str
    blocks: list[dict] = []


class ReportUpdate(BaseModel):
    title: str | None = None
    version: str | None = None
    status: str | None = None
    blocks: list[dict] | None = None


class ReportOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    engagement_id: uuid.UUID
    author_id: uuid.UUID | None
    title: str
    version: str
    status: str
    blocks: list[dict]
    created_at: datetime
    updated_at: datetime
