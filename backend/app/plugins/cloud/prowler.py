"""Prowler: AWS/Azure/GCP security assessment tool."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_PROWLER_SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
}


class ProwlerPlugin(BasePlugin):
    manifest = PluginManifest(
        name="prowler",
        version="4.2.0",
        category="cloud",
        is_intrusive=False,
        binary="prowler",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=3600,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        provider = inputs.get("provider", "aws")
        profile = inputs.get("aws_profile", "")
        region = inputs.get("region", "")
        checks = inputs.get("checks", [])

        cmd = [
            "prowler",
            provider,
            "-M", "json",
            "-o", "/dev/stdout",
            "--quiet",
        ]
        if profile:
            cmd.extend(["--profile", profile])
        if region:
            cmd.extend(["--region", region])
        for check in checks:
            cmd.extend(["--checks", check])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get("Status", data.get("status", "PASS"))
                if status.upper() in ("PASS", "MANUAL"):
                    continue
                severity_raw = (data.get("Severity") or data.get("severity") or "informational").lower()
                findings.append({
                    "check_id": data.get("CheckID", data.get("check_id", "")),
                    "check_title": data.get("CheckTitle", data.get("check_title", "")),
                    "severity": _PROWLER_SEVERITY_MAP.get(severity_raw, "info"),
                    "status": status,
                    "service": data.get("ServiceName", data.get("service_name", "")),
                    "region": data.get("Region", data.get("region", "")),
                    "account_id": data.get("AccountId", data.get("account_id", "")),
                    "resource_arn": data.get("ResourceArn", data.get("resource_arn", "")),
                    "resource_id": data.get("ResourceId", data.get("resource_id", "")),
                    "description": data.get("Description", data.get("description", "")),
                    "risk": data.get("Risk", data.get("risk", "")),
                    "recommendation": data.get("Recommendation", data.get("recommendation", "")),
                    "compliance": data.get("Compliance", {}),
                })
            except (json.JSONDecodeError, AttributeError):
                continue

        by_severity: dict[str, int] = {}
        for f in findings:
            s = f["severity"]
            by_severity[s] = by_severity.get(s, 0) + 1

        return {"findings": findings, "total": len(findings), "by_severity": by_severity}
