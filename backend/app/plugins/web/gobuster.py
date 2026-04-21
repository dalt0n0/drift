"""gobuster: directory/file/DNS/vhost brute-forcer."""
from __future__ import annotations

import re

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_DEFAULT_WORDLIST = "/usr/share/seclists/Discovery/Web-Content/common.txt"
_LINE_RE = re.compile(r"^(/[^\s]*)\s+\(Status:\s*(\d+)\)")


class GobusterPlugin(BasePlugin):
    manifest = PluginManifest(
        name="gobuster",
        version="3.6.0",
        category="web",
        is_intrusive=True,
        binary="gobuster",
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
        mode = inputs.get("mode", "dir")
        threads = inputs.get("threads", 10)

        cmd = [
            "gobuster", mode,
            "-u", target,
            "-w", wordlist,
            "-t", str(threads),
            "--no-error",
            "-q",
        ]
        if inputs.get("extensions"):
            cmd.extend(["-x", inputs["extensions"]])
        if inputs.get("status_codes"):
            cmd.extend(["-s", inputs["status_codes"]])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Standard gobuster output: /path (Status: 200) [Size: 1234]
            m = _LINE_RE.match(line)
            if m:
                path, status = m.group(1), int(m.group(2))
                # Extract size if present
                size_match = re.search(r"\[Size:\s*(\d+)\]", line)
                size = int(size_match.group(1)) if size_match else 0
                target = inputs.get("targets", [""])[0]
                findings.append({
                    "path": path,
                    "url": target.rstrip("/") + path,
                    "status": status,
                    "size": size,
                })
            # DNS mode output: domain.com
            elif "." in line and not line.startswith("/"):
                findings.append({"hostname": line, "status": 0, "size": 0})

        return {"findings": findings, "total": len(findings)}
