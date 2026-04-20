"""RustScan: fast port scanner that feeds results to Nmap."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class RustScanPlugin(BasePlugin):
    manifest = PluginManifest(
        name="rustscan",
        version="2.3.0",
        category="scanning",
        is_intrusive=True,
        binary="rustscan",
        inputs=["hosts"],
        outputs=["ports"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=300,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = [
            "rustscan",
            "--batch-size", str(inputs.get("batch_size", "4500")),
            "--timeout", str(inputs.get("connect_timeout", "3000")),
            "--greppable",
        ]

        if inputs.get("ports"):
            cmd.extend(["-p", inputs["ports"]])

        for target in targets:
            cmd.extend(["-a", target])

        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        ports = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # RustScan greppable format: "Open <ip>:<port>"
            if line.lower().startswith("open "):
                addr_port = line.split(" ", 1)[1] if " " in line else ""
                if ":" in addr_port:
                    parts = addr_port.rsplit(":", 1)
                    try:
                        ports.append({
                            "ip": parts[0],
                            "port": int(parts[1]),
                            "protocol": "tcp",
                        })
                    except (ValueError, IndexError):
                        continue
            # Alternative format: "ip -> [port1, port2]"
            elif " -> [" in line:
                parts = line.split(" -> [")
                if len(parts) == 2:
                    ip = parts[0].strip()
                    port_str = parts[1].rstrip("]").strip()
                    for p in port_str.split(","):
                        p = p.strip()
                        if p.isdigit():
                            ports.append({
                                "ip": ip,
                                "port": int(p),
                                "protocol": "tcp",
                            })

        return {
            "ports": ports,
            "total": len(ports),
        }
