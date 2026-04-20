"""Masscan: mass IP port scanner (very fast, intrusive)."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class MasscanPlugin(BasePlugin):
    manifest = PluginManifest(
        name="masscan",
        version="1.3.2",
        category="scanning",
        is_intrusive=True,
        binary="masscan",
        inputs=["cidr", "hosts"],
        outputs=["ports"],
        dependencies=[],
        rate_limit=1,
        timeout_seconds=600,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        rate = inputs.get("rate", "1000")
        ports = inputs.get("ports", "1-65535")

        cmd = [
            "masscan",
            "-p", str(ports),
            "--rate", str(rate),
            "-oJ", "-",  # JSON to stdout
            "--open-only",
        ]
        cmd.extend(targets)
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json

        ports = []
        # Masscan JSON is an array with trailing comma issues
        stdout = result.stdout.strip()
        if stdout.startswith("["):
            # Fix trailing comma before ]
            stdout = stdout.rstrip().rstrip(",") + "]"
            if not stdout.endswith("]"):
                stdout += "]"

        try:
            data = json.loads(stdout)
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                ip = entry.get("ip", "")
                for port_info in entry.get("ports", []):
                    ports.append({
                        "ip": ip,
                        "port": port_info.get("port", 0),
                        "protocol": port_info.get("proto", "tcp"),
                        "status": port_info.get("status", "open"),
                        "service": port_info.get("service", {}).get("name", ""),
                    })
        except json.JSONDecodeError:
            # Fallback: parse line-by-line
            for line in result.stdout.splitlines():
                line = line.strip()
                if '"ip"' in line:
                    try:
                        entry = json.loads(line.rstrip(","))
                        ip = entry.get("ip", "")
                        for port_info in entry.get("ports", []):
                            ports.append({
                                "ip": ip,
                                "port": port_info.get("port", 0),
                                "protocol": port_info.get("proto", "tcp"),
                                "status": "open",
                            })
                    except json.JSONDecodeError:
                        continue

        return {
            "ports": ports,
            "total": len(ports),
        }
