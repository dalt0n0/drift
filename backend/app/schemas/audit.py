from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    actor_id: uuid.UUID | None
    actor_ip: str | None
    user_agent: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    before_state: dict | None
    after_state: dict | None
    request_id: str | None
    session_id: str | None
    outcome: str
    chain_hash: str

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int
    page: int
    page_size: int


class ChainVerifyResponse(BaseModel):
    valid: bool
    message: str
    entries_checked: int
