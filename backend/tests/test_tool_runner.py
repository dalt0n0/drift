"""Tests for ToolRunner: async subprocess execution."""
from __future__ import annotations

import asyncio
import sys

import pytest

from app.plugins.tool_runner import ToolResult, ToolRunner, ToolRunnerError

pytestmark = pytest.mark.asyncio


class TestToolRunner:
    async def test_run_simple_command(self):
        runner = ToolRunner(timeout=10)
        result = await runner.run([sys.executable, "-c", "print('hello')"])
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.timed_out is False
        assert result.duration_seconds > 0

    async def test_run_captures_stderr(self):
        runner = ToolRunner(timeout=10)
        result = await runner.run(
            [sys.executable, "-c", "import sys; sys.stderr.write('err\\n')"]
        )
        assert result.exit_code == 0
        assert "err" in result.stderr

    async def test_run_nonzero_exit(self):
        runner = ToolRunner(timeout=10)
        result = await runner.run([sys.executable, "-c", "raise SystemExit(42)"])
        assert result.exit_code == 42

    async def test_run_timeout(self):
        runner = ToolRunner(timeout=1)
        result = await runner.run(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        assert result.timed_out is True

    async def test_run_binary_not_found(self):
        runner = ToolRunner(timeout=5)
        with pytest.raises(ToolRunnerError, match="Binary not found"):
            await runner.run(["nonexistent_binary_xyz"])

    async def test_run_empty_command_raises(self):
        runner = ToolRunner(timeout=5)
        with pytest.raises(ToolRunnerError, match="non-empty list"):
            await runner.run([])

    async def test_run_with_publish_callback(self):
        events = []

        async def mock_publish(event):
            events.append(event)

        runner = ToolRunner(timeout=10, publish=mock_publish)
        result = await runner.run(
            [sys.executable, "-c", "print('line1'); print('line2')"]
        )
        assert result.exit_code == 0
        # Should have progress + output + progress events
        progress_events = [e for e in events if e.get("type") == "progress"]
        output_events = [e for e in events if e.get("type") == "output"]
        assert len(progress_events) >= 2  # starting + success
        assert len(output_events) >= 2  # line1 + line2

    async def test_run_multiline_output(self):
        runner = ToolRunner(timeout=10)
        result = await runner.run(
            [sys.executable, "-c", "for i in range(10): print(f'line {i}')"]
        )
        assert result.exit_code == 0
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 10

    async def test_run_command_stores_command(self):
        runner = ToolRunner(timeout=10)
        cmd = [sys.executable, "-c", "pass"]
        result = await runner.run(cmd)
        assert result.command == cmd

    async def test_tool_result_dataclass(self):
        result = ToolResult(
            exit_code=0,
            stdout="out",
            stderr="err",
            timed_out=False,
            duration_seconds=1.5,
            command=["test"],
        )
        assert result.exit_code == 0
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.timed_out is False
        assert result.duration_seconds == 1.5
