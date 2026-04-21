"""enum4linux-ng: SMB/Samba/RPC/LDAP enumeration."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class Enum4linuxNgPlugin(BasePlugin):
    manifest = PluginManifest(
        name="enum4linux-ng",
        version="1.3.4",
        category="network",
        is_intrusive=True,
        binary="enum4linux-ng",
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
        cmd = ["enum4linux-ng", "-oJ", "/dev/stdout", "-A", target]
        if inputs.get("username"):
            cmd.extend(["-u", inputs["username"]])
        if inputs.get("password"):
            cmd.extend(["-p", inputs["password"]])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        try:
            data = json.loads(raw)

            # Users
            users = data.get("users", {})
            if users:
                findings.append({
                    "type": "smb_users",
                    "severity": "medium",
                    "detail": f"Enumerated {len(users)} users",
                    "data": list(users.values()),
                })

            # Groups
            groups = data.get("groups", {})
            if groups:
                findings.append({
                    "type": "smb_groups",
                    "severity": "low",
                    "detail": f"Enumerated {len(groups)} groups",
                    "data": list(groups.values()),
                })

            # Shares
            shares = data.get("shares", {})
            if shares:
                for share_name, share_info in shares.items():
                    access = share_info.get("access", "")
                    findings.append({
                        "type": "smb_share",
                        "severity": "high" if "READ" in str(access) else "info",
                        "share": share_name,
                        "access": access,
                        "comment": share_info.get("comment", ""),
                    })

            # OS info
            os_info = data.get("os_info", {})
            if os_info:
                findings.append({
                    "type": "os_info",
                    "severity": "info",
                    "detail": str(os_info),
                })

            # Password policy
            password_policy = data.get("password_policy", {})
            if password_policy:
                min_len = password_policy.get("min_password_length", 99)
                findings.append({
                    "type": "password_policy",
                    "severity": "high" if min_len < 8 else "low",
                    "min_length": min_len,
                    "detail": str(password_policy),
                })

        except (json.JSONDecodeError, AttributeError):
            pass

        return {"findings": findings, "total": len(findings)}
