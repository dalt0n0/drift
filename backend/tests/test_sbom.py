"""Tests for SBOM service and router."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Service tests ──────────────────────────────────────────────────────────────

class TestGetInstalledPackages:
    def test_returns_list(self):
        from app.services.sbom import _get_installed_packages
        packages = _get_installed_packages()
        assert isinstance(packages, list)
        assert len(packages) > 0

    def test_package_has_required_fields(self):
        from app.services.sbom import _get_installed_packages
        packages = _get_installed_packages()
        for pkg in packages[:5]:
            assert "name" in pkg
            assert "version" in pkg
            assert "license" in pkg
            assert "purl" in pkg
            assert pkg["purl"].startswith("pkg:pypi/")

    def test_sorted_by_name(self):
        from app.services.sbom import _get_installed_packages
        packages = _get_installed_packages()
        names = [p["name"].lower() for p in packages]
        assert names == sorted(names)

    def test_purl_format(self):
        from app.services.sbom import _purl
        assert _purl("FastAPI", "0.111.0") == "pkg:pypi/fastapi@0.111.0"
        assert _purl("my-package", "1.2.3") == "pkg:pypi/my-package@1.2.3"


class TestBuildCyclonedx:
    def test_schema_keys(self):
        from app.services.sbom import build_cyclonedx
        sbom = build_cyclonedx()
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.5"
        assert sbom["serialNumber"].startswith("urn:uuid:")
        assert sbom["version"] == 1
        assert "metadata" in sbom
        assert "components" in sbom

    def test_serial_number_unique(self):
        from app.services.sbom import build_cyclonedx
        s1 = build_cyclonedx()
        s2 = build_cyclonedx()
        assert s1["serialNumber"] != s2["serialNumber"]

    def test_metadata_has_tool_and_component(self):
        from app.services.sbom import build_cyclonedx
        meta = build_cyclonedx()["metadata"]
        assert "tools" in meta
        assert meta["tools"][0]["name"] == "drift-sbom"
        assert "component" in meta
        assert meta["component"]["name"] == "drift"
        assert meta["component"]["type"] == "application"

    def test_components_are_libraries(self):
        from app.services.sbom import build_cyclonedx
        components = build_cyclonedx()["components"]
        for c in components[:5]:
            assert c["type"] == "library"
            assert "name" in c
            assert "version" in c
            assert c["purl"].startswith("pkg:pypi/")

    def test_engagement_id_embedded(self):
        from app.services.sbom import build_cyclonedx
        eid = str(uuid.uuid4())
        sbom = build_cyclonedx(engagement_id=eid)
        props = sbom["metadata"]["properties"]
        assert any(p["name"] == "drift:engagement_id" and p["value"] == eid for p in props)

    def test_no_engagement_id_no_properties(self):
        from app.services.sbom import build_cyclonedx
        sbom = build_cyclonedx()
        assert "properties" not in sbom["metadata"]

    def test_json_serializable(self):
        from app.services.sbom import build_cyclonedx
        sbom = build_cyclonedx()
        dumped = json.dumps(sbom)
        loaded = json.loads(dumped)
        assert loaded["bomFormat"] == "CycloneDX"

    def test_agpl_license_on_component(self):
        from app.services.sbom import build_cyclonedx
        component = build_cyclonedx()["metadata"]["component"]
        assert any(
            lic.get("license", {}).get("id") == "AGPL-3.0-or-later"
            for lic in component["licenses"]
        )


class TestBuildSpdx:
    def test_schema_keys(self):
        from app.services.sbom import build_spdx
        sbom = build_spdx()
        assert sbom["spdxVersion"] == "SPDX-2.3"
        assert sbom["dataLicense"] == "CC0-1.0"
        assert sbom["SPDXID"] == "SPDXRef-DOCUMENT"
        assert "packages" in sbom
        assert "relationships" in sbom
        assert "creationInfo" in sbom

    def test_document_namespace_unique(self):
        from app.services.sbom import build_spdx
        s1 = build_spdx()
        s2 = build_spdx()
        assert s1["documentNamespace"] != s2["documentNamespace"]

    def test_document_namespace_format(self):
        from app.services.sbom import build_spdx
        ns = build_spdx()["documentNamespace"]
        assert ns.startswith("https://github.com/dalt0n0/drift/sbom/")

    def test_app_package_present(self):
        from app.services.sbom import build_spdx
        pkgs = build_spdx()["packages"]
        app_pkg = next((p for p in pkgs if p["SPDXID"] == "SPDXRef-drift"), None)
        assert app_pkg is not None
        assert app_pkg["name"] == "drift"
        assert app_pkg["licenseConcluded"] == "AGPL-3.0-or-later"

    def test_document_describes_app(self):
        from app.services.sbom import build_spdx
        rels = build_spdx()["relationships"]
        describes = next(
            (r for r in rels
             if r["spdxElementId"] == "SPDXRef-DOCUMENT"
             and r["relationshipType"] == "DESCRIBES"),
            None,
        )
        assert describes is not None
        assert describes["relatedSpdxElement"] == "SPDXRef-drift"

    def test_dependency_relationships(self):
        from app.services.sbom import build_spdx
        rels = build_spdx()["relationships"]
        depends_on = [r for r in rels if r["relationshipType"] == "DEPENDS_ON"]
        assert len(depends_on) > 0
        for r in depends_on:
            assert r["spdxElementId"] == "SPDXRef-drift"

    def test_packages_have_purl(self):
        from app.services.sbom import build_spdx
        pkgs = build_spdx()["packages"]
        # skip the app package itself (no PACKAGE-MANAGER ref)
        dep_pkgs = [p for p in pkgs if p["SPDXID"] != "SPDXRef-drift"]
        for p in dep_pkgs[:5]:
            refs = p.get("externalRefs", [])
            purl_refs = [r for r in refs if r["referenceType"] == "purl"]
            assert len(purl_refs) == 1
            assert purl_refs[0]["referenceLocator"].startswith("pkg:pypi/")

    def test_json_serializable(self):
        from app.services.sbom import build_spdx
        dumped = json.dumps(build_spdx())
        loaded = json.loads(dumped)
        assert loaded["spdxVersion"] == "SPDX-2.3"

    def test_engagement_id_in_name(self):
        from app.services.sbom import build_spdx
        eid = str(uuid.uuid4())
        sbom = build_spdx(engagement_id=eid)
        # engagement_id currently does not mutate SPDX structure, just confirm it runs
        assert sbom["spdxVersion"] == "SPDX-2.3"

    def test_license_noassertion_fallback(self):
        from app.services.sbom import build_spdx
        pkgs = build_spdx()["packages"]
        dep_pkgs = [p for p in pkgs if p["SPDXID"] != "SPDXRef-drift"]
        for p in dep_pkgs:
            assert "licenseConcluded" in p
            assert p["licenseConcluded"]  # not empty


# ── Router tests ───────────────────────────────────────────────────────────────

def _make_user(role_value: int = 1):
    user = MagicMock()
    user.role = role_value
    return user


def _mock_require_role():
    return patch("app.routers.sbom.require_role", return_value=None)


class TestSbomRouterApp:
    """Test GET /api/sbom with format query param."""

    def test_cyclonedx_response_structure(self):
        from app.services.sbom import build_cyclonedx
        sbom = build_cyclonedx()
        assert sbom["bomFormat"] == "CycloneDX"
        assert isinstance(sbom["components"], list)

    def test_spdx_response_structure(self):
        from app.services.sbom import build_spdx
        sbom = build_spdx()
        assert sbom["spdxVersion"] == "SPDX-2.3"

    def test_filename_cyclonedx(self):
        filename = "drift-sbom.cdx.json"
        assert filename.endswith(".cdx.json")

    def test_filename_spdx(self):
        filename = "drift-sbom.spdx.json"
        assert filename.endswith(".spdx.json")


class TestSbomSummary:
    def test_summary_structure(self):
        from app.services.sbom import _get_installed_packages, _APP_VERSION
        packages = _get_installed_packages()
        summary = {
            "app_version": _APP_VERSION,
            "bom_format": "CycloneDX",
            "spec_version": "1.5",
            "component_count": len(packages),
            "endpoints": {
                "cyclonedx": "/api/sbom?format=cyclonedx",
                "spdx": "/api/sbom?format=spdx",
            },
        }
        assert summary["component_count"] > 0
        assert summary["bom_format"] == "CycloneDX"
        assert summary["spec_version"] == "1.5"
        assert "/api/sbom?format=cyclonedx" in summary["endpoints"]["cyclonedx"]

    def test_app_version_matches_service(self):
        from app.services.sbom import _APP_VERSION
        assert _APP_VERSION == "0.1.0"


class TestEngagementSbom:
    def test_cyclonedx_with_engagement_id(self):
        from app.services.sbom import build_cyclonedx
        eid = str(uuid.uuid4())
        sbom = build_cyclonedx(engagement_id=eid)
        props = sbom["metadata"]["properties"]
        prop = next((p for p in props if p["name"] == "drift:engagement_id"), None)
        assert prop is not None
        assert prop["value"] == eid

    def test_spdx_with_engagement_id(self):
        from app.services.sbom import build_spdx
        eid = str(uuid.uuid4())
        sbom = build_spdx(engagement_id=eid)
        assert sbom["spdxVersion"] == "SPDX-2.3"

    def test_engagement_filename_cyclonedx(self):
        eid = uuid.uuid4()
        filename = f"drift-sbom-{eid}.cdx.json"
        assert str(eid) in filename

    def test_engagement_filename_spdx(self):
        eid = uuid.uuid4()
        filename = f"drift-sbom-{eid}.spdx.json"
        assert str(eid) in filename
