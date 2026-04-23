"""ffuf: fast web fuzzer for directory and parameter discovery."""
from __future__ import annotations

import json
import os
import tempfile

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult

_WORDLIST_CANDIDATES = [
    "/usr/share/seclists/Discovery/Web-Content/common.txt",
    "/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt",
    "/usr/share/dirb/wordlists/common.txt",
    "/usr/share/wordlists/dirb/common.txt",
    "/opt/drift/wordlists/minimal.txt",  # baked into tools container as fallback
]

# Minimal built-in wordlist used when no system wordlist is available
_BUILTIN_WORDS = [
    ".env", ".git", ".htaccess", ".htpasswd", "admin", "api", "api/v1", "api/v2",
    "backup", "backups", "cgi-bin", "config", "console", "dashboard", "debug",
    "dev", "docs", "download", "env", "graphql", "health", "images", "includes",
    "index.php", "info.php", "js", "login", "logout", "metrics", "panel", "phpmyadmin",
    "server-status", "setup", "staging", "static", "status", "swagger", "swagger-ui",
    "swagger-ui.html", "test", "upload", "uploads", "v1", "v2", "web.config",
    "wp-admin", "wp-login.php", "xmlrpc.php",
]


def _find_wordlist() -> str | None:
    for path in _WORDLIST_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def _write_builtin_wordlist() -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir="/tmp")
    f.write("\n".join(_BUILTIN_WORDS) + "\n")
    f.close()
    return f.name


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
        wordlist = inputs.get("wordlist") or _find_wordlist()
        if not wordlist:
            wordlist = _write_builtin_wordlist()
            self._builtin_wordlist = wordlist
        filter_codes = inputs.get("filter_codes", "404,400,403")
        extensions = inputs.get("extensions", "")

        # Append FUZZ keyword to target URL
        url = target.rstrip("/") + "/FUZZ"

        # Use /tmp output file so ffuf can write JSON (it appends extension)
        self._output_file = tempfile.mktemp(suffix=".json", dir="/tmp")

        cmd = [
            "ffuf",
            "-u", url,
            "-w", wordlist,
            "-of", "json",
            "-o", self._output_file,
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

        # Try to read from temp output file first
        output_file = getattr(self, "_output_file", None)
        raw = ""
        if output_file and os.path.isfile(output_file):
            try:
                with open(output_file) as f:
                    raw = f.read().strip()
                os.unlink(output_file)
            except OSError:
                pass

        builtin_wl = getattr(self, "_builtin_wordlist", None)
        if builtin_wl and os.path.isfile(builtin_wl):
            try:
                os.unlink(builtin_wl)
            except OSError:
                pass

        if not raw:
            raw = result.stdout.strip()

        if not raw:
            return {"findings": [], "total": 0}

        try:
            data = json.loads(raw)
            results = data.get("results", [])
            for r in results:
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
            # Try JSONL
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    findings.append({
                        "url": r.get("url", ""),
                        "status": r.get("status", 0),
                        "length": r.get("length", 0),
                    })
                except json.JSONDecodeError:
                    continue

        return {"findings": findings, "total": len(findings)}
