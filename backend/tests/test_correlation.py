"""Tests for correlation service and ATT&CK tagger."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.attack import tag_finding, technique_url
from app.core.cvss import calculate


# ---------------------------------------------------------------------------
# ATT&CK tagger
# ---------------------------------------------------------------------------

class TestAttackTagger:
    def test_sql_injection(self):
        techniques = tag_finding("SQL Injection in login form")
        assert "T1190" in techniques

    def test_xss(self):
        techniques = tag_finding("Reflected XSS via search parameter")
        assert "T1059.007" in techniques

    def test_ssrf(self):
        techniques = tag_finding("SSRF via URL parameter")
        assert "T1190" in techniques

    def test_default_credentials(self):
        techniques = tag_finding("Default credentials on admin panel")
        assert "T1078.001" in techniques or "T1078" in techniques

    def test_snmp_community(self):
        techniques = tag_finding("SNMP community string 'public' accepted")
        assert "T1046" in techniques

    def test_weak_tls(self):
        techniques = tag_finding("Weak TLS 1.0 supported")
        assert "T1600" in techniques

    def test_smb_enumeration(self):
        techniques = tag_finding("SMB null session allowed")
        assert any(t.startswith("T1021") for t in techniques)

    def test_ldap_enumeration(self):
        techniques = tag_finding("LDAP anonymous bind allowed")
        assert any(t.startswith("T1087") or t.startswith("T1018") for t in techniques)

    def test_heartbleed(self):
        techniques = tag_finding("Heartbleed vulnerability detected")
        assert "T1600" in techniques or "T1119" in techniques

    def test_directory_listing(self):
        techniques = tag_finding("Directory listing enabled at /backup/")
        assert "T1083" in techniques

    def test_csrf(self):
        techniques = tag_finding("CSRF token missing on state-changing endpoint")
        assert "T1185" in techniques

    def test_open_redirect(self):
        techniques = tag_finding("Open redirect via ?next= parameter")
        assert "T1566.002" in techniques

    def test_cloud_metadata(self):
        techniques = tag_finding("Cloud metadata service accessible via SSRF (IMDS)")
        assert "T1552.005" in techniques

    def test_s3_bucket(self):
        techniques = tag_finding("S3 bucket publicly accessible")
        assert "T1530" in techniques

    def test_subdomain_takeover(self):
        techniques = tag_finding("Subdomain takeover via dangling CNAME")
        assert "T1584.001" in techniques

    def test_uses_description(self):
        # Title alone doesn't trigger, but description does
        techniques = tag_finding(
            "Misconfiguration found",
            description="SQL injection possible in the user search field",
        )
        assert "T1190" in techniques

    def test_no_duplicates(self):
        techniques = tag_finding("SQL injection via SSRF and RCE chain")
        # T1190 appears in multiple keywords but should only appear once
        assert techniques.count("T1190") == 1

    def test_empty_finding(self):
        techniques = tag_finding("", "", "")
        assert techniques == []

    def test_technique_url_simple(self):
        url = technique_url("T1190")
        assert "T1190" in url
        assert "attack.mitre.org" in url

    def test_technique_url_subtechnique(self):
        url = technique_url("T1059.007")
        assert "T1059" in url
        assert "007" in url
        assert "attack.mitre.org" in url


# ---------------------------------------------------------------------------
# Correlation service (mocked HTTP calls)
# ---------------------------------------------------------------------------

class TestCorrelationService:
    def test_nvd_severity_mapping(self):
        from app.services.correlation import _nvd_severity_to_drift
        assert _nvd_severity_to_drift("CRITICAL", 9.5) == "critical"
        assert _nvd_severity_to_drift("HIGH", 8.0) == "high"
        assert _nvd_severity_to_drift("MEDIUM", 5.0) == "medium"
        assert _nvd_severity_to_drift("LOW", 2.0) == "low"
        assert _nvd_severity_to_drift("NONE", 0.0) == "info"

    def test_nvd_severity_fallback_from_score(self):
        from app.services.correlation import _nvd_severity_to_drift
        assert _nvd_severity_to_drift("", 9.5) == "critical"
        assert _nvd_severity_to_drift("", 7.5) == "high"
        assert _nvd_severity_to_drift("", 5.0) == "medium"
        assert _nvd_severity_to_drift("", 2.0) == "low"
        assert _nvd_severity_to_drift("", 0.0) == "info"
        assert _nvd_severity_to_drift("", None) == "info"

    def test_enrich_cve_returns_empty_on_http_error(self):
        async def run():
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
                from app.services.correlation import enrich_cve
                result = await enrich_cve("CVE-2021-44228")
                return result

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == {}

    def test_enrich_cve_parses_nvd_response(self):
        nvd_response = {
            "vulnerabilities": [{
                "cve": {
                    "id": "CVE-2021-44228",
                    "descriptions": [{"lang": "en", "value": "Log4Shell vulnerability"}],
                    "metrics": {
                        "cvssMetricV31": [{
                            "cvssData": {
                                "baseScore": 10.0,
                                "baseSeverity": "CRITICAL",
                                "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                            }
                        }]
                    },
                    "published": "2021-12-10T00:00:00.000",
                    "references": [{"url": "https://example.com/advisory"}],
                }
            }]
        }

        async def run():
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=nvd_response)

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_instance.get = AsyncMock(return_value=mock_response)

                from app.services.correlation import enrich_cve
                result = await enrich_cve("CVE-2021-44228")
                return result

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["cve_id"] == "CVE-2021-44228"
        assert result["cvss_score"] == 10.0
        assert result["severity"] == "critical"
        assert "Log4Shell" in result["description"]

    def test_fetch_cisa_kev_caches_result(self):
        import app.services.correlation as corr_mod
        # Inject a pre-populated cache
        corr_mod._kev_cache = {"CVE-2021-44228": True, "CVE-2020-1234": True}
        from datetime import datetime, timezone
        corr_mod._kev_fetched_at = datetime.now(timezone.utc)

        async def run():
            from app.services.correlation import fetch_cisa_kev
            result = await fetch_cisa_kev()
            return result

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.get("CVE-2021-44228") is True

        # Clean up
        corr_mod._kev_cache = None
        corr_mod._kev_fetched_at = None

    def test_is_kev_true(self):
        import app.services.correlation as corr_mod
        from datetime import datetime, timezone
        corr_mod._kev_cache = {"CVE-2021-44228": True}
        corr_mod._kev_fetched_at = datetime.now(timezone.utc)

        async def run():
            from app.services.correlation import is_kev
            return await is_kev("CVE-2021-44228")

        assert asyncio.get_event_loop().run_until_complete(run()) is True
        corr_mod._kev_cache = None
        corr_mod._kev_fetched_at = None

    def test_is_kev_false(self):
        import app.services.correlation as corr_mod
        from datetime import datetime, timezone
        corr_mod._kev_cache = {}
        corr_mod._kev_fetched_at = datetime.now(timezone.utc)

        async def run():
            from app.services.correlation import is_kev
            return await is_kev("CVE-9999-0000")

        assert asyncio.get_event_loop().run_until_complete(run()) is False
        corr_mod._kev_cache = None
        corr_mod._kev_fetched_at = None

    def test_fetch_epss_parses_response(self):
        epss_response = {
            "data": [
                {"cve": "CVE-2021-44228", "epss": "0.97457", "percentile": "0.99997"},
            ]
        }

        async def run():
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=epss_response)

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_instance.get = AsyncMock(return_value=mock_response)

                from app.services.correlation import fetch_epss
                result = await fetch_epss(["CVE-2021-44228"])
                return result

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "CVE-2021-44228" in result
        assert abs(result["CVE-2021-44228"]["score"] - 0.97457) < 0.0001

    def test_correlate_findings_enriches_cve(self):
        async def run():
            import app.services.correlation as corr_mod
            from datetime import datetime, timezone
            corr_mod._kev_cache = {"CVE-2021-44228": True}
            corr_mod._kev_fetched_at = datetime.now(timezone.utc)

            findings = [
                {"title": "Log4Shell", "description": "", "cve_ids": ["CVE-2021-44228"]}
            ]

            mock_nvd = {"CVE-2021-44228": {"cvss_score": 10.0, "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"}}
            mock_epss = {"CVE-2021-44228": {"score": 0.97, "percentile": 0.99}}

            with patch.object(corr_mod, "enrich_cves_batch", AsyncMock(return_value=mock_nvd)):
                with patch.object(corr_mod, "fetch_epss", AsyncMock(return_value=mock_epss)):
                    result = await corr_mod.correlate_findings(findings)
                    return result

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result[0]["cvss_score"] == 10.0
        assert result[0]["epss_score"] == 0.97
        assert result[0]["cisa_kev"] is True

        import app.services.correlation as corr_mod
        corr_mod._kev_cache = None
        corr_mod._kev_fetched_at = None

    def test_correlate_findings_no_cves(self):
        async def run():
            from app.services.correlation import correlate_findings
            findings = [{"title": "Info disclosure", "description": "", "cve_ids": []}]
            return await correlate_findings(findings)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert len(result) == 1
        # No enrichment applied — original finding returned unchanged
        assert "cvss_score" not in result[0]
