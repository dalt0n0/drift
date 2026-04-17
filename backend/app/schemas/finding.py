import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_STATUSES = {"open", "triaged", "accepted-risk", "resolved", "false_positive"}


class ReferenceItem(BaseModel):
    label: str
    url: str


class FindingCreate(BaseModel):
    title: str
    severity: str
    cvss: float = 0.0
    status: str = "open"
    target_id: uuid.UUID | None = None
    category: str | None = None
    cwe: str | None = None
    tags: list[str] = []
    confidence: str = "confirmed"
    summary: str = ""
    description: str = ""
    steps: list[str] = []
    payload: str = ""
    impact: str = ""
    recommendation: str = ""
    references: list[ReferenceItem] = []
    assignee_id: uuid.UUID | None = None

    @field_validator("severity")
    @classmethod
    def severity_valid(cls, v: str) -> str:
        if v not in VALID_SEVERITIES:
            raise ValueError(f"Severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v

    @field_validator("cvss")
    @classmethod
    def cvss_range(cls, v: float) -> float:
        if not (0.0 <= v <= 10.0):
            raise ValueError("CVSS must be 0.0–10.0")
        return round(v, 1)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title required")
        if len(v) > 512:
            raise ValueError("Title too long")
        return v.strip()


class FindingUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    cvss: float | None = None
    status: str | None = None
    target_id: uuid.UUID | None = None
    category: str | None = None
    cwe: str | None = None
    tags: list[str] | None = None
    confidence: str | None = None
    summary: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    payload: str | None = None
    impact: str | None = None
    recommendation: str | None = None
    references: list[ReferenceItem] | None = None
    assignee_id: uuid.UUID | None = None


class EvidenceOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    kind: str
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: uuid.UUID | None
    created_at: datetime


class CommentCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment cannot be empty")
        if len(v) > 10000:
            raise ValueError("Comment too long")
        return v.strip()


class CommentOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    finding_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    created_at: datetime
    updated_at: datetime


class FindingOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    engagement_id: uuid.UUID
    target_id: uuid.UUID | None
    target_host: str | None = None
    title: str
    severity: str
    cvss: float
    status: str
    category: str | None
    cwe: str | None
    tags: list[str]
    confidence: str
    summary: str
    description: str
    steps: list[str]
    payload: str
    impact: str
    recommendation: str
    references: list[dict]
    assignee_id: uuid.UUID | None
    reporter_id: uuid.UUID | None
    evidence_count: int = 0
    comment_count: int = 0
    retest_status: str | None = None
    created_at: datetime
    updated_at: datetime
