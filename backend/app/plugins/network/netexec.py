"""NetExec (nxc): network service testing framework (successor to CrackMapExec)."""
from __future__ import annotations

import json
import re

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class NetExecPlugin(BasePlugin):
    manifest = PluginManifest(
        name="netexec",
        version="1.1.0",
        category="network",
        is_intrusive=True,
        binary="nxc",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=300,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        protocol = inputs.get("protocol", "smb")

        cmd = ["nxc", protocol, target]

        if inputs.get("username"):
            cmd.extend(["-u", inputs["username"]])
        if inputs.get("password"):
            cmd.extend(["-p", inputs["password"]])
        if inputs.get("null_session", False):
            cmd.extend(["-u", "", "-p", ""])

        # Module
        if inputs.get("module"):
            cmd.extend(["-M", inputs["module"]])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            # Strip ANSI codes
            clean = _ANSI_RE.sub("", line).strip()
            if not clean:
                continue

            # Try JSON parse first
            try:
                data = json.loads(clean)
                findings.append(data)
                continue
            except json.JSONDecodeError:
                pass

            # Parse plain-text output: SMB 10.0.0.1 445 HOSTNAME [+] ...
            parts = clean.split()
            if len(parts) >= 4 and parts[0] in ("SMB", "LDAP", "WINRM", "SSH", "FTP", "RDP", "MSSQL"):
                severity = "high" if "[+]" in clean and "Pwn3d!" in clean else \
                           "medium" if "[+]" in clean else "info"
                findings.append({
                    "type": "netexec_result",
                    "protocol": parts[0],
                    "ip": parts[1],
                    "port": parts[2],
                    "hostname": parts[3],
                    "result": clean,
                    "severity": severity,
                    "admin": "Pwn3d!" in clean,
                })

        return {"findings": findings, "total": len(findings)}
