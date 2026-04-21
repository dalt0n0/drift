"""Tests for Phase 4 network testing plugins."""
from __future__ import annotations

import json
import sys
import types

import pytest


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

    base_mod = sys.modules["app.plugins.base"]
    if not hasattr(base_mod, "BasePlugin"):
        class BasePlugin:
            manifest = None
            def __init__(self, rate_limiter=None):
                pass
        base_mod.BasePlugin = BasePlugin

    sg_mod = sys.modules["app.plugins.scope_guard"]
    if not hasattr(sg_mod, "scope_guard"):
        sg_mod.scope_guard = lambda fn: fn

    sl = sys.modules["structlog"]
    if not hasattr(sl, "get_logger"):
        class _Logger:
            def debug(self, *a, **kw): pass
            def info(self, *a, **kw): pass
            def warning(self, *a, **kw): pass
            def error(self, *a, **kw): pass
        sl.get_logger = lambda *a, **kw: _Logger()


_ensure_stubs()

from app.plugins.tool_runner import ToolResult


def make_result(stdout: str = "", exit_code: int = 0) -> ToolResult:
    return ToolResult(stdout=stdout, stderr="", exit_code=exit_code)


def _import(module_path, cls_name):
    import importlib
    return getattr(importlib.import_module(module_path), cls_name)


# ---------------------------------------------------------------------------
# enum4linux-ng
# ---------------------------------------------------------------------------

class TestEnum4linuxNgPlugin:
    def setup_method(self):
        self.Plugin = _import("app.plugins.network.enum4linux_ng", "Enum4linuxNgPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "enum4linux-ng"
        assert p.manifest.is_intrusive is True
        assert p.manifest.safe_mode_allowed is False
        assert p.manifest.category == "network"

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["10.0.0.1"]})
        assert "enum4linux-ng" in cmd
        assert "10.0.0.1" in cmd
        assert "-oJ" in cmd

    def test_parse_output_shares(self):
        p = self.Plugin()
        data = {
            "users": {},
            "groups": {},
            "shares": {
                "IPC$": {"access": "NO ACCESS", "comment": "Remote IPC"},
                "ADMIN$": {"access": "READ WRITE", "comment": "Remote Admin"},
                "C$": {"access": "READ", "comment": "Default share"},
            },
            "os_info": {"OS": "Windows Server 2019"},
        }
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        shares = [f for f in parsed["findings"] if f.get("type") == "smb_share"]
        assert len(shares) == 3
        admin_share = next(f for f in shares if f["share"] == "ADMIN$")
        assert admin_share["severity"] == "high"

    def test_parse_output_password_policy(self):
        p = self.Plugin()
        data = {"password_policy": {"min_password_length": 4}}
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        policy = [f for f in parsed["findings"] if f.get("type") == "password_policy"]
        assert len(policy) == 1
        assert policy[0]["severity"] == "high"  # min_len < 8

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# netexec
# ---------------------------------------------------------------------------

class TestNetExecPlugin:
    def setup_method(self):
        self.Plugin = _import("app.plugins.network.netexec", "NetExecPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "netexec"
        assert p.manifest.is_intrusive is True
        assert p.manifest.binary == "nxc"

    def test_build_command_default_smb(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["10.0.0.1"]})
        assert "nxc" in cmd
        assert "smb" in cmd
        assert "10.0.0.1" in cmd

    def test_build_command_with_creds(self):
        p = self.Plugin()
        cmd = p.build_command({
            "targets": ["10.0.0.1"],
            "username": "admin",
            "password": "Password1",
        })
        assert "-u" in cmd
        assert "admin" in cmd
        assert "-p" in cmd

    def test_parse_output_pwned(self):
        p = self.Plugin()
        line = "SMB 10.0.0.1 445 WORKSTATION [+] DOMAIN\\admin:Password1 (Pwn3d!)"
        parsed = p.parse_output(make_result(line), {})
        assert parsed["total"] >= 1
        pwned = [f for f in parsed["findings"] if f.get("admin")]
        assert len(pwned) == 1
        assert pwned[0]["severity"] == "high"

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# smbmap
# ---------------------------------------------------------------------------

