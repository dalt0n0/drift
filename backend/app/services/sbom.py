"""SBOM service: builds CycloneDX 1.5 SBOM from installed packages."""
from __future__ import annotations

import importlib.metadata
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_APP_VERSION = "0.1.0"
_PYPI_LICENSE_URL = "https://pypi.org/project/{name}/{version}/"


def _purl(name: str, version: str) -> str:
    """Build a Package URL (PURL) for a PyPI package."""
    return f"pkg:pypi/{name.lower()}@{version}"


def _get_installed_packages() -> list[dict]:
    """Enumerate all installed Python packages via importlib.metadata."""
    packages = []
    for dist in importlib.metadata.distributions():
        meta = dist.metadata
        name = meta.get("Name", "")
        version = meta.get("Version", "")
        if not name or not version:
            continue
        license_expr = (
            meta.get("License-Expression")
            or meta.get("License")
            or "NOASSERTION"
        )
        # Truncate very long license blobs (sometimes entire license text is embedded)
        if len(license_expr) > 128:
            license_expr = license_expr[:128].strip() + "..."
        home_page = (
            meta.get("Home-page")
            or meta.get("Project-URL", "")
            or ""
        )
        # Project-URL can be "Source Code, https://..." — extract the URL
        if "," in home_page and not home_page.startswith("http"):
            home_page = home_page.split(",", 1)[1].strip()
        packages.append({
            "name": name,
            "version": version,
            "license": license_expr,
            "purl": _purl(name, version),
            "home_page": home_page,
        })
    packages.sort(key=lambda p: p["name"].lower())
    return packages


def build_cyclonedx(engagement_id: str | None = None) -> dict:
    """Build a CycloneDX 1.5 SBOM document from the current Python environment.

    Args:
        engagement_id: Optional engagement UUID to embed in the SBOM metadata.

    Returns:
        CycloneDX 1.5 SBOM as a Python dict (JSON-serialisable).
    """
    packages = _get_installed_packages()
    components: list[dict] = []

    for pkg in packages:
        component: dict[str, Any] = {
            "type": "library",
            "name": pkg["name"],
            "version": pkg["version"],
            "purl": pkg["purl"],
        }
        if pkg["license"] and pkg["license"] != "NOASSERTION":
            component["licenses"] = [{"license": {"name": pkg["license"]}}]
        if pkg["home_page"]:
            component["externalReferences"] = [
                {"type": "website", "url": pkg["home_page"]}
            ]
        components.append(component)

    metadata: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tools": [
            {
                "vendor": "Drift",
                "name": "drift-sbom",
                "version": _APP_VERSION,
                "externalReferences": [
                    {"type": "website", "url": "https://github.com/dalt0n0/drift"}
                ],
            }
        ],
        "component": {
            "type": "application",
            "bom-ref": f"drift-{_APP_VERSION}",
            "name": "drift",
            "version": _APP_VERSION,
            "description": "Open-source automated penetration testing platform",
            "licenses": [{"license": {"id": "AGPL-3.0-or-later"}}],
            "externalReferences": [
                {"type": "vcs", "url": "https://github.com/dalt0n0/drift"},
                {"type": "website", "url": "https://github.com/dalt0n0/drift"},
            ],
        },
    }
    if engagement_id:
        metadata["properties"] = [
            {"name": "drift:engagement_id", "value": engagement_id}
        ]

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": metadata,
        "components": components,
    }

    logger.info(
        "sbom.generated",
        component_count=len(components),
        engagement_id=engagement_id,
    )
    return sbom


def build_spdx(engagement_id: str | None = None) -> dict:
    """Build an SPDX 2.3 SBOM document from the current Python environment.

    Returns:
        SPDX 2.3 SBOM as a Python dict (JSON-serialisable).
    """
    packages = _get_installed_packages()
    now = datetime.now(timezone.utc).isoformat()

    spdx_packages: list[dict] = []
    relationships: list[dict] = []
    doc_ref = "SPDXRef-DOCUMENT"
    app_ref = "SPDXRef-drift"

    for pkg in packages:
        pkg_ref = f"SPDXRef-{pkg['name'].replace('-', '_').replace('.', '_')}-{pkg['version'].replace('.', '_')}"
        spdx_pkg: dict[str, Any] = {
            "SPDXID": pkg_ref,
            "name": pkg["name"],
            "versionInfo": pkg["version"],
            "downloadLocation": f"https://pypi.org/project/{pkg['name']}/{pkg['version']}/",
            "filesAnalyzed": False,
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": pkg["purl"],
                }
            ],
        }
        if pkg["license"] and pkg["license"] != "NOASSERTION":
            spdx_pkg["licenseConcluded"] = pkg["license"]
            spdx_pkg["licenseDeclared"] = pkg["license"]
        else:
            spdx_pkg["licenseConcluded"] = "NOASSERTION"
            spdx_pkg["licenseDeclared"] = "NOASSERTION"
        spdx_packages.append(spdx_pkg)
        relationships.append({
            "spdxElementId": app_ref,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": pkg_ref,
        })

    # The application package itself
    app_package: dict[str, Any] = {
        "SPDXID": app_ref,
        "name": "drift",
        "versionInfo": _APP_VERSION,
        "downloadLocation": "https://github.com/dalt0n0/drift",
        "filesAnalyzed": False,
        "licenseConcluded": "AGPL-3.0-or-later",
        "licenseDeclared": "AGPL-3.0-or-later",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:github/dalt0n0/drift@{_APP_VERSION}",
            }
        ],
    }

    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": doc_ref,
        "name": f"drift-sbom-{_APP_VERSION}",
        "documentNamespace": f"https://github.com/dalt0n0/drift/sbom/{uuid.uuid4()}",
        "creationInfo": {
            "created": now,
            "creators": [
                f"Tool: drift-sbom-{_APP_VERSION}",
                "Organization: Drift",
            ],
            "licenseListVersion": "3.22",
        },
        "packages": [app_package] + spdx_packages,
        "relationships": [
            {
                "spdxElementId": doc_ref,
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": app_ref,
            }
        ] + relationships,
    }

    logger.info("sbom.spdx_generated", package_count=len(spdx_packages))
    return sbom
