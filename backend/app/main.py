from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.websocket import ws_engagement_handler
from app.database import engine
from app.models import (  # noqa: F401
    AuditEntry,
    APIKey,
    Engagement,
    EngagementRun,
    LoginAttempt,
    RefreshToken,
    ScopeItem,
    User,
)
from app.routers import admin as admin_router
from app.routers import audit as audit_router
from app.routers import auth as auth_router
from app.routers import engagements as engagements_router
from app.routers import modules as modules_router
from app.routers import runs as runs_router
from app.routers import scope as scope_router
from app.routers import users as users_router

logger = structlog.get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("drift.startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    yield
    await engine.dispose()
    logger.info("drift.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # -- Rate limiting --
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # -- Middleware (outermost first) --
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # -- Routers --
    app.include_router(auth_router.router, prefix="/api")
    app.include_router(users_router.router, prefix="/api")
    app.include_router(audit_router.router, prefix="/api")
    app.include_router(admin_router.router, prefix="/api")
    app.include_router(engagements_router.router, prefix="/api")
    app.include_router(scope_router.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    app.include_router(modules_router.router, prefix="/api")

    # -- Health --
    @app.get("/api/health", tags=["meta"])
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    # -- WebSocket: real implementation with JWT auth + Redis pub/sub --
    @app.websocket("/ws/{engagement_id}")
    async def ws_engagement(websocket: WebSocket, engagement_id: str):
        await ws_engagement_handler(websocket, engagement_id)

    return app


app = create_app()
