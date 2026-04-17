import uuid
from datetime import datetime, date
from pydantic import BaseModel


class RetestCreate(BaseModel):
    fix_claim: str | None = None
    fix_claim_by: str | None = None
    notes: str = ""
    evidence_requested: bool = False
    repro_script: str | None = None
    due_by: date | None = None


class RetestUpdate(BaseModel):
    status: str | None = None
    fix_claim: str | None = None
    fix_claim_by: str | None = None
    notes: str | None = None
    evidence_requested: bool | None = None
    repro_script: str | None = None
    due_by: date | None = None


class RetestHistoryOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    status: str
    notes: str
    tester_id: uuid.UUID | None
    created_at: datetime


class RetestOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    finding_id: uuid.UUID
    tester_id: uuid.UUID | None
    status: str
    fix_claim: str | None
    fix_claim_by: str | None
    notes: str
    evidence_requested: bool
    repro_script: str | None
    due_by: date | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    history: list[RetestHistoryOut] = []
