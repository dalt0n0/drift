"""Base plugin class: defines the standard interface all tool plugins implement."""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

import structlog

from app.plugins.manifest import PluginManifest
from app.plugins.rate_limiter import RateLimiter
from app.plugins.scope_guard import scope_guard
from app.plugins.tool_runner import ToolResult, ToolRunner

logger = structlog.get_logger(__name__)


class BasePlugin(ABC):
    """Abstract base class for all Drift tool plugins.

    Subclasses must define:
        - manifest: PluginManifest class attribute
        - build_command(): construct the command list from inputs
        - parse_output(): parse ToolResult into structured findings

    The `run()` method handles the full lifecycle:
        1. Validate inputs vs scope (via ScopeGuard)
        2. Acquire rate-limit slot
        3. Build and execute the subprocess
        4. Stream stdout to publish callback
        5. Parse output into structured data
        6. Store artifacts to MinIO
        7. Release rate-limit slot
    """

    manifest: PluginManifest

    def __init__(self, rate_limiter: RateLimiter | None = None):
        self._rate_limiter = rate_limiter

    @abstractmethod
    def build_command(self, inputs: dict) -> list[str]:
        """Build the command-line argument list from inputs.

        Args:
            inputs: Dict with at minimum "targets" key.

        Returns:
            Command as a list of strings. NEVER use shell=True.
        """
        ...

    @abstractmethod
    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        """Parse raw tool output into structured findings.

        Args:
            result: The ToolResult from execution.
            inputs: Original inputs for context.

        Returns:
            Dict with structured output (findings, subdomains, ports, etc.)
        """
        ...

    @scope_guard
    async def run(
        self,
        inputs: dict,
        run_id: str | uuid.UUID,
        publish: Callable[[dict], Coroutine] | None = None,
    ) -> dict:
        """Execute the plugin's tool and return structured results.

        Args:
            inputs: Must contain "targets" and optionally "engagement_id".
            run_id: The EngagementRun ID for artifact storage.
            publish: Async callback for streaming events to WebSocket.

        Returns:
            Dict with parsed results, timing, and artifact paths.
        """
        engagement_id = inputs.get("engagement_id", "unknown")
        tool_name = self.manifest.name

        # Acquire rate limit
        if self._rate_limiter and self.manifest.rate_limit > 0:
            await self._rate_limiter.acquire(
                tool_name,
                max_concurrent=self.manifest.rate_limit,
                timeout=self.manifest.timeout_seconds,
            )

        try:
            # Build command
            cmd = self.build_command(inputs)

            if publish:
                await publish({
                    "type": "progress",
                    "tool": tool_name,
                    "status": "running",
                    "command": cmd[0],
                })

            # Execute — route through tools container if configured
            from app.config import get_settings
            tools_container = get_settings().TOOLS_CONTAINER

            runner = ToolRunner(
                timeout=self.manifest.timeout_seconds,
                publish=publish,
                tools_container=tools_container,
            )
            result = await runner.run(cmd)

            # Parse output
            parsed = self.parse_output(result, inputs)

            # Build artifact JSONL
            artifact_lines = self._build_artifact_lines(parsed, result, inputs)

            # Store artifact
            artifact_path = f"artifacts/{engagement_id}/{run_id}/{tool_name}.jsonl"
            await self._store_artifact(artifact_path, artifact_lines)

            if publish:
                await publish({
                    "type": "progress",
                    "tool": tool_name,
                    "status": "completed",
                    "exit_code": result.exit_code,
                    "duration": result.duration_seconds,
                    "findings_count": len(parsed.get("findings", [])),
                })

            return {
                "tool": tool_name,
                "status": "success" if result.exit_code == 0 else "error",
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "duration_seconds": result.duration_seconds,
                "artifact_path": artifact_path,
                "parsed": parsed,
                # Include stderr tail so executor can surface a useful error message
                "stderr": result.stderr[-500:] if result.stderr else "",
            }

        except Exception as e:
            logger.error(
                "plugin.run_error",
                plugin=tool_name,
                error=str(e),
                run_id=str(run_id),
            )
            if publish:
                await publish({
                    "type": "error",
                    "tool": tool_name,
                    "message": str(e),
                })
            return {
                "tool": tool_name,
                "status": "error",
                "error": str(e),
            }
        finally:
            # Release rate limit
            if self._rate_limiter and self.manifest.rate_limit > 0:
                await self._rate_limiter.release(tool_name)

    def _build_artifact_lines(
        self, parsed: dict, result: ToolResult, inputs: dict
    ) -> list[str]:
        """Build JSONL artifact lines from parsed output."""
        lines = []
        meta = {
            "tool": self.manifest.name,
            "version": self.manifest.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "timed_out": result.timed_out,
            "targets": inputs.get("targets", []),
        }
        lines.append(json.dumps({"type": "meta", **meta}, default=str))

        # Add individual findings/results as JSONL entries
        for key in ("findings", "subdomains", "hosts", "ports", "urls", "results"):
            items = parsed.get(key, [])
            for item in items:
                if isinstance(item, dict):
                    lines.append(json.dumps({"type": key, **item}, default=str))
                else:
                    lines.append(json.dumps({"type": key, "value": str(item)}, default=str))

        # Store raw stdout/stderr as final entries
        if result.stdout:
            lines.append(json.dumps({
                "type": "raw_stdout",
                "data": result.stdout[:50000],  # Truncate massive output
            }))
        if result.stderr:
            lines.append(json.dumps({
                "type": "raw_stderr",
                "data": result.stderr[:10000],
            }))

        return lines

    async def _store_artifact(self, path: str, lines: list[str]) -> None:
        """Store JSONL artifact to MinIO."""
        content = "\n".join(lines) + "\n"
        try:
            from app.config import get_settings
            from minio import Minio
            from io import BytesIO

            settings = get_settings()
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ROOT_USER,
                secret_key=settings.MINIO_ROOT_PASSWORD,
                secure=settings.MINIO_SECURE,
            )

            bucket = settings.MINIO_BUCKET_ARTIFACTS
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)

            data = content.encode("utf-8")
            client.put_object(
                bucket,
                path,
                BytesIO(data),
                length=len(data),
                content_type="application/x-ndjson",
            )
            logger.info("plugin.artifact_stored", path=path, size=len(data))
        except Exception as e:
            # Don't fail the run if artifact storage fails
            logger.warning("plugin.artifact_store_error", path=path, error=str(e))
