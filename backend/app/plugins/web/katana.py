"""katana: JS-aware web crawler for endpoint discovery."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class KatanaPlugin(BasePlugin):
    manifest = PluginManifest(
        name="katana",
        version="1.0.5",
        category="web",
        is_intrusive=False,
        binary="katana",
        inputs=["targets"],
        outputs=["urls"],
        dependencies=[],
        rate_limit=3,
        timeout_seconds=300,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        depth = inputs.get("depth", 3)

        cmd = [
            "katana",
            "-json",
            "-silent",
            "-depth", str(depth),
            "-js-crawl",
            "-automatic-form-fill",
        ]
        for target in targets:
            cmd.extend(["-u", target])
        if inputs.get("scope"):
            cmd.extend(["-cs", inputs["scope"]])
        if inputs.get("rate_limit"):
            cmd.extend(["-rate-limit", str(inputs["rate_limit"])])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        urls = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                endpoint = data.get("endpoint", "")
                if endpoint:
                    urls.append({
                        "url": endpoint,
                        "method": data.get("request", {}).get("method", "GET"),
                        "source": data.get("source", ""),
                        "tag": data.get("tag", ""),
                        "attribute": data.get("attribute", ""),
                    })
            except json.JSONDecodeError:
                # Plain URL fallback
                if line.startswith("http"):
                    urls.append({"url": line, "method": "GET", "source": "katana"})

        return {"urls": urls, "total": len(urls)}
