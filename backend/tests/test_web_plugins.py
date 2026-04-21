"""Tests for Phase 4 web testing plugins."""
from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal stub imports so we can import plugin modules without full app stack
# ---------------------------------------------------------------------------

def _stub_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stubs() -> None:
    stubs = [
        "structlog", "minio", "app", "app.config", "app.plugins",
        "app.plugins.manifest", "app.plugins.tool_runner",
        "app.plugins.rate_limiter", "app.plugins.scope_guard",
        "app.plugins.base",
    ]
    for s in stubs:
        if s not in sys.modules:
            _stub_module(s)

    # PluginManifest stub
    manifest_mod = sys.modules["app.plugins.manifest"]
    if not hasattr(manifest_mod, "PluginManifest"):
        from dataclasses import dataclass, field

        @dataclass(frozen=True)
        class PluginManifest:
            name: str
            version: str
            category: str
            is_intrusive: bool
            binary: str
            inputs: list = field(default_factory=list)
            outputs: list = field(default_factory=list)
            dependencies: list = field(default_factory=list)
            rate_limit: int = 0
            timeout_seconds: int = 300
            safe_mode_allowed: bool = True

        manifest_mod.PluginManifest = PluginManifest

    # ToolResult stub
    tool_runner_mod = sys.modules["app.plugins.tool_runner"]
    if not hasattr(tool_runner_mod, "ToolResult"):
        from dataclasses import dataclass

        @dataclass
        class ToolResult:
            stdout: str = ""
            stderr: str = ""
            exit_code: int = 0
            timed_out: bool = False
            duration_seconds: float = 0.0

        tool_runner_mod.ToolResult = ToolResult

    # BasePlugin stub
    base_mod = sys.modules["app.plugins.base"]
    if not hasattr(base_mod, "BasePlugin"):
        class BasePlugin:
            manifest = None
            def __init__(self, rate_limiter=None):
                pass
        base_mod.BasePlugin = BasePlugin

    # scope_guard stub (no-op decorator)
    sg_mod = sys.modules["app.plugins.scope_guard"]
    if not hasattr(sg_mod, "scope_guard"):
        def scope_guard(fn):
            return fn
        sg_mod.scope_guard = scope_guard

    # structlog stub
    sl = sys.modules["structlog"]
    if not hasattr(sl, "get_logger"):
        class _Logger:
            def debug(self, *a, **kw): pass
            def info(self, *a, **kw): pass
            def warning(self, *a, **kw): pass
            def error(self, *a, **kw): pass
        sl.get_logger = lambda *a, **kw: _Logger()


_ensure_stubs()

# ---------------------------------------------------------------------------
# Import plugins (after stubs are in place)
# ---------------------------------------------------------------------------

from app.plugins.manifest import PluginManifest  # noqa: E402
from app.plugins.tool_runner import ToolResult  # noqa: E402


