"""Run executor: executes an EngagementRun's plugin pipeline as a background task."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.database import AsyncSessionLocal
from app.models.run import EngagementRun, RunStatus

logger = structlog.get_logger(__name__)

# Maximum log lines kept in checkpoint (prevents unbounded growth)
_MAX_LOG_LINES = 2000


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
                "logs": [],
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

            # Shared in-memory log buffer — flushed to checkpoint after each plugin
            log_lines: list[str] = []

            def _make_publish(plugin_name: str):
                """Return an async publish callback that appends to log_lines."""
                async def publish(event: dict) -> None:
                    evt_type = event.get("type", "")
                    tool = event.get("tool", plugin_name)
                    if evt_type == "output":
                        line = event.get("line", "")
                        if line:
                            log_lines.append(line)
                    elif evt_type == "progress":
                        status = event.get("status", "")
                        if status:
                            log_lines.append(f"[{tool}] {status}")
                    elif evt_type == "error":
                        msg = event.get("message", "error")
                        log_lines.append(f"[{tool}] ERROR: {msg}")
                return publish

            for plugin_name in plugin_names:
                # Update checkpoint: mark plugin as current
                run.checkpoint = {
                    **run.checkpoint,
                    "current_plugin": plugin_name,
                    "logs": log_lines[-_MAX_LOG_LINES:],
                }
                await db.commit()

                plugin_cls = get_plugin_class(plugin_name)
                if not plugin_cls:
                    msg = f"Plugin '{plugin_name}' not found in registry."
                    logger.warning(
                        "run_executor.plugin_not_found",
                        plugin=plugin_name,
                        run_id=str(run_id),
                    )
                    errors.append(f"{plugin_name}: {msg}")
                    log_lines.append(f"[{plugin_name}] ERROR: {msg}")
                    continue

                try:
                    plugin = plugin_cls()
                    inputs = {
                        "targets": [target] if target else [],
                        "target": target,
                        "engagement_id": str(run.engagement_id),
                        **{k: v for k, v in params.items() if k not in ("target",)},
                    }

                    log_lines.append(f"[{plugin_name}] Starting — target: {target or '(none)'}")

                    result = await plugin.run(
                        inputs=inputs,
                        run_id=run.id,
                        publish=_make_publish(plugin_name),
                    )
                    results[plugin_name] = result

                    # If the plugin returned an error dict, surface it
                    if result.get("status") == "error":
                        # Prefer explicit error message, then last stderr line, then exit code
                        stderr_tail = (result.get("stderr") or "").strip()
                        stderr_last = stderr_tail.splitlines()[-1] if stderr_tail else ""
                        err = (
                            result.get("error")
                            or stderr_last
                            or f"exited with code {result.get('exit_code', '?')}"
                        )
                        errors.append(f"{plugin_name}: {err}")
                        log_lines.append(f"[{plugin_name}] ERROR: {err}")
                        # Emit all stderr lines for visibility
                        for stderr_line in stderr_tail.splitlines():
                            log_lines.append(f"  stderr: {stderr_line}")
                    elif result.get("status") == "skipped":
                        reason = result.get("reason", "unknown")
                        errors.append(f"{plugin_name}: skipped ({reason})")
                        log_lines.append(f"[{plugin_name}] SKIPPED: {reason}")
                    else:
                        duration = result.get("duration_seconds", 0)
                        log_lines.append(
                            f"[{plugin_name}] Done in {duration}s"
                            + (f" — exit {result.get('exit_code')}" if result.get("exit_code") is not None else "")
                        )

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
                    err_msg = str(exc)
                    errors.append(f"{plugin_name}: {err_msg}")
                    log_lines.append(f"[{plugin_name}] EXCEPTION: {err_msg}")
                    results[plugin_name] = {"status": "error", "error": err_msg}

                # Mark plugin as completed; flush logs to checkpoint
                completed = list(run.checkpoint.get("completed_plugins", []))
                completed.append(plugin_name)
                run.checkpoint = {
                    **run.checkpoint,
                    "completed_plugins": completed,
                    "current_plugin": None,
                    "logs": log_lines[-_MAX_LOG_LINES:],
                }
                await db.commit()

            # Final status — skipped counts as an error for overall status
            all_ok = not errors and all(
                r.get("status") not in ("error", "skipped")
                for r in results.values()
            )
            run.status = RunStatus.completed.value if all_ok else RunStatus.failed.value
            run.completed_at = datetime.now(timezone.utc)
            run.checkpoint = {
                **run.checkpoint,
                "current_plugin": None,
                "results": {k: {ek: ev for ek, ev in v.items() if ek != "parsed"} for k, v in results.items()},
                "logs": log_lines[-_MAX_LOG_LINES:],
            }
            if errors:
                run.error_message = "; ".join(errors[:5])

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
            # Best-effort: mark the run as failed with an error message
            try:
                async with AsyncSessionLocal() as db2:
                    run2 = await db2.get(EngagementRun, run_id)
                    if run2 and run2.status in (
                        RunStatus.pending.value,
                        RunStatus.running.value,
                    ):
                        run2.status = RunStatus.failed.value
                        run2.error_message = f"Executor crashed: {exc}"
                        run2.completed_at = datetime.now(timezone.utc)
                        await db2.commit()
            except Exception:
                pass
