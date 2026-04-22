"""Pydantic schemas for engagements, scope items, and runs."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Engagement schemas
# ---------------------------------------------------------------------------

class EngagementCreateRequest(BaseModel):
    title: str
    client_name: str
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class EngagementUpdateRequest(BaseModel):
    title: str | None = None
    client_name: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"draft", "active", "paused", "completed", "archived"}
            if v not in allowed:
                raise ValueError(f"Status must be one of {allowed}")
        return v


class EngagementResponse(BaseModel):
    id: uuid.UUID
    title: str
    client_name: str
    description: str | None
    status: str
    start_date: datetime | None
    end_date: datetime | None
    owner_id: uuid.UUID
    authorization_letter_path: str | None
    authorization_hash: str | None
    authorization_confirmed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EngagementListResponse(BaseModel):
    items: list[EngagementResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Scope schemas
# ---------------------------------------------------------------------------

class ScopeItemCreateRequest(BaseModel):
    type: str
    value: str
    is_excluded: bool = False
    notes: str | None = None

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        allowed = {"cidr", "domain", "url", "ip", "wildcard"}
        if v not in allowed:
            raise ValueError(f"Scope type must be one of {allowed}")
        return v

    @field_validator("value")
    @classmethod
    def value_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Value cannot be empty")
        return v.strip()


class ScopeItemResponse(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    type: str
    value: str
    is_excluded: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScopeItemBatchRequest(BaseModel):
    items: list[ScopeItemCreateRequest]


# ---------------------------------------------------------------------------
# Run schemas
# ---------------------------------------------------------------------------

class RunCreateRequest(BaseModel):
    plugin_names: list[str] | None = None
    safe_mode: bool = False
    params: dict | None = None  # Per-run parameters (target, flags, etc.)


class RunResponse(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    status: str
    pipeline_config: dict | None
    checkpoint: dict | None
    triggered_by: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    error_message: str | None

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DryRunResponse(BaseModel):
    engagement_id: str
    safe_mode: bool
    plugins: list[dict]
    total_plugins: int
    authorization_confirmed: bool
    authorization_issues: list[str]


# ---------------------------------------------------------------------------
# Module (plugin) schemas
# ---------------------------------------------------------------------------

class ModuleResponse(BaseModel):
    name: str
    version: str
    category: str
    is_intrusive: bool
    safe_mode_allowed: bool
    timeout_seconds: int
    rate_limit: int
    inputs: list[str]
    outputs: list[str]
    dependencies: list[str]
