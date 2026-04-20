"""Celery tasks for ReconStrike workers.

Phase 1: Audit integrity check task.
Phase 2: Scan execution, report generation, notification tasks.
"""
from __future__ import annotations

import structlog

from workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="workers.tasks.audit.run_integrity_check",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_audit_integrity_check(self):
    """Daily audit chain integrity verification task.

    Runs via Celery Beat schedule. Connects to DB and verifies the
    hash chain is intact. Logs result and alerts on failure.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import os

    database_url = os.environ.get("DATABASE_URL", "")

    async def _check():
        from app.core.audit import run_daily_integrity_check
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            result = await run_daily_integrity_check(session)
            await session.commit()
        await engine.dispose()
        return result

    try:
        result = asyncio.run(_check())
        log.info("audit_integrity_task_complete", result=result)
        return result
    except Exception as exc:
        log.error("audit_integrity_task_error", error=str(exc))
        raise self.retry(exc=exc)
