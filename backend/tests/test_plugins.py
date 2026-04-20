"""Tests for plugin registration and manifest validation."""
from __future__ import annotations

import pytest

from app.plugins.manifest import PluginManifest, PluginRegistry


class TestPluginRegistration:
    """Test that all recon plugins register correctly."""

    def test_register_all_plugins(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        all_plugins = reg.list_all()
        assert len(all_plugins) == 13  # 9 passive + 4 active

    def test_passive_plugins_count(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        passive = [p for p in reg.list_all() if not p.is_intrusive]
        assert len(passive) == 9

    def test_active_plugins_count(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        active = reg.list_intrusive()
        assert len(active) == 4

    def test_safe_mode_excludes_intrusive(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        safe = reg.list_safe_mode()
        for p in safe:
            assert p.safe_mode_allowed is True
            assert p.is_intrusive is False

    def test_all_plugins_have_binary(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        for p in reg.list_all():
            assert p.binary, f"Plugin {p.name} missing binary"

    def test_all_plugins_have_version(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        for p in reg.list_all():
            assert p.version, f"Plugin {p.name} missing version"

    def test_all_plugins_have_category(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        categories = {p.category for p in reg.list_all()}
        assert "recon" in categories
        assert "scanning" in categories

    def test_topological_sort_respects_dependencies(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        # dnsx depends on subfinder; httpx depends on subfinder
        order = reg.topological_sort()
        names = order
        idx_subfinder = names.index("subfinder")
        idx_dnsx = names.index("dnsx")
        idx_httpx = names.index("httpx")
        assert idx_subfinder < idx_dnsx
        assert idx_subfinder < idx_httpx

    def test_nmap_depends_on_httpx(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        order = reg.topological_sort()
        idx_httpx = order.index("httpx")
        idx_nmap = order.index("nmap")
        assert idx_httpx < idx_nmap

    def test_get_plugin_class(self):
        from app.plugins.registry import get_plugin_class

        cls = get_plugin_class("subfinder")
        assert cls is not None
        assert cls.manifest.name == "subfinder"

    def test_get_plugin_class_unknown(self):
        from app.plugins.registry import get_plugin_class

        cls = get_plugin_class("nonexistent")
        assert cls is None

    def test_execution_plan_safe_mode(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        all_names = [p.name for p in reg.list_all()]
        plan = reg.get_execution_plan(all_names, safe_mode=True)

        for p in plan:
            assert p.is_intrusive is False

    def test_execution_plan_full(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        all_names = [p.name for p in reg.list_all()]
        plan = reg.get_execution_plan(all_names, safe_mode=False)

        assert len(plan) == 13

    def test_plugin_manifests_are_frozen(self):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        p = reg.get("subfinder")
        with pytest.raises(AttributeError):
            p.name = "modified"  # type: ignore


class TestPluginManifestFields:
    """Test specific plugin manifest configurations."""

    @pytest.mark.parametrize(
        "name,expected_intrusive,expected_safe",
        [
            ("subfinder", False, True),
            ("amass", False, True),
            ("assetfinder", False, True),
            ("dnsx", False, True),
            ("httpx", False, True),
            ("waybackurls", False, True),
            ("gau", False, True),
            ("theharvester", False, True),
            ("sherlock", False, True),
            ("nmap", True, False),
            ("masscan", True, False),
            ("naabu", True, False),
            ("rustscan", True, False),
        ],
    )
    def test_intrusive_and_safe_mode(self, name, expected_intrusive, expected_safe):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        p = reg.get(name)
        assert p.is_intrusive is expected_intrusive
        assert p.safe_mode_allowed is expected_safe

    @pytest.mark.parametrize(
        "name,expected_category",
        [
            ("subfinder", "recon"),
            ("nmap", "scanning"),
            ("masscan", "scanning"),
        ],
    )
    def test_categories(self, name, expected_category):
        from app.plugins.registry import register_all_plugins

        reg = PluginRegistry()
        register_all_plugins(reg)

        p = reg.get(name)
        assert p.category == expected_category
