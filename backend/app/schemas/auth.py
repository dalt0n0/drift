from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    role: str = "tester"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        allowed = {"admin", "lead", "tester", "viewer", "client_readonly"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MFASetupResponse(BaseModel):
    totp_uri: str
    secret: str  # shown once for manual entry


class MFAConfirmRequest(BaseModel):
    totp_code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v


class CreateAPIKeyRequest(BaseModel):
    name: str
    expires_days: int | None = None


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    prefix: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    """Returned once on creation; raw_key not stored."""
    raw_key: str
