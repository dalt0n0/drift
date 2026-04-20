"""httpx: fast HTTP probing and technology detection."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class HttpxPlugin(BasePlugin):
    manifest = PluginManifest(
        name="httpx",
        version="1.6.6",
        category="recon",
        is_intrusive=False,
        binary="httpx",
        inputs=["subdomains", "hosts"],
        outputs=["http_services"],
        dependencies=["subfinder"],
        rate_limit=5,
        timeout_seconds=300,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = [
            "httpx",
            "-silent",
            "-json",
            "-status-code",
            "-title",
            "-tech-detect",
            "-content-length",
            "-follow-redirects",
            "-threads", "50",
        ]
        if len(targets) == 1:
            cmd.extend(["-u", targets[0]])
        else:
            cmd.extend(["-l", "/dev/stdin"])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        services = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                services.append({
                    "url": data.get("url", ""),
                    "status_code": data.get("status_code", 0),
                    "title": data.get("title", ""),
                    "tech": data.get("tech", []),
                    "content_length": data.get("content_length", 0),
                    "webserver": data.get("webserver", ""),
                    "host": data.get("host", ""),
                    "port": data.get("port", ""),
                    "scheme": data.get("scheme", ""),
                    "final_url": data.get("final_url", ""),
                })
            except json.JSONDecodeError:
                continue

        return {
            "results": services,
            "total": len(services),
        }
