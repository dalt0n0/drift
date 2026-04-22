"""ToolRunner: async subprocess execution with timeout and graceful kill."""
from __future__ import annotations

import asyncio
import signal
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Grace period before SIGKILL after SIGTERM
_KILL_GRACE_SECONDS = 5


@dataclass
class ToolResult:
    """Result of a tool execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
    command: list[str] = field(default_factory=list)


class ToolRunnerError(Exception):
    """Raised when a tool execution fails fatally."""


class ToolRunner:
    """Async subprocess runner with streaming, timeout, and graceful kill.

    When tools_container is set, every command is prefixed with
    ``docker exec -i <container>`` so that binaries are executed inside the
    dedicated Kali tools container rather than the API container.

    Usage:
        runner = ToolRunner(timeout=300)
        result = await runner.run(["nmap", "-sV", "target.com"])
    """

    def __init__(
        self,
        timeout: int = 300,
        publish: Callable[[dict], Coroutine] | None = None,
        tools_container: str = "",
    ):
        self.timeout = timeout
        self.publish = publish
        self.tools_container = tools_container

    async def _emit(self, event: dict) -> None:
        """Publish an event if a publish callback is set."""
        if self.publish:
            try:
                await self.publish(event)
            except Exception as e:
                logger.warning("tool_runner.publish_error", error=str(e))

    async def run(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        stream_stdout: bool = True,
    ) -> ToolResult:
        """Execute a command as an async subprocess.

        Args:
            cmd: Command as a LIST of arguments. Never shell=True.
            env: Optional environment variables to merge.
            cwd: Working directory.
            stream_stdout: If True, stream stdout lines via publish callback.

        Returns:
            ToolResult with exit code, captured output, timing info.
        """
        if not cmd or not isinstance(cmd, list):
            raise ToolRunnerError("Command must be a non-empty list of strings")

        # Route execution through the tools container if configured
        tool_name = cmd[0]
        if self.tools_container:
            cmd = ["docker", "exec", "-i", self.tools_container] + cmd

        logger.info("tool_runner.start", cmd=tool_name, args=cmd[1:], timeout=self.timeout)
        await self._emit({"type": "progress", "tool": tool_name, "status": "starting"})

        start_time = time.monotonic()
        timed_out = False
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError:
            raise ToolRunnerError(f"Binary not found: {tool_name}")
        except PermissionError:
            raise ToolRunnerError(f"Permission denied: {tool_name}")
        except OSError as e:
            raise ToolRunnerError(f"OS error executing {tool_name}: {e}")

        async def _read_stream(
            stream: asyncio.StreamReader,
            lines_buf: list[str],
            stream_name: str,
        ) -> None:
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                lines_buf.append(line)
                if stream_stdout and stream_name == "stdout":
                    await self._emit({"type": "output", "tool": tool_name, "line": line})

        try:
            stdout_task = asyncio.create_task(
                _read_stream(proc.stdout, stdout_lines, "stdout")
            )
            stderr_task = asyncio.create_task(
                _read_stream(proc.stderr, stderr_lines, "stderr")
            )

            await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, proc.wait()),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            logger.warning(
                "tool_runner.timeout",
                cmd=cmd[0],
                pid=proc.pid,
                timeout=self.timeout,
            )
            await self._emit({
                "type": "error",
                "tool": tool_name,
                "message": f"Timed out after {self.timeout}s",
            })
            await self._graceful_kill(proc)

        duration = time.monotonic() - start_time
        exit_code = proc.returncode if proc.returncode is not None else -1

        result = ToolResult(
            exit_code=exit_code,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            timed_out=timed_out,
            duration_seconds=round(duration, 2),
            command=cmd,
        )

        logger.info(
            "tool_runner.complete",
            cmd=tool_name,
            exit_code=exit_code,
            duration=result.duration_seconds,
            timed_out=timed_out,
            stdout_lines=len(stdout_lines),
            stderr_lines=len(stderr_lines),
        )

        await self._emit({
            "type": "progress",
            "tool": tool_name,
            "status": "timeout" if timed_out else ("success" if exit_code == 0 else "error"),
            "exit_code": exit_code,
            "duration": result.duration_seconds,
        })

        return result

    @staticmethod
    async def _graceful_kill(proc: asyncio.subprocess.Process) -> None:
        """SIGTERM, wait grace period, then SIGKILL if still alive."""
        try:
            proc.terminate()
        except ProcessLookupError:
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE_SECONDS)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await proc.wait()
            except Exception:
                pass
