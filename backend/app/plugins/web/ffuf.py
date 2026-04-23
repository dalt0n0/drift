"""ffuf: fast web fuzzer for directory and parameter discovery."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_DEFAULT_WORDLIST = "/opt/drift/wordlists/minimal.txt"


class FfufPlugin(BasePlugin):
    manifest = PluginManifest(
        name="ffuf",
        version="2.1.0",
        category="web",
        is_intrusive=True,
        binary="ffuf",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=2,
        timeout_seconds=600,
        safe_mode_allowed=False,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        target = targets[0] if targets else ""
        wordlist = inputs.get("wordlist") or _DEFAULT_WORDLIST
        filter_codes = inputs.get("filter_codes", "404,400,403")
        extensions = inputs.get("extensions", "")

        url = target.rstrip("/") + "/FUZZ"

        cmd = [
            "ffuf",
            "-u", url,
            "-w", wordlist,
            "-json",           # JSONL to stdout — no temp file, works in container
            "-noninteractive",
            "-fc", filter_codes,
            "-v",
        ]
        if extensions:
            cmd.extend(["-e", extensions])
        if inputs.get("rate"):
            cmd.extend(["-rate", str(inputs["rate"])])
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                findings.append({
                    "url": r.get("url", ""),
                    "path": r.get("input", {}).get("FUZZ", ""),
                    "status": r.get("status", 0),
                    "length": r.get("length", 0),
                    "words": r.get("words", 0),
                    "lines": r.get("lines", 0),
                    "content_type": r.get("content-type", ""),
                    "redirect_location": r.get("redirectlocation", ""),
                })
            except json.JSONDecodeError:
                continue

        return {"findings": findings, "total": len(findings)}
