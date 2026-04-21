"""onesixtyone: fast SNMP community string brute-forcer."""
from __future__ import annotations

import re
import tempfile
import os

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_DEFAULT_COMMUNITIES = ["public", "private", "community", "manager", "admin",
                        "secret", "cisco", "default", "snmp", "monitor"]

# Output line: 10.0.0.1 [public] Hardware: ...
_LINE_RE = re.compile(r"^(\S+)\s+\[([^\]]+)\]\s+(.*)")


class OnesixtyonePlugin(BasePlugin):
    manifest = PluginManifest(
        name="onesixtyone",
        version="0.3.4",
        category="network",
        is_intrusive=True,
        binary="onesixtyone",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=120,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        communities = inputs.get("communities", _DEFAULT_COMMUNITIES)

        # Write communities to temp file (onesixtyone reads from file)
        comm_file = inputs.get("_comm_file", "/tmp/onesixtyone_communities.txt")
        try:
            with open(comm_file, "w") as f:
                f.write("\n".join(communities))
        except OSError:
            comm_file = "/dev/stdin"

        cmd = ["onesixtyone", "-c", comm_file, "-w", "100"]
        cmd.extend(targets)
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _LINE_RE.match(line)
            if m:
                ip, community, sysDescr = m.group(1), m.group(2), m.group(3)
                is_default = community.lower() in [c.lower() for c in _DEFAULT_COMMUNITIES]
                findings.append({
                    "type": "snmp_community",
                    "ip": ip,
                    "community": community,
                    "sysDescr": sysDescr,
                    "severity": "critical" if is_default else "high",
                    "detail": f"SNMP community '{community}' accepted on {ip}",
                })

        return {"findings": findings, "total": len(findings)}
