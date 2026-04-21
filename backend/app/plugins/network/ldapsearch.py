"""ldapsearch: LDAP directory enumeration."""
from __future__ import annotations

import re

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_DN_RE = re.compile(r"^dn:\s*(.+)$", re.IGNORECASE)
_ATTR_RE = re.compile(r"^([a-zA-Z0-9-]+):\s*(.+)$")


class LdapsearchPlugin(BasePlugin):
    manifest = PluginManifest(
        name="ldapsearch",
        version="2.6.0",
        category="network",
        is_intrusive=True,
        binary="ldapsearch",
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
        base_dn = inputs.get("base_dn", "")
        bind_dn = inputs.get("bind_dn", "")
        password = inputs.get("password", "")
        query = inputs.get("query", "(objectClass=*)")
        port = inputs.get("port", 389)

        cmd = [
            "ldapsearch",
            "-x",                      # simple auth
            "-H", f"ldap://{target}:{port}",
            "-b", base_dn,
            query,
        ]
        if bind_dn:
            cmd.extend(["-D", bind_dn, "-w", password])
        else:
            cmd.extend(["-D", "", "-w", ""])  # anonymous

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        current: dict = {}

        for line in result.stdout.splitlines():
            line = line.rstrip()
            if not line:
                if current.get("dn"):
                    findings.append({
                        "type": "ldap_entry",
                        "severity": _entry_severity(current),
                        **current,
                    })
                current = {}
                continue

            dn_m = _DN_RE.match(line)
            if dn_m:
                current["dn"] = dn_m.group(1)
                continue

            attr_m = _ATTR_RE.match(line)
            if attr_m:
                key, value = attr_m.group(1), attr_m.group(2)
                if key in current:
                    existing = current[key]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        current[key] = [existing, value]
                else:
                    current[key] = value

        if current.get("dn"):
            findings.append({
                "type": "ldap_entry",
                "severity": _entry_severity(current),
                **current,
            })

        # Check for null-base enumeration success (always interesting)
        num_results = len([f for f in findings if f.get("dn")])
        summary = []
        if num_results > 0:
            summary.append({
                "type": "ldap_summary",
                "severity": "medium",
                "detail": f"Anonymous LDAP enumeration returned {num_results} entries",
                "entries": num_results,
            })

        return {"findings": summary + findings, "total": len(summary + findings)}


def _entry_severity(entry: dict) -> str:
    dn = str(entry.get("dn", "")).lower()
    object_class = str(entry.get("objectClass", "")).lower()
    if "admin" in dn or "privileged" in dn:
        return "high"
    if "user" in object_class or "person" in object_class:
        return "medium"
    return "info"
