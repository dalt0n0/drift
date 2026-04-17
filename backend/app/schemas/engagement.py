import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator


class EngagementCreate(BaseModel):
    code: str
    name: str
    client: str
    type: str
    start_date: date
    end_date: date
    scope_in: str = ""
    scope_out: str = ""
    rules_of_engagement: str = ""
    lead_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = []

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        allowed = {"External Web App", "Internal Network", "Mobile App", "API", "Cloud", "Physical"}
        if v not in allowed:
            raise ValueError(f"Invalid engagement type")
        return v

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be after start_date")
        return v


class EngagementUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    type: str | None = None
    status: str | None = None
    phase: str | None = None
    progress: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    scope_in: str | None = None
    scope_out: str | None = None
    rules_of_engagement: str | None = None
    lead_id: uuid.UUID | None = None

    @field_validator("progress")
    @classmethod
    def progress_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Progress must be 0.0–1.0")
        return v


class MemberOut(BaseModel):
    model_config = {"from_attributes": True}
    user_id: uuid.UUID
    role: str
    username: str = ""
    full_name: str = ""


class FindingSummary(BaseModel):
    crit: int = 0
    high: int = 0
    med: int = 0
    low: int = 0
    info: int = 0


class EngagementOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
    client: str
    type: str
    status: str
    phase: str
    progress: float
    start_date: date
    end_date: date
    scope_in: str
    scope_out: str
    rules_of_engagement: str
    lead_id: uuid.UUID | None
    target_count: int = 0
    findings: FindingSummary = FindingSummary()
    team: list[str] = []
    created_at: datetime
    updated_at: datetime
