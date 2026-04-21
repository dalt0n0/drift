"""CloudSploit: cloud infrastructure security scanner."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_STATUS_SEVERITY = {"FAIL": "high", "WARN": "medium", "PASS": "info", "UNKNOWN": "low"}


class CloudSploitPlugin(BasePlugin):
    manifest = PluginManifest(
        name="cloudsploit",
        version="2.0.0",
        category="cloud",
        is_intrusive=False,
        binary="cloudsploit",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=3600,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        provider = inputs.get("provider", "aws")
        config_file = inputs.get("config_file", "/etc/cloudsploit/config.js")

        cmd = [
            "cloudsploit",
            "scan",
            "--config", config_file,
            "--cloud", provider,
            "--json",
        ]
        if inputs.get("plugins"):
            cmd.extend(["--plugins", ",".join(inputs["plugins"])])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        # CloudSploit outputs one big JSON array
        try:
            results = json.loads(raw)
            if not isinstance(results, list):
                results = [results]
            for r in results:
                status = r.get("status", "UNKNOWN").upper()
                if status == "PASS":
                    continue
                findings.append({
                    "plugin": r.get("plugin", ""),
                    "category": r.get("category", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "severity": _STATUS_SEVERITY.get(status, "medium"),
                    "status": status,
                    "region": r.get("region", "global"),
                    "resource": r.get("resource", "N/A"),
                    "message": r.get("message", ""),
                    "compliance": r.get("compliance", {}),
                })
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Try JSONL
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    status = r.get("status", "UNKNOWN").upper()
                    if status != "PASS":
                        findings.append({
                            "plugin": r.get("plugin", ""),
                            "severity": _STATUS_SEVERITY.get(status, "medium"),
                            "message": r.get("message", ""),
                        })
                except json.JSONDecodeError:
                    continue

        return {"findings": findings, "total": len(findings)}
