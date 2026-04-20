"""Assetfinder: find related domains and subdomains."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class AssetfinderPlugin(BasePlugin):
    manifest = PluginManifest(
        name="assetfinder",
        version="0.1.1",
        category="recon",
        is_intrusive=False,
        binary="assetfinder",
        inputs=["domains"],
        outputs=["subdomains"],
        dependencies=[],
        rate_limit=5,
        timeout_seconds=120,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        # assetfinder takes one domain at a time via stdin or argument
        # For multiple targets, we run for the first one (orchestrator fans out)
        target = targets[0] if targets else ""
        return ["assetfinder", "--subs-only", target]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        subdomains = []
        seen = set()
        for line in result.stdout.splitlines():
            line = line.strip().lower()
            if line and "." in line and line not in seen:
                seen.add(line)
                subdomains.append({"subdomain": line, "source": "assetfinder"})

        return {
            "subdomains": subdomains,
            "total": len(subdomains),
        }