def _import_plugin(module_path: str, cls_name: str):
    """Import a plugin class, injecting stubs as needed."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(stdout: str = "", exit_code: int = 0) -> ToolResult:
    return ToolResult(stdout=stdout, stderr="", exit_code=exit_code)


# ---------------------------------------------------------------------------
# Nuclei
# ---------------------------------------------------------------------------

class TestNucleiPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.nuclei", "NucleiPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "nuclei"
        assert p.manifest.is_intrusive is True
        assert p.manifest.safe_mode_allowed is False
        assert p.manifest.category == "web"
        assert "httpx" in p.manifest.dependencies

    def test_build_command_single_target(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"]})
        assert "nuclei" in cmd
        assert "-u" in cmd
        assert "https://example.com" in cmd
        assert "-json" in cmd

    def test_build_command_multiple_targets(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://a.com", "https://b.com"]})
        assert cmd.count("-u") == 2

    def test_parse_output_valid_json(self):
        p = self.Plugin()
        finding = {
            "template-id": "cve-2021-1234",
            "info": {"name": "Test CVE", "severity": "high", "description": "desc"},
            "matched-at": "https://example.com/path",
            "host": "example.com",
            "ip": "1.2.3.4",
            "type": "http",
        }
        result = make_result(json.dumps(finding))
        parsed = p.parse_output(result, {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["severity"] == "high"
        assert parsed["findings"][0]["name"] == "Test CVE"
        assert parsed["by_severity"]["high"] == 1

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0
        assert parsed["findings"] == []

    def test_parse_output_invalid_json_lines_skipped(self):
        p = self.Plugin()
        stdout = "not json\n" + json.dumps({
            "template-id": "x",
            "info": {"name": "X", "severity": "low"},
            "matched-at": "http://x.com",
        })
        parsed = p.parse_output(make_result(stdout), {})
        assert parsed["total"] == 1


# ---------------------------------------------------------------------------
# ZAP
# ---------------------------------------------------------------------------

class TestZAPPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.zap", "ZAPPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "zap"
        assert p.manifest.is_intrusive is True
        assert p.manifest.timeout_seconds == 1800
        assert p.manifest.rate_limit == 1

    def test_build_command_passive(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"]})
        assert "zap-baseline.py" in cmd or "zap-baseline.py" in " ".join(cmd)
        assert "https://example.com" in cmd

    def test_build_command_active(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"], "active_scan": True})
        assert "zap-full-scan.py" in cmd or "full" in " ".join(cmd)

    def test_parse_output_zap_json(self):
        p = self.Plugin()
        report = {
            "site": [{
                "alerts": [{
                    "name": "X-Frame-Options Header Not Set",
                    "riskcode": "2",
                    "confidence": "2",
                    "desc": "desc",
                    "solution": "Add header",
                    "instances": [{"uri": "http://x.com", "method": "GET", "evidence": ""}],
                }]
            }]
        }
        parsed = p.parse_output(make_result(json.dumps(report)), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["severity"] == "medium"

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# ffuf
# ---------------------------------------------------------------------------

class TestFfufPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.ffuf", "FfufPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "ffuf"
        assert p.manifest.is_intrusive is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"]})
        assert "ffuf" in cmd
        assert "-u" in cmd
        assert "FUZZ" in " ".join(cmd)
        assert "-of" in cmd

    def test_parse_output_json(self):
        p = self.Plugin()
        output = {
            "results": [
                {"url": "https://example.com/admin", "status": 200, "length": 1234,
                 "words": 10, "lines": 5, "content-type": "text/html",
                 "input": {"FUZZ": "admin"}, "redirectlocation": ""},
            ]
        }
        parsed = p.parse_output(make_result(json.dumps(output)), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["status"] == 200

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# katana
# ---------------------------------------------------------------------------

class TestKatanaPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.katana", "KatanaPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "katana"
        assert p.manifest.is_intrusive is False
        assert p.manifest.safe_mode_allowed is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"], "depth": 5})
        assert "katana" in cmd
        assert "-depth" in cmd
        assert "5" in cmd
        assert "-json" in cmd

    def test_parse_output_json(self):
        p = self.Plugin()
        line = json.dumps({"endpoint": "https://example.com/api", "source": "katana",
                           "request": {"method": "GET"}})
        parsed = p.parse_output(make_result(line), {})
        assert parsed["total"] == 1
        assert parsed["urls"][0]["url"] == "https://example.com/api"

    def test_parse_output_plain_url(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result("https://example.com/page"), {})
        assert parsed["total"] == 1


# ---------------------------------------------------------------------------
# gobuster
# ---------------------------------------------------------------------------

class TestGobusterPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.gobuster", "GobusterPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "gobuster"
        assert p.manifest.is_intrusive is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["https://example.com"]})
        assert "gobuster" in cmd
        assert "dir" in cmd

    def test_parse_output(self):
        p = self.Plugin()
        stdout = "/admin (Status: 200) [Size: 4321]\n/login (Status: 301) [Size: 0]"
        parsed = p.parse_output(
            make_result(stdout), {"targets": ["https://example.com"]}
        )
        assert parsed["total"] == 2
        assert parsed["findings"][0]["path"] == "/admin"
        assert parsed["findings"][0]["status"] == 200
        assert parsed["findings"][0]["size"] == 4321


# ---------------------------------------------------------------------------
# sslyze
# ---------------------------------------------------------------------------

class TestSslyzePlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.sslyze", "SslyzePlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "sslyze"
        assert p.manifest.is_intrusive is False
        assert p.manifest.safe_mode_allowed is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["example.com"]})
        assert "sslyze" in cmd
        assert "--json_out=-" in cmd
        assert "example.com" in cmd

    def test_parse_output_weak_protocol(self):
        p = self.Plugin()
        data = {
            "server_scan_results": [{
                "server_location": {"hostname": "example.com", "port": 443},
                "scan_result": {
                    "tls_1_0_cipher_suites": {
                        "result": {"accepted_cipher_suites": [{"cipher_suite": {"name": "RC4-SHA"}}]}
                    }
                },
            }]
        }
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        assert parsed["total"] >= 1
        weak = [f for f in parsed["findings"] if f.get("type") == "weak_protocol"]
        assert len(weak) == 1
        assert weak[0]["severity"] == "high"


# ---------------------------------------------------------------------------
# testssl
# ---------------------------------------------------------------------------

class TestTestsslPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.testssl", "TestsslPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "testssl"
        assert p.manifest.is_intrusive is False
        assert p.manifest.safe_mode_allowed is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["example.com:443"]})
        assert "testssl.sh" in cmd
        assert "--quiet" in cmd
        assert "--fast" in cmd

    def test_parse_output_filters_ok(self):
        p = self.Plugin()
        entries = [
            {"id": "TLS1", "ip": "1.2.3.4", "port": "443", "finding": "TLSv1.0 offered",
             "severity": "MEDIUM", "cve": "", "cwe": ""},
            {"id": "cert_ok", "ip": "1.2.3.4", "port": "443", "finding": "yes",
             "severity": "OK", "cve": "", "cwe": ""},
        ]
        parsed = p.parse_output(make_result(json.dumps(entries)), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["severity"] == "medium"


# ---------------------------------------------------------------------------
# feroxbuster
# ---------------------------------------------------------------------------

class TestFeroxbusterPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.feroxbuster", "FeroxbusterPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "feroxbuster"
        assert p.manifest.is_intrusive is True

    def test_parse_output_jsonl(self):
        p = self.Plugin()
        lines = [
            json.dumps({"type": "response", "url": "https://example.com/admin",
                        "status": 200, "content_length": 100, "word_count": 10,
                        "line_count": 5, "method": "GET", "extension": ""}),
            json.dumps({"type": "summary"}),
        ]
        parsed = p.parse_output(make_result("\n".join(lines)), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["url"] == "https://example.com/admin"


# ---------------------------------------------------------------------------
# wapiti
# ---------------------------------------------------------------------------

class TestWapitiPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.wapiti", "WapitiPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "wapiti"
        assert p.manifest.is_intrusive is True
        assert p.manifest.timeout_seconds == 900

    def test_parse_output(self):
        p = self.Plugin()
        data = {
            "vulnerabilities": {
                "SQL Injection": [
                    {"level": 3, "path": "/search", "parameter": "q",
                     "info": "SQL injection detected", "http_request": "GET /search?q=' HTTP/1.1",
                     "curl_command": "curl ...", "wstg": ["WSTG-INPV-05"]},
                ]
            }
        }
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["severity"] == "high"
        assert parsed["findings"][0]["name"] == "SQL Injection"


# ---------------------------------------------------------------------------
# nikto
# ---------------------------------------------------------------------------

class TestNiktoPlugin:
    def setup_method(self):
        self.Plugin = _import_plugin("app.plugins.web.nikto", "NiktoPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "nikto"
        assert p.manifest.is_intrusive is True

    def test_parse_output_json(self):
        p = self.Plugin()
        data = {
            "vulnerabilities": [
                {"id": "123", "OSVDB": "OSVDB-0", "method": "GET",
                 "url": "/", "msg": "Server version disclosed"},
            ]
        }
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        assert parsed["total"] == 1
        assert "Server version" in parsed["findings"][0]["msg"]
