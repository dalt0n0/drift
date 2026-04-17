import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
import ipaddress


class TargetCreate(BaseModel):
    host: str
    ip: str | None = None
    type: str = "Web"
    state: str = "active"
    tags: list[str] = []
    ports: list[int] = []
    tech: list[str] = []
    owner: str | None = None
    notes: str | None = None

    @field_validator("host")
    @classmethod
    def host_safe(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 253:
            raise ValueError("Host too long")
        return v

    @field_validator("ip")
    @classmethod
    def ip_valid(cls, v: str | None) -> str | None:
        if v:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError("Invalid IP address")
        return v

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        allowed = {"Web", "API", "Service", "CDN", "Mobile", "Network", "Cloud"}
        if v not in allowed:
            raise ValueError("Invalid target type")
        return v

    @field_validator("ports")
    @classmethod
    def ports_valid(cls, v: list[int]) -> list[int]:
        for p in v:
            if not 1 <= p <= 65535:
                raise ValueError(f"Invalid port: {p}")
        return v


class TargetUpdate(BaseModel):
    host: str | None = None
    ip: str | None = None
    type: str | None = None
    state: str | None = None
    tags: list[str] | None = None
    ports: list[int] | None = None
    tech: list[str] | None = None
    owner: str | None = None
    notes: str | None = None


class TargetOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    engagement_id: uuid.UUID
    host: str
    ip: str | None
    type: str
    state: str
    tags: list[str]
    ports: list[int]
    tech: list[str]
    owner: str | None
    notes: str | None
    finding_count: int = 0
    last_scan: datetime | None
    created_at: datetime
    updated_at: datetime
