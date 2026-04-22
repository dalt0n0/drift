"""Schemas for findings and reports."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

class FindingCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str = Field(default="")
    severity: str = Field(default="info", pattern="^(critical|high|medium|low|info)$")
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    cvss_vector: str | None = None
    epss_score: float | None = Field(default=None, ge=0, le=1)
    epss_percentile: float | None = Field(default=None, ge=0, le=1)
    cve_ids: list[str] = Field(default_factory=list)
    cisa_kev: bool = False
    attack_technique_ids: list[str] = Field(default_factory=list)
    affected_target: str = Field(default="", max_length=512)
    evidence: dict[str, Any] = Field(default_factory=dict)
    discovered_by: str = Field(default="", max_length=128)
    notes: str | None = None
    run_id: uuid.UUID | None = None


class FindingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    severity: str | None = Field(default=None, pattern="^(critical|high|medium|low|info)$")
    status: str | None = Field(
        default=None,
        pattern="^(suggested|open|confirmed|false_positive|remediated|accepted_risk)$",
    )
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    cvss_vector: str | None = None
    epss_score: float | None = Field(default=None, ge=0, le=1)
    epss_percentile: float | None = Field(default=None, ge=0, le=1)
    cve_ids: list[str] | None = None
    cisa_kev: bool | None = None
    attack_technique_ids: list[str] | None = None
    affected_target: str | None = Field(default=None, max_length=512)
    evidence: dict[str, Any] | None = None
    notes: str | None = None


class FindingResponse(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    run_id: uuid.UUID | None
    title: str
    description: str
    severity: str
    cvss_score: float | None
    cvss_vector: str | None
    epss_score: float | None
    epss_percentile: float | None
    cve_ids: list[str]
    cisa_kev: bool
    attack_technique_ids: list[str]
    affected_target: str
    evidence: dict[str, Any]
    status: str
    discovered_by: str
    deduplicated_from: list[uuid.UUID]
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FindingListResponse(BaseModel):
    findings: list[FindingResponse]
    total: int
    page: int
    pages: int
    by_severity: dict[str, int]


# ---------------------------------------------------------------------------
# CVE enrichment
# ---------------------------------------------------------------------------

class CVEEnrichRequest(BaseModel):
    cve_ids: list[str] = Field(..., min_length=1, max_length=20)


class CVEEnrichResponse(BaseModel):
    results: dict[str, dict]


# ---------------------------------------------------------------------------
# CVSS calculation
# ---------------------------------------------------------------------------

class CVSSCalculateRequest(BaseModel):
    vector: str = Field(..., description="CVSS 3.1 vector string")


class CVSSCalculateResponse(BaseModel):
    score: float
    severity: str
    vector: str
    iss: float
    impact: float
    exploitability: float


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportRequest(BaseModel):
    format: str = Field(
        default="pdf",
        pattern="^(pdf|html|json|csv|sarif)$",
        description="Output format",
    )
    report_type: str = Field(
        default="technical",
        pattern="^(executive|technical|client)$",
        description="Report type",
    )
