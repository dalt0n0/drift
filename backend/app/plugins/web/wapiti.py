"""Wapiti: web application vulnerability scanner."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class WapitiPlugin(BasePlugin):
    manifest = PluginManifest(
        name="wapiti",
        version="3.2.0",
        category="web",
        is_intrusive=True,
        binary="wapiti",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=900,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        return [
            "wapiti",
            "-u", target,
            "-f", "json",
            "-o", "/dev/stdout",
            "--flush-session",
            "--no-bugreport",
        ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        try:
            data = json.loads(raw)
            vulnerabilities = data.get("vulnerabilities", {})
            for vuln_type, vuln_list in vulnerabilities.items():
                for v in vuln_list:
                    findings.append({
                        "name": vuln_type,
                        "severity": _wapiti_level_to_severity(v.get("level", 1)),
                        "path": v.get("path", ""),
                        "parameter": v.get("parameter", ""),
                        "info": v.get("info", ""),
                        "http_request": v.get("http_request", ""),
                        "curl_command": v.get("curl_command", ""),
                        "wstg": v.get("wstg", []),
                    })
        except (json.JSONDecodeError, AttributeError):
            pass

        return {"findings": findings, "total": len(findings)}


def _wapiti_level_to_severity(level: int) -> str:
    return {1: "low", 2: "medium", 3: "high"}.get(level, "info")
