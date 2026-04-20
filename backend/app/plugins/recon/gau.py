"""gau (GetAllURLs): fetch known URLs from multiple sources."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class GauPlugin(BasePlugin):
    manifest = PluginManifest(
        name="gau",
        version="2.2.3",
        category="recon",
        is_intrusive=False,
        binary="gau",
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
        return ["gau", "--threads", "5", "--json", target]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        urls = []
        seen = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                url = data.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    urls.append({
                        "url": url,
                        "source": data.get("source", "gau"),
                    })
            except json.JSONDecodeError:
                # Plain text output
                if line.startswith("http") and line not in seen:
                    seen.add(line)
                    urls.append({"url": line, "source": "gau"})

        return {
            "urls": urls,
            "total": len(urls),
        }
