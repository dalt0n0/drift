"""Nikto: web server scanner."""
from __future__ import annotations

import re

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
            "-nointeractive",
            "-Tuning", "x",  # all checks
        ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = (result.stdout or "") + "\n" + (result.stderr or "")

        # Parse nikto text output lines like:
        # + /path: Description of finding (OSVDB-12345)
        _SKIP_PATH = re.compile(
            r'^(\d|Server|Retrieved|No CGI|Allowed HTTP|Target IP|Target Host|Target Port|End Time|Start Time)',
            re.IGNORECASE,
        )
        _SKIP_MSG = re.compile(
            r'(\d+\s+errors?\s+and\s+\d+\s+items?\s+reported|\d+\s+host.{0,20}test|\d{2}:\d{2}:\d{2})',
            re.IGNORECASE,
        )
        pattern = re.compile(r"^\+\s+(.+?):\s+(.+)$", re.MULTILINE)
        for m in pattern.finditer(raw):
            path = m.group(1).strip()
            msg = m.group(2).strip()
            if _SKIP_PATH.match(path) or _SKIP_MSG.search(msg) or _SKIP_MSG.search(path):
                continue
            osvdb_match = re.search(r"OSVDB-(\d+)", msg)
            findings.append({
                "path": path,
                "msg": msg,
                "osvdb": osvdb_match.group(1) if osvdb_match else "",
                "severity": _infer_severity(msg),
            })

        return {"findings": findings, "total": len(findings)}


def _infer_severity(msg: str) -> str:
    msg_l = msg.lower()
    if any(k in msg_l for k in ("remote file inclusion", "rfi", "rce", "remote code", "shell", "backdoor")):
        return "critical"
    if any(k in msg_l for k in ("sql injection", "sqli", "xss", "cross-site", "directory traversal", "lfi", "path traversal")):
        return "high"
    if any(k in msg_l for k in ("csrf", "clickjacking", "default credential", "default password", "weak", "insecure")):
        return "medium"
    if any(k in msg_l for k in ("information disclosure", "version", "banner", "header", "cookie")):
        return "low"
    return "info"
