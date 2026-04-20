"""Amass: in-depth DNS enumeration and network mapping."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class AmassPlugin(BasePlugin):
    manifest = PluginManifest(
        name="amass",
        version="4.2.0",
        category="recon",
        is_intrusive=False,
        binary="amass",
        inputs=["domains"],
        outputs=["subdomains"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=600,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = ["amass", "enum", "-passive", "-json", "/dev/stdout"]
        for target in targets:
            cmd.extend(["-d", target])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        subdomains = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                name = data.get("name", "")
                if name:
                    subdomains.append({
                        "subdomain": name,
                        "source": ",".join(data.get("sources", ["amass"])),
                        "addresses": data.get("addresses", []),
                    })
            except json.JSONDecodeError:
                if line and "." in line:
                    subdomains.append({"subdomain": line, "source": "amass"})

        return {
            "subdomains": subdomains,
            "total": len(subdomains),
        }
