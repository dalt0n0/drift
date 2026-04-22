"""Run executor: executes an EngagementRun's plugin pipeline as a background task."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.database import AsyncSessionLocal
from app.models.run import EngagementRun, RunStatus

logger = structlog.get_logger(__name__)


async def execute_run(run_id: uuid.UUID) -> None:
    """Background task: execute all plugins for a pending run.

    Opens its own DB session so it can safely run outside the request lifecycle.
    """
    async with AsyncSessionLocal() as db:
        try:
            run = await db.get(EngagementRun, run_id)
            if not run:
                logger.error("run_executor.run_not_found", run_id=str(run_id))
                return

            if run.status != RunStatus.pending.value:
                logger.warning(
                    "run_executor.skip_non_pending",
                    run_id=str(run_id),
                    status=run.status,
                )
                return

            # Transition to running
            run.status = RunStatus.running.value
            run.started_at = datetime.now(timezone.utc)
            run.checkpoint = {
                "completed_plugins": [],
                "current_plugin": None,
                "results": {},
            }
            await db.commit()
            await db.refresh(run)

            pipeline_cfg = run.pipeline_config or {}
            plugin_names: list[str] = pipeline_cfg.get("plugins", [])
            params: dict = pipeline_cfg.get("params", {})
            target: str = params.get("target", "")

            if not plugin_names:
                logger.warning("run_executor.no_plugins", run_id=str(run_id))
                run.status = RunStatus.failed.value
                run.error_message = "No plugins configured in pipeline."
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            logger.info(
                "run_executor.start",
                run_id=str(run_id),
                plugins=plugin_names,
                target=target,
            )

            from app.plugins.registry import get_plugin_class

            results: dict[str, dict] = {}
            errors: list[str] = []

            for plugin_name in plugin_names:
                # Update checkpoint
                run.checkpoint = {
                    **run.checkpoint,
                    "current_plugin": plugin_name,
                }
                await db.commit()

                plugin_cls = get_plugin_class(plugin_name)
                if not plugin_cls:
                    logger.warning(
                        "run_executor.plugin_not_found",
                        plugin=plugin_name,
                        run_id=str(run_id),
                    )
                    errors.append(f"Plugin '{plugin_name}' not found.")
                    continue

                try:
                    plugin = plugin_cls()
                    inputs = {
                        "targets": [target] if target else [],
                        "target": target,
                        "engagement_id": str(run.engagement_id),
                        **{k: v for k, v in params.items() if k not in ("target",)},
                    }
                    result = await plugin.run(inputs=inputs, run_id=run.id)
                    results[plugin_name] = result

                    logger.info(
                        "run_executor.plugin_done",
                        plugin=plugin_name,
                        status=result.get("status"),
                        run_id=str(run_id),
                    )

                except Exception as exc:
                    logger.error(
                        "run_executor.plugin_error",
                        plugin=plugin_name,
                        error=str(exc),
                        run_id=str(run_id),
                    )
                    errors.append(f"{plugin_name}: {exc}")
                    results[plugin_name] = {"status": "error", "error": str(exc)}

                # Mark plugin as completed
                completed = list(run.checkpoint.get("completed_plugins", []))
                completed.append(plugin_name)
                run.checkpoint = {
                    **run.checkpoint,
                    "completed_plugins": completed,
                    "current_plugin": None,
                }
                await db.commit()

            # Final status
            all_ok = all(r.get("status") != "error" for r in results.values())
            run.status = RunStatus.completed.value if (all_ok and not errors) else RunStatus.failed.value
            run.completed_at = datetime.now(timezone.utc)
            run.checkpoint = {
                **run.checkpoint,
                "current_plugin": None,
                "results": results,
            }
            if errors:
                run.error_message = "; ".join(errors[:3])

            await db.commit()

            logger.info(
                "run_executor.finished",
                run_id=str(run_id),
                status=run.status,
                plugins_run=len(results),
                errors=len(errors),
            )

        except Exception as exc:
            logger.error(
                "run_executor.fatal_error",
                run_id=str(run_id),
                error=str(exc),
            )
            # Best-effort: mark the run as failed
            try:
                async with AsyncSessionLocal() as db2:
                    run2 = await db2.get(EngagementRun, run_id)
                    if run2 and run2.status in (
                        RunStatus.pending.value,
                        RunStatus.running.value,
                    ):
                        run2.status = RunStatus.failed.value
                        run2.error_message = f"Executor error: {exc}"
                        run2.completed_at = datetime.now(timezone.utc)
                        await db2.commit()
            except Exception:
                pass
