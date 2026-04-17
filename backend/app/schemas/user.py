import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    role: str = "tester"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9_\-\.]{3,64}$", v):
            raise ValueError("Username: 3-64 chars, alphanumeric/.-_ only")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        allowed = {"admin", "lead", "senior", "tester", "junior"}
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(sorted(allowed))}")
        return v


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain lowercase")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain a special character")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    avatar_color: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    mfa_enabled: bool
    avatar_color: str
    last_login: datetime | None
    created_at: datetime


class APIKeyCreate(BaseModel):
    name: str
    scopes: list[str] = []
    expires_days: int | None = None


class APIKeyOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used: datetime | None
    expires_at: datetime | None
    created_at: datetime


class APIKeyCreated(APIKeyOut):
    """Only returned on creation — includes the raw key."""
    raw_key: str
