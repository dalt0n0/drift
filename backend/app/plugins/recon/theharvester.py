"""theHarvester: email, name, subdomain, IP, and URL harvesting."""
from __future__ import annotations

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class TheHarvesterPlugin(BasePlugin):
    manifest = PluginManifest(
        name="theharvester",
        version="4.6.0",
        category="recon",
        is_intrusive=False,
        binary="theHarvester",
        inputs=["domains"],
        outputs=["emails", "subdomains", "hosts"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=300,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        sources = inputs.get("sources", "anubis,baidu,bing,certspotter,crtsh,dnsdumpster,hackertarget,otx,rapiddns,threatminer,urlscan,virustotal")
        return [
            "theHarvester",
            "-d", target,
            "-b", sources,
            "-f", "/dev/stdout",
        ]

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        import json
        import re

        emails = []
        subdomains = []
        hosts = []

        # theHarvester outputs mixed format; parse known patterns
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # Email pattern
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", line)
            if email_match:
                email = email_match.group(0).lower()
                if email not in [e["email"] for e in emails]:
                    emails.append({"email": email, "source": "theharvester"})
                continue

            # IP:hostname pattern
            if ":" in line and not line.startswith("["):
                parts = line.split(":")
                if len(parts) == 2:
                    hosts.append({
                        "ip": parts[0].strip(),
                        "hostname": parts[1].strip(),
                        "source": "theharvester",
                    })
                continue

            # Subdomain pattern
            if "." in line and not line.startswith("[") and not line.startswith("*"):
                subdomains.append({"subdomain": line, "source": "theharvester"})

        return {
            "emails": emails,
            "subdomains": subdomains,
            "hosts": hosts,
            "total_emails": len(emails),
            "total_subdomains": len(subdomains),
            "total_hosts": len(hosts),
        }
