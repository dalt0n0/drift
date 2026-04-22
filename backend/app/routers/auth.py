from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit as audit_svc
from app.core.deps import CurrentUser, DB
from app.core.security import (
    create_access_token,
    generate_api_key,
    generate_refresh_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
    verify_totp,
)
from app.models.session import RefreshToken
from app.models.user import APIKey, LoginAttempt, User
from app.schemas.auth import (
    APIKeyCreatedResponse,
    APIKeyResponse,
    ChangePasswordRequest,
    CreateAPIKeyRequest,
    LoginRequest,
    MFAConfirmRequest,
    MFASetupResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

_MAX_FAILURES = 5
_LOCKOUT_MINUTES = 15
_REFRESH_COOKIE = "drift_refresh"


def _problem(status_code: int, title: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"type": "about:blank", "title": title, "status": status_code, "detail": detail},
    )


async def _check_lockout(db: AsyncSession, username: str, ip: str) -> None:
    since = datetime.now(timezone.utc) - timedelta(minutes=_LOCKOUT_MINUTES)
    result = await db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.username == username,
            LoginAttempt.success == False,
            LoginAttempt.attempted_at >= since,
        )
    )
    failures = result.scalar_one()
    if failures >= _MAX_FAILURES:
        raise _problem(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Account Locked",
            "Too many failed attempts. Try again later.",
        )


