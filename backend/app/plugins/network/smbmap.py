"""smbmap: SMB share enumeration and access testing."""
from __future__ import annotations

import json
import re

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class SmbmapPlugin(BasePlugin):
    manifest = PluginManifest(
        name="smbmap",
        version="1.10.4",
        category="network",
        is_intrusive=True,
        binary="smbmap",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=3,
        timeout_seconds=120,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""

        cmd = ["smbmap", "-H", target]

        if inputs.get("username"):
            cmd.extend(["-u", inputs["username"]])
        else:
            cmd.extend(["-u", ""])
        if inputs.get("password"):
            cmd.extend(["-p", inputs["password"]])
        else:
            cmd.extend(["-p", ""])

        cmd.append("--json")
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()

        # Try JSON
        try:
            data = json.loads(raw)
            # smbmap JSON: {host: {share: {access, comment}}}
            for host, shares in data.items():
                for share_name, share_info in shares.items():
                    access = share_info.get("access", "")
                    can_read = "READ" in str(access).upper()
                    can_write = "WRITE" in str(access).upper()
                    findings.append({
                        "type": "smb_share",
                        "host": host,
                        "share": share_name,
                        "access": access,
                        "comment": share_info.get("comment", ""),
                        "can_read": can_read,
                        "can_write": can_write,
                        "severity": "critical" if can_write else ("high" if can_read else "info"),
                    })
            return {"findings": findings, "total": len(findings)}
        except (json.JSONDecodeError, AttributeError):
            pass

        # Plaintext fallback
        for line in raw.splitlines():
            clean = _ANSI_RE.sub("", line).strip()
            # Disk      Permissions     Comment
            if re.match(r"^\s+\w+\s+READ|WRITE|NO ACCESS", clean):
                parts = clean.split()
                if len(parts) >= 2:
                    findings.append({
                        "type": "smb_share",
                        "share": parts[0],
                        "access": parts[1],
                        "severity": "high" if "READ" in parts[1] else "info",
                    })

        return {"findings": findings, "total": len(findings)}
