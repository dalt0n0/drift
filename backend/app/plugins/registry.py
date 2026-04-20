"""Plugin registration: loads all built-in plugins into the global registry."""
from __future__ import annotations

import structlog

from app.plugins.manifest import PluginRegistry, registry

logger = structlog.get_logger(__name__)


def register_all_plugins(reg: PluginRegistry | None = None) -> PluginRegistry:
    """Register all built-in recon plugins.

    Args:
        reg: Registry instance. Defaults to the global singleton.

    Returns:
        The registry with all plugins registered.
    """
    if reg is None:
        reg = registry

    # -- Passive recon --
    from app.plugins.recon.subfinder import SubfinderPlugin
    from app.plugins.recon.amass import AmassPlugin
    from app.plugins.recon.assetfinder import AssetfinderPlugin
    from app.plugins.recon.dnsx import DnsxPlugin
    from app.plugins.recon.httpx import HttpxPlugin
    from app.plugins.recon.waybackurls import WaybackurlsPlugin
    from app.plugins.recon.gau import GauPlugin
    from app.plugins.recon.theharvester import TheHarvesterPlugin
    from app.plugins.recon.sherlock import SherlockPlugin

    # -- Active recon --
    from app.plugins.recon.nmap import NmapPlugin
    from app.plugins.recon.masscan import MasscanPlugin
    from app.plugins.recon.naabu import NaabuPlugin
    from app.plugins.recon.rustscan import RustScanPlugin

    plugins = [
        SubfinderPlugin,
        AmassPlugin,
        AssetfinderPlugin,
        DnsxPlugin,
        HttpxPlugin,
        WaybackurlsPlugin,
        GauPlugin,
        TheHarvesterPlugin,
        SherlockPlugin,
        NmapPlugin,
        MasscanPlugin,
        NaabuPlugin,
        RustScanPlugin,
    ]

    for plugin_cls in plugins:
        reg.register(plugin_cls.manifest)
        logger.debug(
            "plugin.registered",
            name=plugin_cls.manifest.name,
            category=plugin_cls.manifest.category,
            intrusive=plugin_cls.manifest.is_intrusive,
        )

    logger.info(
        "plugins.registered",
        total=len(plugins),
        passive=len([p for p in plugins if not p.manifest.is_intrusive]),
        active=len([p for p in plugins if p.manifest.is_intrusive]),
    )

    return reg


# Plugin class lookup by name
_PLUGIN_CLASSES: dict[str, type] = {}


def get_plugin_class(name: str) -> type | None:
    """Get the plugin class by manifest name."""
    if not _PLUGIN_CLASSES:
        _load_plugin_classes()
    return _PLUGIN_CLASSES.get(name)


def _load_plugin_classes() -> None:
    """Lazily load all plugin classes into the lookup dict."""
    from app.plugins.recon.subfinder import SubfinderPlugin
    from app.plugins.recon.amass import AmassPlugin
    from app.plugins.recon.assetfinder import AssetfinderPlugin
    from app.plugins.recon.dnsx import DnsxPlugin
    from app.plugins.recon.httpx import HttpxPlugin
    from app.plugins.recon.waybackurls import WaybackurlsPlugin
    from app.plugins.recon.gau import GauPlugin
    from app.plugins.recon.theharvester import TheHarvesterPlugin
    from app.plugins.recon.sherlock import SherlockPlugin
    from app.plugins.recon.nmap import NmapPlugin
    from app.plugins.recon.masscan import MasscanPlugin
    from app.plugins.recon.naabu import NaabuPlugin
    from app.plugins.recon.rustscan import RustScanPlugin

    for cls in [
        SubfinderPlugin, AmassPlugin, AssetfinderPlugin, DnsxPlugin,
        HttpxPlugin, WaybackurlsPlugin, GauPlugin, TheHarvesterPlugin,
        SherlockPlugin, NmapPlugin, MasscanPlugin, NaabuPlugin, RustScanPlugin,
    ]:
        _PLUGIN_CLASSES[cls.manifest.name] = cls
