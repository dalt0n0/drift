"""Subfinder: fast passive subdomain discovery."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class SubfinderPlugin(BasePlugin):
    manifest = PluginManifest(
        name="subfinder",
        version="2.6.6",
        category="recon",
        is_intrusive=False,
        binary="subfinder",
        inputs=["domains"],
        outputs=["subdomains"],
        dependencies=[],
        rate_limit=3,
        timeout_seconds=300,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = ["subfinder", "-silent", "-json"]
        if len(targets) == 1:
            cmd.extend(["-d", targets[0]])
        else:
            # Multiple domains: use comma-separated
            cmd.extend(["-d", ",".join(targets)])
        # Optional: custom resolvers
        if inputs.get("resolvers_file"):
            cmd.extend(["-rL", inputs["resolvers_file"]])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        """Parse subfinder JSON output into structured subdomains."""
        import json

        subdomains = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                host = data.get("host", "")
                if host:
                    subdomains.append({
                        "subdomain": host,
                        "source": data.get("source", "subfinder"),
                    })
            except json.JSONDecodeError:
                # Plain text fallback (non-json mode)
                if line and "." in line:
                    subdomains.append({"subdomain": line, "source": "subfinder"})

        return {
            "subdomains": subdomains,
            "total": len(subdomains),
        }
