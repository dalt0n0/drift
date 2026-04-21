"""Plugin registration: loads all built-in plugins into the global registry."""
from __future__ import annotations

import structlog

from app.plugins.manifest import PluginRegistry, registry

logger = structlog.get_logger(__name__)


def register_all_plugins(reg: PluginRegistry | None = None) -> PluginRegistry:
    """Register all built-in plugins.

    Args:
        reg: Registry instance. Defaults to the global singleton.

    Returns:
        The registry with all plugins registered.
    """
    if reg is None:
        reg = registry

    from app.config import get_settings

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

    # -- Web testing --
    from app.plugins.web.nuclei import NucleiPlugin
    from app.plugins.web.zap import ZAPPlugin
    from app.plugins.web.ffuf import FfufPlugin
    from app.plugins.web.feroxbuster import FeroxbusterPlugin
    from app.plugins.web.katana import KatanaPlugin
    from app.plugins.web.gobuster import GobusterPlugin
    from app.plugins.web.wapiti import WapitiPlugin
    from app.plugins.web.nikto import NiktoPlugin
    from app.plugins.web.sslyze import SslyzePlugin
    from app.plugins.web.testssl import TestsslPlugin

    # -- Network testing --
    from app.plugins.network.enum4linux_ng import Enum4linuxNgPlugin
    from app.plugins.network.netexec import NetExecPlugin
    from app.plugins.network.smbmap import SmbmapPlugin
    from app.plugins.network.ldapsearch import LdapsearchPlugin
    from app.plugins.network.onesixtyone import OnesixtyonePlugin

    plugins = [
        # passive recon
        SubfinderPlugin, AmassPlugin, AssetfinderPlugin, DnsxPlugin,
        HttpxPlugin, WaybackurlsPlugin, GauPlugin, TheHarvesterPlugin, SherlockPlugin,
        # active recon
        NmapPlugin, MasscanPlugin, NaabuPlugin, RustScanPlugin,
        # web
        NucleiPlugin, ZAPPlugin, FfufPlugin, FeroxbusterPlugin, KatanaPlugin,
        GobusterPlugin, WapitiPlugin, NiktoPlugin, SslyzePlugin, TestsslPlugin,
        # network
        Enum4linuxNgPlugin, NetExecPlugin, SmbmapPlugin, LdapsearchPlugin, OnesixtyonePlugin,
    ]

    # -- Cloud (opt-in) --
    if get_settings().ENABLE_CLOUD_MODULES:
        from app.plugins.cloud.prowler import ProwlerPlugin
        from app.plugins.cloud.scoutsuite import ScoutSuitePlugin
        from app.plugins.cloud.cloudsploit import CloudSploitPlugin
        plugins.extend([ProwlerPlugin, ScoutSuitePlugin, CloudSploitPlugin])

    for plugin_cls in plugins:
        reg.register(plugin_cls.manifest)
        logger.debug(
            "plugin.registered",
            name=plugin_cls.manifest.name,
            category=plugin_cls.manifest.category,
            intrusive=plugin_cls.manifest.is_intrusive,
        )

    passive = len([p for p in plugins if not p.manifest.is_intrusive])
    active = len([p for p in plugins if p.manifest.is_intrusive])
    logger.info("plugins.registered", total=len(plugins), passive=passive, active=active)

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
    from app.config import get_settings

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
    from app.plugins.web.nuclei import NucleiPlugin
    from app.plugins.web.zap import ZAPPlugin
    from app.plugins.web.ffuf import FfufPlugin
    from app.plugins.web.feroxbuster import FeroxbusterPlugin
    from app.plugins.web.katana import KatanaPlugin
    from app.plugins.web.gobuster import GobusterPlugin
    from app.plugins.web.wapiti import WapitiPlugin
    from app.plugins.web.nikto import NiktoPlugin
    from app.plugins.web.sslyze import SslyzePlugin
    from app.plugins.web.testssl import TestsslPlugin
    from app.plugins.network.enum4linux_ng import Enum4linuxNgPlugin
    from app.plugins.network.netexec import NetExecPlugin
    from app.plugins.network.smbmap import SmbmapPlugin
    from app.plugins.network.ldapsearch import LdapsearchPlugin
    from app.plugins.network.onesixtyone import OnesixtyonePlugin

    all_cls = [
        SubfinderPlugin, AmassPlugin, AssetfinderPlugin, DnsxPlugin,
        HttpxPlugin, WaybackurlsPlugin, GauPlugin, TheHarvesterPlugin, SherlockPlugin,
        NmapPlugin, MasscanPlugin, NaabuPlugin, RustScanPlugin,
        NucleiPlugin, ZAPPlugin, FfufPlugin, FeroxbusterPlugin, KatanaPlugin,
        GobusterPlugin, WapitiPlugin, NiktoPlugin, SslyzePlugin, TestsslPlugin,
        Enum4linuxNgPlugin, NetExecPlugin, SmbmapPlugin, LdapsearchPlugin, OnesixtyonePlugin,
    ]

    if get_settings().ENABLE_CLOUD_MODULES:
        from app.plugins.cloud.prowler import ProwlerPlugin
        from app.plugins.cloud.scoutsuite import ScoutSuitePlugin
        from app.plugins.cloud.cloudsploit import CloudSploitPlugin
        all_cls.extend([ProwlerPlugin, ScoutSuitePlugin, CloudSploitPlugin])

    for cls in all_cls:
        _PLUGIN_CLASSES[cls.manifest.name] = cls
