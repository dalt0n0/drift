"""Orchestrator service: manages engagement runs and plugin execution."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import Engagement, EngagementStatus
from app.models.run import EngagementRun, RunStatus
from app.plugins.manifest import PluginManifest, PluginRegistry, registry

logger = structlog.get_logger(__name__)


class AuthorizationNotConfirmedError(Exception):
    """Raised when an intrusive plugin is attempted without authorization confirmation."""


class OrchestratorService:
    """Manages the lifecycle of engagement runs."""

    def __init__(self, db: AsyncSession, plugin_registry: PluginRegistry | None = None):
        self.db = db
        self.registry = plugin_registry or registry

    async def _get_engagement(self, engagement_id: uuid.UUID) -> Engagement:
        result = await self.db.execute(
            select(Engagement).where(Engagement.id == engagement_id)
        )
        engagement = result.scalar_one_or_none()
        if not engagement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "Engagement not found.",
                },
            )
        return engagement

    async def _get_run(self, run_id: uuid.UUID) -> EngagementRun:
        result = await self.db.execute(
            select(EngagementRun).where(EngagementRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "Run not found.",
                },
            )
        return run

    def _verify_authorization_for_intrusive(
        self, engagement: Engagement, plugins: list[str]
    ) -> None:
        """Verify authorization is confirmed before running any intrusive plugin."""
        for plugin_name in plugins:
            try:
                manifest = self.registry.get(plugin_name)
            except Exception:
                continue
            if manifest.is_intrusive and not engagement.authorization_confirmed:
                raise AuthorizationNotConfirmedError(
                    f"Cannot run intrusive plugin '{plugin_name}' without "
                    f"confirmed authorization on engagement {engagement.id}"
                )

    async def create_run(
        self,
        engagement_id: uuid.UUID,
        triggered_by: uuid.UUID,
        plugin_names: list[str] | None = None,
        safe_mode: bool = False,
        params: dict | None = None,
    ) -> EngagementRun:
        """Create a new engagement run.

        Args:
            engagement_id: The engagement to run against.
            triggered_by: User ID that triggered the run.
            plugin_names: Specific plugins to run. None = all registered.
            safe_mode: If True, only run non-intrusive plugins.
        """
        engagement = await self._get_engagement(engagement_id)

        if engagement.status not in (
            EngagementStatus.active.value,
            EngagementStatus.draft.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "about:blank",
                    "title": "Bad Request",
                    "status": 400,
                    "detail": f"Engagement is '{engagement.status}', must be 'active' or 'draft'.",
                },
            )

        # Resolve plugin execution plan
        if plugin_names:
            plan = self.registry.get_execution_plan(plugin_names, safe_mode=safe_mode)
        else:
            all_names = [p.name for p in self.registry.list_all()]
            plan = self.registry.get_execution_plan(all_names, safe_mode=safe_mode)

        plan_names = [p.name for p in plan]

        # Verify authorization for intrusive plugins
        if not safe_mode:
            self._verify_authorization_for_intrusive(engagement, plan_names)

        pipeline_config = {
            "plugins": plan_names,
            "safe_mode": safe_mode,
            "params": params or {},
            "plugin_configs": {
                p.name: {
                    "timeout_seconds": p.timeout_seconds,
                    "rate_limit": p.rate_limit,
                    "is_intrusive": p.is_intrusive,
                }
                for p in plan
            },
        }

        run = EngagementRun(
            engagement_id=engagement_id,
            status=RunStatus.pending.value,
            pipeline_config=pipeline_config,
            checkpoint={"completed_plugins": [], "current_plugin": None},
            triggered_by=triggered_by,
        )
        self.db.add(run)
        await self.db.flush()

        logger.info(
            "orchestrator.run_created",
            run_id=str(run.id),
            engagement_id=str(engagement_id),
            plugins=plan_names,
            safe_mode=safe_mode,
        )

        return run

    async def resume_run(self, run_id: uuid.UUID) -> EngagementRun:
        """Resume a paused or failed run from its last checkpoint."""
        run = await self._get_run(run_id)

        if run.status not in (RunStatus.paused.value, RunStatus.failed.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "about:blank",
                    "title": "Bad Request",
                    "status": 400,
                    "detail": f"Run status is '{run.status}', can only resume 'paused' or 'failed' runs.",
                },
            )

        # Verify engagement authorization still holds
        engagement = await self._get_engagement(run.engagement_id)
        if run.pipeline_config and not run.pipeline_config.get("safe_mode", False):
            remaining_plugins = self._get_remaining_plugins(run)
            self._verify_authorization_for_intrusive(engagement, remaining_plugins)

        run.status = RunStatus.running.value
        run.updated_at = datetime.now(timezone.utc)
        run.error_message = None

        logger.info(
            "orchestrator.run_resumed",
            run_id=str(run.id),
            checkpoint=run.checkpoint,
        )

        return run

    async def cancel_run(self, run_id: uuid.UUID) -> EngagementRun:
        """Cancel a pending or running run."""
        run = await self._get_run(run_id)

        if run.status in (RunStatus.completed.value, RunStatus.cancelled.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "type": "about:blank",
                    "title": "Bad Request",
                    "status": 400,
                    "detail": f"Run is already '{run.status}'.",
                },
            )

        run.status = RunStatus.cancelled.value
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

        logger.info("orchestrator.run_cancelled", run_id=str(run.id))

        return run

    async def dry_run(
        self,
        engagement_id: uuid.UUID,
        plugin_names: list[str] | None = None,
        safe_mode: bool = False,
    ) -> dict:
        """Preview execution plan without creating a run.

        Returns the execution plan details without persisting anything.
        """
        engagement = await self._get_engagement(engagement_id)

        if plugin_names:
            plan = self.registry.get_execution_plan(plugin_names, safe_mode=safe_mode)
        else:
            all_names = [p.name for p in self.registry.list_all()]
            plan = self.registry.get_execution_plan(all_names, safe_mode=safe_mode)

        # Check authorization issues
        auth_issues = []
        for p in plan:
            if p.is_intrusive and not engagement.authorization_confirmed:
                auth_issues.append(
                    f"Plugin '{p.name}' is intrusive but authorization is not confirmed"
                )

        return {
            "engagement_id": str(engagement_id),
            "safe_mode": safe_mode,
            "plugins": [
                {
                    "name": p.name,
                    "category": p.category,
                    "is_intrusive": p.is_intrusive,
                    "timeout_seconds": p.timeout_seconds,
                    "dependencies": p.dependencies,
                }
                for p in plan
            ],
            "total_plugins": len(plan),
            "authorization_confirmed": engagement.authorization_confirmed,
            "authorization_issues": auth_issues,
        }

    async def safe_mode_run(
        self,
        engagement_id: uuid.UUID,
        triggered_by: uuid.UUID,
    ) -> EngagementRun:
        """Create a safe-mode run (non-intrusive plugins only)."""
        return await self.create_run(
            engagement_id=engagement_id,
            triggered_by=triggered_by,
            safe_mode=True,
        )

    def _get_remaining_plugins(self, run: EngagementRun) -> list[str]:
        """Get plugins that haven't completed yet from checkpoint."""
        if not run.pipeline_config or not run.checkpoint:
            return []
        all_plugins = run.pipeline_config.get("plugins", [])
        completed = set(run.checkpoint.get("completed_plugins", []))
        return [p for p in all_plugins if p not in completed]