async def _record_attempt(db: AsyncSession, username: str, ip: str, success: bool) -> None:
    attempt = LoginAttempt(username=username, ip_address=ip, success=success)
    db.add(attempt)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: DB):
    existing = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise _problem(409, "Conflict", "Username or email already registered")

    user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    await audit_svc.log(
        db, action="user.register", actor_id=user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="user", resource_id=str(user.id),
        after_state={"username": user.username, "role": user.role},
        request_id=request.headers.get("x-request-id"),
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DB):
    ip = audit_svc.get_client_ip(request)
    ua = request.headers.get("user-agent")

    await _check_lockout(db, body.username, ip)

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    _invalid = _problem(401, "Unauthorized", "Invalid credentials")

    if user is None or not user.is_active:
        await _record_attempt(db, body.username, ip, False)
        await audit_svc.log(
            db, action="auth.login.failed", actor_ip=ip, user_agent=ua,
            resource_type="user", resource_id=body.username, outcome="failure",
            request_id=request.headers.get("x-request-id"),
        )
        raise _invalid

    if not verify_password(body.password, user.hashed_password):
        await _record_attempt(db, body.username, ip, False)
        await audit_svc.log(
            db, action="auth.login.failed", actor_id=user.id, actor_ip=ip, user_agent=ua,
            resource_type="user", resource_id=str(user.id), outcome="failure",
            request_id=request.headers.get("x-request-id"),
        )
        raise _invalid

    if user.mfa_enabled:
        if not body.totp_code:
            response.headers["X-MFA-Required"] = "true"
            raise _problem(401, "MFA Required", "Provide totp_code to complete login")
        from app.core.crypto import decrypt
        try:
            secret = decrypt(user.mfa_secret)
        except Exception:
            raise _problem(500, "Internal Error", "MFA configuration error")
        if not verify_totp(secret, body.totp_code):
            await _record_attempt(db, body.username, ip, False)
            await audit_svc.log(
                db, action="auth.mfa.failed", actor_id=user.id, actor_ip=ip, user_agent=ua,
                resource_type="user", resource_id=str(user.id), outcome="failure",
                request_id=request.headers.get("x-request-id"),
            )
            raise _problem(401, "Unauthorized", "Invalid MFA code")

    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)

    access_token, expires_in = create_access_token({"sub": str(user.id), "role": user.role})
    raw_refresh, refresh_hash = generate_refresh_token()

    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        device_info=ua,
        ip_address=ip,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    user.last_login_at = datetime.now(timezone.utc)
    await _record_attempt(db, body.username, ip, True)

    await audit_svc.log(
        db, action="auth.login.success", actor_id=user.id, actor_ip=ip, user_agent=ua,
        resource_type="user", resource_id=str(user.id),
        request_id=request.headers.get("x-request-id"),
        session_id=str(rt.id),
    )

    response.set_cookie(
        key=_REFRESH_COOKIE, value=raw_refresh, httponly=True,
        secure=settings.is_production, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request, response: Response, db: DB,
    drift_refresh: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    if not drift_refresh:
        raise _problem(401, "Unauthorized", "No refresh token")

    token_hash = hash_token(drift_refresh)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False,
        )
    )
    rt = result.scalar_one_or_none()
    if rt is None or rt.expires_at < datetime.now(timezone.utc):
        raise _problem(401, "Unauthorized", "Invalid or expired refresh token")

    rt.is_revoked = True
    rt.revoked_at = datetime.now(timezone.utc)

    result = await db.execute(select(User).where(User.id == rt.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _problem(401, "Unauthorized", "User not found")

    access_token, expires_in = create_access_token({"sub": str(user.id), "role": user.role})
    raw_refresh, refresh_hash = generate_refresh_token()
    new_rt = RefreshToken(
        user_id=user.id, token_hash=refresh_hash, device_info=rt.device_info,
        ip_address=audit_svc.get_client_ip(request),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)

    await audit_svc.log(
        db, action="auth.token.refreshed", actor_id=user.id,
        actor_ip=audit_svc.get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        resource_type="user", resource_id=str(user.id),
        request_id=request.headers.get("x-request-id"), session_id=str(new_rt.id),
    )

    response.set_cookie(
        key=_REFRESH_COOKIE, value=raw_refresh, httponly=True,
        secure=settings.is_production, samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/api/auth",
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, db: DB, current_user: CurrentUser,
    drift_refresh: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    if drift_refresh:
        token_hash = hash_token(drift_refresh)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        rt = result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
            rt.revoked_at = datetime.now(timezone.utc)
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/auth")
    await audit_svc.log(
        db, action="auth.logout", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(current_user.id),
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(request: Request, response: Response, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False,
        )
    )
    tokens = result.scalars().all()
    now = datetime.now(timezone.utc)
    for t in tokens:
        t.is_revoked = True
        t.revoked_at = now
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/auth")
    await audit_svc.log(
        db, action="auth.logout_all", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(current_user.id),
        request_id=request.headers.get("x-request-id"),
        after_state={"revoked_count": len(tokens)},
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(current_user: CurrentUser, db: DB):
    from app.core.crypto import encrypt
    secret = generate_totp_secret()
    totp_uri = get_totp_uri(secret, current_user.username)
    current_user.mfa_secret = encrypt(secret)
    return MFASetupResponse(totp_uri=totp_uri, secret=secret)


@router.post("/mfa/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_confirm(body: MFAConfirmRequest, request: Request, current_user: CurrentUser, db: DB):
    from app.core.crypto import decrypt
    if not current_user.mfa_secret:
        raise _problem(400, "Bad Request", "Call /mfa/setup first")
    try:
        secret = decrypt(current_user.mfa_secret)
    except Exception:
        raise _problem(500, "Internal Error", "MFA secret decryption failed")
    if not verify_totp(secret, body.totp_code):
        raise _problem(400, "Bad Request", "Invalid TOTP code")
    current_user.mfa_enabled = True
    await audit_svc.log(
        db, action="auth.mfa.enabled", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(current_user.id),
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(body: MFAConfirmRequest, request: Request, current_user: CurrentUser, db: DB):
    from app.core.crypto import decrypt
    if not current_user.mfa_enabled:
        raise _problem(400, "Bad Request", "MFA is not enabled")
    try:
        secret = decrypt(current_user.mfa_secret)
    except Exception:
        raise _problem(500, "Internal Error", "MFA secret decryption failed")
    if not verify_totp(secret, body.totp_code):
        raise _problem(401, "Unauthorized", "Invalid TOTP code")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await audit_svc.log(
        db, action="auth.mfa.disabled", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(current_user.id),
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, request: Request,
    current_user: CurrentUser, db: DB, response: Response,
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise _problem(401, "Unauthorized", "Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    current_user.must_change_password = False
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False,
        )
    )
    now = datetime.now(timezone.utc)
    for t in result.scalars().all():
        t.is_revoked = True
        t.revoked_at = now
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/auth")
    await audit_svc.log(
        db, action="auth.password_changed", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="user", resource_id=str(current_user.id),
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(body: CreateAPIKeyRequest, request: Request, current_user: CurrentUser, db: DB):
    raw, key_hash, prefix = generate_api_key()
    expires_at = None
    if body.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)
    api_key = APIKey(
        user_id=current_user.id, prefix=prefix, key_hash=key_hash,
        name=body.name, expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    await audit_svc.log(
        db, action="auth.api_key.created", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="api_key", resource_id=str(api_key.id),
        after_state={"name": api_key.name, "prefix": prefix},
        request_id=request.headers.get("x-request-id"),
    )
    return APIKeyCreatedResponse(
        id=api_key.id, prefix=prefix, name=api_key.name,
        created_at=api_key.created_at, expires_at=expires_at,
        last_used_at=None, is_active=True, raw_key=raw,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id, APIKey.is_active == True)
    )
    return result.scalars().all()


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, request: Request, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise _problem(404, "Not Found", "API key not found")
    key.is_active = False
    await audit_svc.log(
        db, action="auth.api_key.revoked", actor_id=current_user.id,
        actor_ip=audit_svc.get_client_ip(request),
        resource_type="api_key", resource_id=str(key.id),
        request_id=request.headers.get("x-request-id"),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user
