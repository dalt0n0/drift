"""Waybackurls: fetch URLs from the Wayback Machine."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class WaybackurlsPlugin(BasePlugin):
    manifest = PluginManifest(
        name="waybackurls",
        version="0.1.0",
        category="recon",
        is_intrusive=False,
        binary="waybackurls",
        inputs=["domains"],
        outputs=["urls"],
        dependencies=[],
        rate_limit=3,
        timeout_seconds=180,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        return ["waybackurls", target]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        urls = []
        seen = set()
        for line in result.stdout.splitlines():
            url = line.strip()
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                urls.append({"url": url, "source": "waybackurls"})

        return {
            "urls": urls,
            "total": len(urls),
        }
