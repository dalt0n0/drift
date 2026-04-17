from pydantic import BaseModel, EmailStr, field_validator
import re


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: str | None = None

    @field_validator("username")
    @classmethod
    def username_safe(cls, v: str) -> str:
        if len(v) > 64:
            raise ValueError("Username too long")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Password required")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class MFASetupResponse(BaseModel):
    provisioning_uri: str
    secret: str  # shown once


class MFAVerifyRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def code_digits(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{6}$", v):
            raise ValueError("MFA code must be 6 digits")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain a special character")
        return v
