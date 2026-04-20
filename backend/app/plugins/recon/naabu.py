"""Naabu: fast port scanner written in Go."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class NaabuPlugin(BasePlugin):
    manifest = PluginManifest(
        name="naabu",
        version="2.3.2",
        category="scanning",
        is_intrusive=True,
        binary="naabu",
        inputs=["hosts", "cidr"],
        outputs=["ports"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=300,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = [
            "naabu",
            "-silent",
            "-json",
            "-rate", str(inputs.get("rate", "1000")),
        ]

        if inputs.get("ports"):
            cmd.extend(["-p", inputs["ports"]])
        else:
            cmd.extend(["-top-ports", "1000"])

        if len(targets) == 1:
            cmd.extend(["-host", targets[0]])
        else:
            cmd.extend(["-list", "/dev/stdin"])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        ports = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                ports.append({
                    "ip": data.get("ip", data.get("host", "")),
                    "port": data.get("port", 0),
                    "protocol": data.get("protocol", "tcp"),
                })
            except json.JSONDecodeError:
                # Plain text: "host:port"
                if ":" in line:
                    parts = line.rsplit(":", 1)
                    if len(parts) == 2:
                        try:
                            ports.append({
                                "ip": parts[0],
                                "port": int(parts[1]),
                                "protocol": "tcp",
                            })
                        except ValueError:
                            continue

        return {
            "ports": ports,
            "total": len(ports),
        }
