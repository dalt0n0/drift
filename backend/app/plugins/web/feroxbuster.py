"""feroxbuster: recursive content discovery tool."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_DEFAULT_WORDLIST = "/usr/share/seclists/Discovery/Web-Content/common.txt"


class FeroxbusterPlugin(BasePlugin):
    manifest = PluginManifest(
        name="feroxbuster",
        version="2.10.0",
        category="web",
        is_intrusive=True,
        binary="feroxbuster",
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
        wordlist = inputs.get("wordlist", _DEFAULT_WORDLIST)
        depth = inputs.get("depth", 3)
        filter_codes = inputs.get("filter_codes", [404, 400])

        cmd = [
            "feroxbuster",
            "--url", target,
            "--wordlist", wordlist,
            "--depth", str(depth),
            "--json",
            "--quiet",
            "--no-state",
        ]
        for code in filter_codes:
            cmd.extend(["--filter-status", str(code)])
        if inputs.get("extensions"):
            cmd.extend(["--extensions", inputs["extensions"]])
        if inputs.get("rate_limit"):
            cmd.extend(["--rate-limit", str(inputs["rate_limit"])])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # feroxbuster JSONL: type "response" has the actual results
                if data.get("type") == "response":
                    findings.append({
                        "url": data.get("url", ""),
                        "status": data.get("status", 0),
                        "content_length": data.get("content_length", 0),
                        "word_count": data.get("word_count", 0),
                        "line_count": data.get("line_count", 0),
                        "method": data.get("method", "GET"),
                        "extension": data.get("extension", ""),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

        return {"findings": findings, "total": len(findings)}
