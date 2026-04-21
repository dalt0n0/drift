"""Nuclei: fast template-based vulnerability scanner."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class NucleiPlugin(BasePlugin):
    manifest = PluginManifest(
        name="nuclei",
        version="3.2.0",
        category="web",
        is_intrusive=True,
        binary="nuclei",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=["httpx"],
        rate_limit=2,
        timeout_seconds=900,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        severities = inputs.get("severities", "low,medium,high,critical")
        cmd = [
            "nuclei",
            "-json",
            "-silent",
            "-severity", severities,
            "-update-templates",
        ]
        for target in targets:
            cmd.extend(["-u", target])
        if inputs.get("templates"):
            cmd.extend(["-t", inputs["templates"]])
        if inputs.get("exclude_templates"):
            cmd.extend(["-exclude-templates", inputs["exclude_templates"]])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                info = data.get("info", {})
                findings.append({
                    "name": info.get("name", ""),
                    "severity": info.get("severity", "info"),
                    "matched_at": data.get("matched-at", ""),
                    "template_id": data.get("template-id", ""),
                    "type": data.get("type", ""),
                    "host": data.get("host", ""),
                    "ip": data.get("ip", ""),
                    "description": info.get("description", ""),
                    "reference": info.get("reference", []),
                    "cvss_score": info.get("classification", {}).get("cvss-score"),
                    "cve_id": info.get("classification", {}).get("cve-id", []),
                    "tags": info.get("tags", []),
                    "curl_command": data.get("curl-command", ""),
                    "request": data.get("request", ""),
                    "response": data.get("response", "")[:2000] if data.get("response") else "",
                })
            except (json.JSONDecodeError, AttributeError):
                continue

        by_severity: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "info")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "findings": findings,
            "total": len(findings),
            "by_severity": by_severity,
        }