class TestSmbmapPlugin:
    def setup_method(self):
        self.Plugin = _import("app.plugins.network.smbmap", "SmbmapPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "smbmap"
        assert p.manifest.is_intrusive is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["10.0.0.1"]})
        assert "smbmap" in cmd
        assert "-H" in cmd
        assert "10.0.0.1" in cmd
        assert "--json" in cmd

    def test_parse_output_json(self):
        p = self.Plugin()
        data = {
            "10.0.0.1": {
                "SYSVOL": {"access": "READ ONLY", "comment": "Logon server share"},
                "NETLOGON": {"access": "READ WRITE", "comment": "Logon server share"},
                "IPC$": {"access": "NO ACCESS", "comment": ""},
            }
        }
        parsed = p.parse_output(make_result(json.dumps(data)), {})
        writable = [f for f in parsed["findings"] if f.get("can_write")]
        assert len(writable) == 1
        assert writable[0]["severity"] == "critical"
        readable = [f for f in parsed["findings"] if f.get("can_read") and not f.get("can_write")]
        assert len(readable) == 1
        assert readable[0]["severity"] == "high"

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# ldapsearch
# ---------------------------------------------------------------------------

class TestLdapsearchPlugin:
    def setup_method(self):
        self.Plugin = _import("app.plugins.network.ldapsearch", "LdapsearchPlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "ldapsearch"
        assert p.manifest.is_intrusive is True

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["10.0.0.1"], "base_dn": "dc=corp,dc=local"})
        assert "ldapsearch" in cmd
        assert "-x" in cmd
        assert "ldap://10.0.0.1" in " ".join(cmd)
        assert "dc=corp,dc=local" in cmd

    def test_parse_output_ldif(self):
        p = self.Plugin()
        ldif = (
            "dn: cn=John Doe,ou=users,dc=corp,dc=local\n"
            "objectClass: person\n"
            "cn: John Doe\n"
            "mail: john@corp.local\n"
            "\n"
            "dn: cn=admin,ou=admins,dc=corp,dc=local\n"
            "objectClass: person\n"
            "cn: admin\n"
            "\n"
        )
        parsed = p.parse_output(make_result(ldif), {})
        entries = [f for f in parsed["findings"] if f.get("type") == "ldap_entry"]
        assert len(entries) == 2
        admin_entry = next(f for f in entries if "admin" in f.get("dn", ""))
        assert admin_entry["severity"] == "high"

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0


# ---------------------------------------------------------------------------
# onesixtyone
# ---------------------------------------------------------------------------

class TestOnesixtyonePlugin:
    def setup_method(self):
        self.Plugin = _import("app.plugins.network.onesixtyone", "OnesixtyonePlugin")

    def test_manifest(self):
        p = self.Plugin()
        assert p.manifest.name == "onesixtyone"
        assert p.manifest.is_intrusive is True
        assert p.manifest.safe_mode_allowed is False

    def test_build_command(self):
        p = self.Plugin()
        cmd = p.build_command({"targets": ["10.0.0.1"]})
        assert "onesixtyone" in cmd
        assert "-c" in cmd
        assert "10.0.0.1" in cmd

    def test_parse_output_found_community(self):
        p = self.Plugin()
        stdout = "10.0.0.1 [public] Hardware: x86 - Software: Linux"
        parsed = p.parse_output(make_result(stdout), {})
        assert parsed["total"] == 1
        f = parsed["findings"][0]
        assert f["community"] == "public"
        assert f["severity"] == "critical"  # default community string

    def test_parse_output_non_default_community(self):
        p = self.Plugin()
        stdout = "10.0.0.2 [secretcommunity123] Router info"
        parsed = p.parse_output(make_result(stdout), {})
        assert parsed["total"] == 1
        assert parsed["findings"][0]["severity"] == "high"

    def test_parse_output_empty(self):
        p = self.Plugin()
        parsed = p.parse_output(make_result(""), {})
        assert parsed["total"] == 0

    def test_parse_output_skips_comments(self):
        p = self.Plugin()
        stdout = "# Scanning...\n10.0.0.1 [public] Info"
        parsed = p.parse_output(make_result(stdout), {})
        assert parsed["total"] == 1
