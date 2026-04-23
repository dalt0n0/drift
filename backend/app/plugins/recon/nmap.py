"""Nmap: network scanner with service/version detection and NSE scripts."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class NmapPlugin(BasePlugin):
    manifest = PluginManifest(
        name="nmap",
        version="7.94",
        category="scanning",
        is_intrusive=True,
        binary="nmap",
        inputs=["hosts", "cidr"],
        outputs=["ports", "services", "os_detection"],
        dependencies=["httpx"],
        rate_limit=2,
        timeout_seconds=900,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = [
            "/usr/lib/nmap/nmap",   # bypass /usr/bin/nmap Kali wrapper (prepends --privileged)
            "-sT",          # TCP connect scan — no raw socket needed
            "-sV",          # Service version detection
            "-oX", "-",     # XML to stdout
            "--open",       # Only open ports
            "-T4",          # Aggressive timing
            "--max-retries", "2",
        ]

        # Optional port specification
        if inputs.get("ports"):
            cmd.extend(["-p", inputs["ports"]])
        elif inputs.get("top_ports"):
            cmd.extend(["--top-ports", str(inputs["top_ports"])])
        else:
            cmd.extend(["--top-ports", "1000"])  # default: top 1000 (faster than -p-)

        cmd.extend(targets)
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        """Parse Nmap XML output into structured host/port/service data."""
        hosts = []

        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError:
            return {"hosts": [], "total_hosts": 0, "total_ports": 0, "raw": result.stdout[:5000]}

        total_ports = 0
        for host_elem in root.findall(".//host"):
            # Get addresses
            addresses = []
            for addr in host_elem.findall("address"):
                addresses.append({
                    "addr": addr.get("addr", ""),
                    "addrtype": addr.get("addrtype", ""),
                })

            # Get hostnames
            hostnames = []
            for hostname in host_elem.findall(".//hostname"):
                hostnames.append({
                    "name": hostname.get("name", ""),
                    "type": hostname.get("type", ""),
                })

            # Get ports
            ports = []
            for port_elem in host_elem.findall(".//port"):
                state = port_elem.find("state")
                service = port_elem.find("service")

                port_data = {
                    "port": int(port_elem.get("portid", 0)),
                    "protocol": port_elem.get("protocol", ""),
                    "state": state.get("state", "") if state is not None else "",
                }

                if service is not None:
                    port_data["service"] = {
                        "name": service.get("name", ""),
                        "product": service.get("product", ""),
                        "version": service.get("version", ""),
                        "extrainfo": service.get("extrainfo", ""),
                        "cpe": [c.text for c in service.findall("cpe") if c.text],
                    }

                # NSE script results
                scripts = []
                for script in port_elem.findall("script"):
                    scripts.append({
                        "id": script.get("id", ""),
                        "output": script.get("output", ""),
                    })
                if scripts:
                    port_data["scripts"] = scripts

                ports.append(port_data)
                total_ports += 1

            # OS detection
            os_matches = []
            for osmatch in host_elem.findall(".//osmatch"):
                os_matches.append({
                    "name": osmatch.get("name", ""),
                    "accuracy": osmatch.get("accuracy", ""),
                })

            hosts.append({
                "addresses": addresses,
                "hostnames": hostnames,
                "ports": ports,
                "os_matches": os_matches[:3],  # Top 3
            })

        return {
            "hosts": hosts,
            "total_hosts": len(hosts),
            "total_ports": total_ports,
        }
