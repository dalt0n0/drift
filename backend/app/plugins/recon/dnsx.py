"""dnsx: fast DNS resolver and record lookup."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class DnsxPlugin(BasePlugin):
    manifest = PluginManifest(
        name="dnsx",
        version="1.2.1",
        category="recon",
        is_intrusive=False,
        binary="dnsx",
        inputs=["subdomains"],
        outputs=["dns_records"],
        dependencies=["subfinder"],
        rate_limit=5,
        timeout_seconds=180,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = [
            "dnsx",
            "-silent",
            "-json",
            "-a", "-aaaa", "-cname", "-mx", "-ns", "-txt",
            "-resp",
        ]
        # dnsx reads from stdin or -l file; for direct targets:
        if targets:
            cmd.extend(["-l", "/dev/stdin"])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        dns_records = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                dns_records.append({
                    "host": data.get("host", ""),
                    "a": data.get("a", []),
                    "aaaa": data.get("aaaa", []),
                    "cname": data.get("cname", []),
                    "mx": data.get("mx", []),
                    "ns": data.get("ns", []),
                    "txt": data.get("txt", []),
                    "status_code": data.get("status_code", ""),
                })
            except json.JSONDecodeError:
                continue

        return {
            "results": dns_records,
            "total": len(dns_records),
        }
