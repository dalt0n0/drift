import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


VALID_TYPES = {"password", "token", "apikey", "key", "file"}


class VaultItemCreate(BaseModel):
    name: str
    type: str
    username: str | None = None
    secret: str  # plaintext — encrypted before storage
    notes: str | None = None
    engagement_id: uuid.UUID | None = None
    target_id: uuid.UUID | None = None
    tags: list[str] = []
    sensitive: bool = True
    expires_at: datetime | None = None

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Type must be one of: {', '.join(sorted(VALID_TYPES))}")
        return v

    @field_validator("secret")
    @classmethod
    def secret_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Secret cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name required")
        if len(v) > 256:
            raise ValueError("Name too long")
        return v.strip()


class VaultItemUpdate(BaseModel):
    name: str | None = None
    username: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    sensitive: bool | None = None
    expires_at: datetime | None = None


class VaultItemOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    name: str
    type: str
    username: str | None = None  # decrypted for display
    engagement_id: uuid.UUID | None
    target_id: uuid.UUID | None
    target_host: str | None = None
    owner_id: uuid.UUID | None
    tags: list[str]
    sensitive: bool
    expires_at: datetime | None
    last_accessed: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VaultItemSecret(BaseModel):
    """Returned only on explicit reveal — logged in access_log."""
    secret: str
    username: str | None


class VaultAccessLogOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    ip_address: str | None
    created_at: datetime
