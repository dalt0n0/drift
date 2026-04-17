"""
Drift — self-hosted pentest suite
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis_async

from app.config import settings
from app.database import engine
from app.models import *  # noqa: F401 — registers all models with Base
from app.database import Base

from app.routers import (
    auth, engagements, targets, findings, retest,
    vault, reports, notifications, integrations,
    team, activity, settings as settings_router,
)

logger = logging.getLogger("drift")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (use Alembic in production)
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


# Rate limiter (backed by Redis)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["200/minute"],
)

app = FastAPI(
    title="Drift — Pentest Suite API",
    version="1.8.2",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Security headers middleware ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-MFA-Required"],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)


# ── Validation error handler ───────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": None},
    )


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": "1.8.2"}


# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api"

app.include_router(auth.router,           prefix=PREFIX)
app.include_router(engagements.router,    prefix=PREFIX)
app.include_router(targets.router,        prefix=PREFIX)
app.include_router(findings.router,       prefix=PREFIX)
app.include_router(retest.router,         prefix=PREFIX)
app.include_router(vault.router,          prefix=PREFIX)
app.include_router(reports.router,        prefix=PREFIX)
app.include_router(notifications.router,  prefix=PREFIX)
app.include_router(integrations.router,   prefix=PREFIX)
app.include_router(team.router,           prefix=PREFIX)
app.include_router(activity.router,       prefix=PREFIX)
app.include_router(settings_router.router, prefix=PREFIX)
