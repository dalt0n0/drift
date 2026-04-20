"""Sherlock: find social media accounts by username."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class SherlockPlugin(BasePlugin):
    manifest = PluginManifest(
        name="sherlock",
        version="0.14.3",
        category="recon",
        is_intrusive=False,
        binary="sherlock",
        inputs=["usernames"],
        outputs=["social_profiles"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=120,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        # Sherlock takes usernames as args
        cmd = ["sherlock", "--print-found", "--json", "/dev/stdout"]
        cmd.extend(targets)
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        profiles = []
        try:
            data = json.loads(result.stdout)
            for username, sites in data.items():
                if isinstance(sites, dict):
                    for site_name, info in sites.items():
                        if isinstance(info, dict) and info.get("status") == "Claimed":
                            profiles.append({
                                "username": username,
                                "site": site_name,
                                "url": info.get("url_user", ""),
                            })
        except json.JSONDecodeError:
            # Fallback: parse line-by-line text output
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("[+]") or line.startswith("http"):
                    profiles.append({
                        "url": line.lstrip("[+] ").strip(),
                        "source": "sherlock",
                    })

        return {
            "results": profiles,
            "total": len(profiles),
        }
