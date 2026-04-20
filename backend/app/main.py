from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.database import engine
from app.models import AuditEntry, RefreshToken, User, APIKey, LoginAttempt  # noqa: F401 — register models
from app.routers import auth as auth_router
from app.routers import users as users_router
from app.routers import audit as audit_router
from app.routers import admin as admin_router

logger = structlog.get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("reconstrike_startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    yield
    await engine.dispose()
    logger.info("reconstrike_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── Rate limiting ──────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Middleware (outermost first) ────────────────────────────────────────────
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(auth_router.router, prefix="/api")
    app.include_router(users_router.router, prefix="/api")
    app.include_router(audit_router.router, prefix="/api")
    app.include_router(admin_router.router, prefix="/api")

    # ── Health ─────────────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["meta"])
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    # ── WebSocket stub (Phase 2 will fill this) ─────────────────────────────────
    @app.websocket("/ws/{engagement_id}")
    async def ws_engagement(websocket: WebSocket, engagement_id: str):
        await websocket.accept()
        try:
            while True:
                await websocket.receive_text()
                await websocket.send_json({"type": "ping", "engagement_id": engagement_id})
        except WebSocketDisconnect:
            pass

    return app


app = create_app()
