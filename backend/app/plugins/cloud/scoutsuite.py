"""ScoutSuite: multi-cloud security auditing tool."""
from __future__ import annotations

import json
import os
import tempfile

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class ScoutSuitePlugin(BasePlugin):
    manifest = PluginManifest(
        name="scoutsuite",
        version="5.13.0",
        category="cloud",
        is_intrusive=False,
        binary="scout",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=3600,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        provider = inputs.get("provider", "aws")
        report_dir = inputs.get("report_dir", "/tmp/scoutsuite_report")
        profile = inputs.get("aws_profile", "")

        cmd = [
            "scout",
            provider,
            "--report-dir", report_dir,
            "--no-browser",
        ]
        if profile:
            cmd.extend(["--profile", profile])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        report_dir = inputs.get("report_dir", "/tmp/scoutsuite_report")

        # ScoutSuite writes a JSON report file, not stdout
        # Try to read it from the report directory
        try:
            import glob
            json_files = glob.glob(os.path.join(report_dir, "*.js"))
            for json_file in json_files:
                with open(json_file, "r") as f:
                    content = f.read()
                # ScoutSuite JS files start with "scoutsuite_results =" or similar
                if content.startswith("scoutsuite_results"):
                    content = content.split("=", 1)[1].strip().rstrip(";")
                data = json.loads(content)
                services = data.get("services", {})
                for service_name, service_data in services.items():
                    for finding_id, finding_data in service_data.get("findings", {}).items():
                        flagged = finding_data.get("flagged_items", 0)
                        if flagged == 0:
                            continue
                        level = finding_data.get("level", "informational").lower()
                        severity_map = {
                            "danger": "high", "warning": "medium",
                            "good": "info", "informational": "info",
                        }
                        findings.append({
                            "check_id": finding_id,
                            "service": service_name,
                            "description": finding_data.get("description", ""),
                            "severity": severity_map.get(level, "medium"),
                            "flagged_items": flagged,
                            "checked_items": finding_data.get("checked_items", 0),
                            "level": level,
                        })
        except (OSError, json.JSONDecodeError, KeyError):
            # Parse stdout as fallback (progress output)
            for line in result.stdout.splitlines():
                if "ERROR" in line or "WARN" in line:
                    findings.append({
                        "type": "scan_message",
                        "severity": "medium" if "ERROR" in line else "low",
                        "detail": line.strip(),
                    })

        return {"findings": findings, "total": len(findings)}
