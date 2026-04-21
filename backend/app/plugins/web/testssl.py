"""testssl.sh: comprehensive TLS/SSL testing."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFO": "info",
    "OK": "info",
    "WARN": "low",
    "NOT ok": "medium",
}


class TestsslPlugin(BasePlugin):
    manifest = PluginManifest(
        name="testssl",
        version="3.2",
        category="web",
        is_intrusive=False,
        binary="testssl.sh",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=5,
        timeout_seconds=300,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        return [
            "testssl.sh",
            "--jsonfile", "/dev/stdout",
            "--quiet",
            "--fast",
            "--color", "0",
            target,
        ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        try:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                entries = [entries]
            for entry in entries:
                severity_str = entry.get("severity", "INFO").upper()
                severity = _SEVERITY_MAP.get(severity_str, "info")
                if severity_str in ("OK", "INFO") and entry.get("finding", "").lower() in ("yes", "offered", ""):
                    continue
                findings.append({
                    "id": entry.get("id", ""),
                    "ip": entry.get("ip", ""),
                    "port": entry.get("port", ""),
                    "finding": entry.get("finding", ""),
                    "severity": severity,
                    "cve": entry.get("cve", ""),
                    "cwe": entry.get("cwe", ""),
                })
        except (json.JSONDecodeError, AttributeError, TypeError):
            # testssl.sh may produce partial output; skip unparseable
            pass

        return {"findings": findings, "total": len(findings)}
