"""OWASP ZAP: headless web application scanner."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class ZAPPlugin(BasePlugin):
    manifest = PluginManifest(
        name="zap",
        version="2.14.0",
        category="web",
        is_intrusive=True,
        binary="zap.sh",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=1800,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        # Use ZAP baseline scan (passive) or full scan (active) depending on mode
        active = inputs.get("active_scan", False)
        report_path = inputs.get("report_path", "/tmp/zap_report.json")

        if active:
            # Full active scan
            return [
                "zap-full-scan.py",
                "-t", target,
                "-J", report_path,
                "-I",  # ignore rules failures
            ]
        else:
            # Baseline passive scan
            return [
                "zap-baseline.py",
                "-t", target,
                "-J", report_path,
                "-I",
            ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []

        # Try to parse JSON report file output (written by ZAP scripts)
        # ZAP scripts write JSON to the report path, but also print summary to stdout
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # ZAP JSON report structure
                if "site" in data:
                    for site in data.get("site", []):
                        for alert in site.get("alerts", []):
                            risk = alert.get("riskcode", "0")
                            risk_map = {"3": "high", "2": "medium", "1": "low", "0": "info"}
                            findings.append({
                                "name": alert.get("name", ""),
                                "severity": risk_map.get(str(risk), "info"),
                                "risk_code": risk,
                                "confidence": alert.get("confidence", ""),
                                "description": alert.get("desc", ""),
                                "solution": alert.get("solution", ""),
                                "reference": alert.get("reference", ""),
                                "alert_ref": alert.get("alertRef", ""),
                                "instances": [
                                    {
                                        "uri": inst.get("uri", ""),
                                        "method": inst.get("method", ""),
                                        "evidence": inst.get("evidence", ""),
                                    }
                                    for inst in alert.get("instances", [])
                                ],
                            })
            except (json.JSONDecodeError, KeyError):
                continue

        return {
            "findings": findings,
            "total": len(findings),
        }
