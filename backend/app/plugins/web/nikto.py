"""Nikto: web server scanner."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class NiktoPlugin(BasePlugin):
    manifest = PluginManifest(
        name="nikto",
        version="2.1.6",
        category="web",
        is_intrusive=True,
        binary="nikto",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=600,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        return [
            "nikto",
            "-h", target,
            "-Format", "json",
            "-output", "/dev/stdout",
            "-nointeractive",
        ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        try:
            data = json.loads(raw)
            vulns = data.get("vulnerabilities", [])
            for v in vulns:
                findings.append({
                    "id": v.get("id", ""),
                    "osvdb": v.get("OSVDB", ""),
                    "method": v.get("method", "GET"),
                    "url": v.get("url", ""),
                    "msg": v.get("msg", ""),
                })
        except (json.JSONDecodeError, AttributeError):
            # Nikto sometimes writes partial JSON; attempt JSONL
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    v = json.loads(line)
                    findings.append({
                        "id": v.get("id", ""),
                        "url": v.get("url", ""),
                        "msg": v.get("msg", ""),
                    })
                except json.JSONDecodeError:
                    continue

        return {"findings": findings, "total": len(findings)}
