"""
Auth endpoints: login, logout, refresh, MFA setup/verify, password change.
Rate-limited: 10 attempts per 15 min per IP on login.
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import CurrentUser, DB
from app.core.security import (
    verify_password, hash_password, create_access_token,
    generate_refresh_token, hash_refresh_token,
    generate_totp_secret, verify_totp,
    get_totp_provisioning_uri, get_totp_qr_base64,
    password_needs_rehash,
)
from app.core import audit
from app.models.user import User, RefreshToken, LoginAttempt
from app.schemas.auth import (
    LoginRequest, TokenResponse, MFASetupResponse,
    MFAVerifyRequest, ChangePasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Brute-force settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DB,
) -> TokenResponse:
    client_ip = audit.get_client_ip(request)

    # Check lockout
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)
    fail_count_result = await db.execute(
        select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.username == body.username,
            LoginAttempt.ip_address == client_ip,
            LoginAttempt.success == False,
            LoginAttempt.created_at >= cutoff,
        )
    )
    fail_count = fail_count_result.scalar_one()
    if fail_count >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again in {LOCKOUT_MINUTES} minutes.",
        )

    # Fetch user
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    async def _record_failure():
        db.add(LoginAttempt(username=body.username, ip_address=client_ip, success=False))
        await audit.log(db, action="auth.login_failed", ip_address=client_ip,
                        request_data={"username": body.username})
        await db.commit()

    if user is None or not verify_password(body.password, user.hashed_password):
        await _record_failure()
        # Same error regardless of which check failed (no username enumeration)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        await _record_failure()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # MFA
    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code required",
                headers={"X-MFA-Required": "true"},
            )
        if not verify_totp(user.mfa_secret, body.mfa_code):
            await _record_failure()
            await audit.log(db, action="auth.mfa_failed", user=user, ip_address=client_ip)
            await db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    # Re-hash if Argon2 params changed
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)

    # Issue tokens
    access_token, expires_in = create_access_token(str(user.id), user.username, user.role)
    raw_refresh, hashed_refresh = generate_refresh_token()

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("User-Agent", "")[:512],
        ip_address=client_ip,
    ))

    user.last_login = datetime.now(tz=timezone.utc)
    db.add(LoginAttempt(username=body.username, ip_address=client_ip, success=True))
    await audit.log(db, action="auth.login", user=user, ip_address=client_ip, response_status=200)
    await db.commit()

    # Set refresh token in httpOnly secure cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: DB,
) -> TokenResponse:
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if not stored or stored.revoked or stored.expires_at < datetime.now(tz=timezone.utc):
        # Revoke all tokens for this user if token is reused (theft detection)
        if stored and not stored.revoked:
            await db.execute(
                select(RefreshToken).where(RefreshToken.user_id == stored.user_id)
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    # Rotate refresh token
    stored.revoked = True
    raw_new, hashed_new = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_new,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("User-Agent", "")[:512],
        ip_address=audit.get_client_ip(request),
    ))

    access_token, expires_in = create_access_token(str(user.id), user.username, user.role)
    await db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_new,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: CurrentUser,
    db: DB,
) -> None:
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()
        if stored:
            stored.revoked = True

    await audit.log(db, action="auth.logout", user=user, ip_address=audit.get_client_ip(request))
    await db.commit()

    response.delete_cookie("refresh_token", path="/api/auth")


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "mfa_enabled": user.mfa_enabled,
        "avatar_color": user.avatar_color,
        "last_login": user.last_login,
    }


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(user: CurrentUser, db: DB) -> MFASetupResponse:
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA already enabled")
    secret = generate_totp_secret()
    user.mfa_secret = secret
    await db.commit()
    uri = get_totp_provisioning_uri(secret, user.username)
    return MFASetupResponse(provisioning_uri=uri, secret=secret)


@router.post("/mfa/confirm", status_code=204)
async def mfa_confirm(body: MFAVerifyRequest, user: CurrentUser, db: DB) -> None:
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Call /mfa/setup first")
    if not verify_totp(user.mfa_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    user.mfa_enabled = True
    await db.commit()


@router.post("/mfa/disable", status_code=204)
async def mfa_disable(body: MFAVerifyRequest, user: CurrentUser, db: DB) -> None:
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    if not verify_totp(user.mfa_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    user.mfa_enabled = False
    user.mfa_secret = None
    await db.commit()


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    db: DB,
) -> None:
    if not verify_password(body.current_password, user.hashed_password):
        await audit.log(db, action="auth.change_password_failed", user=user,
                        ip_address=audit.get_client_ip(request))
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user.hashed_password = hash_password(body.new_password)
    # Revoke all refresh tokens on password change
    result = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    for token in result.scalars():
        token.revoked = True
    await audit.log(db, action="auth.password_changed", user=user,
                    ip_address=audit.get_client_ip(request))
    await db.commit()
