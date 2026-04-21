"""CVE correlation service: enriches findings with NVD, OSV, CISA KEV, and EPSS data."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_OSV_BASE = "https://api.osv.dev/v1"
_CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_EPSS_BASE = "https://api.first.org/data/v1/epss"

_HTTP_TIMEOUT = 15.0
_HTTP_HEADERS = {"User-Agent": "Drift/0.1.0 (security research; https://github.com/dalt0n0/drift)"}

# Simple in-process cache to avoid hammering external APIs during a run
_kev_cache: dict[str, bool] | None = None
_kev_fetched_at: datetime | None = None
_KEV_TTL_SECONDS = 3600


async def enrich_cve(cve_id: str) -> dict:
    """Fetch CVE details from NVD for a single CVE ID.

    Returns:
        Dict with keys: cve_id, description, cvss_score, cvss_vector,
        severity, published, references. Empty dict on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.get(_NVD_BASE, params={"cveId": cve_id})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("correlation.nvd_error", cve_id=cve_id, error=str(exc))
        return {}

    vulns = data.get("vulnerabilities", [])
    if not vulns:
        return {}

    cve_data = vulns[0].get("cve", {})

    # Description
    descriptions = cve_data.get("descriptions", [])
    description = next(
        (d["value"] for d in descriptions if d.get("lang") == "en"),
        "",
    )

    # CVSS score — prefer v3.1, fall back to v3.0 then v2
    metrics = cve_data.get("metrics", {})
    cvss_score: float | None = None
    cvss_vector: str | None = None
    severity: str = "info"

    for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(version_key, [])
        if entries:
            cvss_data = entries[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            cvss_vector = cvss_data.get("vectorString")
            severity = _nvd_severity_to_drift(
                cvss_data.get("baseSeverity", ""),
                cvss_score,
            )
            break

    references = [
        r.get("url", "") for r in cve_data.get("references", [])
    ]

    return {
        "cve_id": cve_id,
        "description": description,
        "cvss_score": cvss_score,
        "cvss_vector": cvss_vector,
        "severity": severity,
        "published": cve_data.get("published", ""),
        "references": references[:10],
    }


async def enrich_cves_batch(cve_ids: list[str]) -> dict[str, dict]:
    """Enrich multiple CVEs concurrently (max 5 parallel to respect NVD rate limits).

    Returns:
        Dict mapping cve_id -> enrichment dict.
    """
    semaphore = asyncio.Semaphore(5)

    async def _one(cve_id: str) -> tuple[str, dict]:
        async with semaphore:
            result = await enrich_cve(cve_id)
            # NVD rate limit: 6 requests / rolling 30 seconds without API key
            await asyncio.sleep(0.6)
            return cve_id, result

    tasks = [_one(cve_id) for cve_id in cve_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, dict] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning("correlation.batch_error", error=str(result))
        elif isinstance(result, tuple):
            cve_id, data = result
            output[cve_id] = data

    return output


async def query_osv(package_name: str, ecosystem: str, version: str | None = None) -> list[dict]:
    """Query OSV for vulnerabilities affecting a package.

    Args:
        package_name: Package name (e.g. "requests").
        ecosystem: Ecosystem (e.g. "PyPI", "npm", "Go", "Maven").
        version: Specific version to check (optional).

    Returns:
        List of vulnerability dicts from OSV.
    """
    payload: dict[str, Any] = {
        "package": {"name": package_name, "ecosystem": ecosystem}
    }
    if version:
        payload["version"] = version

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.post(f"{_OSV_BASE}/query", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("correlation.osv_error", package=package_name, error=str(exc))
        return []

    vulns = data.get("vulns", [])
    results = []
    for v in vulns:
        cve_ids = [alias for alias in v.get("aliases", []) if alias.startswith("CVE-")]
        results.append({
            "osv_id": v.get("id", ""),
            "summary": v.get("summary", ""),
            "severity": _osv_severity(v),
            "cve_ids": cve_ids,
            "references": [r.get("url", "") for r in v.get("references", [])][:5],
            "modified": v.get("modified", ""),
        })

    return results


async def fetch_cisa_kev() -> dict[str, bool]:
    """Fetch the CISA Known Exploited Vulnerabilities catalog.

    Returns:
        Dict mapping CVE ID -> True for all KEV entries.
        Result is cached for ``_KEV_TTL_SECONDS``.
    """
    global _kev_cache, _kev_fetched_at

    now = datetime.now(timezone.utc)
    if _kev_cache is not None and _kev_fetched_at is not None:
        age = (now - _kev_fetched_at).total_seconds()
        if age < _KEV_TTL_SECONDS:
            return _kev_cache

    try:
        async with httpx.AsyncClient(timeout=30.0, headers=_HTTP_HEADERS) as client:
            resp = await client.get(_CISA_KEV_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("correlation.kev_error", error=str(exc))
        return _kev_cache or {}

    catalog = {
        entry["cveID"]: True
        for entry in data.get("vulnerabilities", [])
        if entry.get("cveID")
    }
    _kev_cache = catalog
    _kev_fetched_at = now
    logger.info("correlation.kev_loaded", count=len(catalog))
    return catalog


async def is_kev(cve_id: str) -> bool:
    """Return True if the CVE is in the CISA KEV catalog."""
    catalog = await fetch_cisa_kev()
    return catalog.get(cve_id, False)


async def fetch_epss(cve_ids: list[str]) -> dict[str, dict]:
    """Fetch EPSS scores for a list of CVE IDs.

    Returns:
        Dict mapping cve_id -> {"score": float, "percentile": float}.
    """
    if not cve_ids:
        return {}

    # EPSS API accepts comma-separated CVE IDs
    cve_param = ",".join(cve_ids[:100])  # API limit

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.get(_EPSS_BASE, params={"cve": cve_param})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("correlation.epss_error", error=str(exc))
        return {}

    output: dict[str, dict] = {}
    for entry in data.get("data", []):
        cve_id = entry.get("cve", "")
        if cve_id:
            output[cve_id] = {
                "score": float(entry.get("epss", 0)),
                "percentile": float(entry.get("percentile", 0)),
            }

    return output


async def correlate_findings(findings: list[dict]) -> list[dict]:
    """Enrich a list of raw findings with CVE/EPSS/KEV data.

    Each finding dict must have at minimum: title, description, cve_ids (list[str]).

    Returns:
        The same list with enrichment fields added in-place:
        cvss_score, cvss_vector, epss_score, epss_percentile, cisa_kev.
    """
    # Collect all CVE IDs across all findings
    all_cves: list[str] = []
    for f in findings:
        all_cves.extend(f.get("cve_ids", []))
    unique_cves = list(dict.fromkeys(all_cves))  # deduplicate, preserve order

    if not unique_cves:
        return findings

    # Fetch NVD, EPSS, and KEV concurrently
    nvd_data, epss_data, kev_catalog = await asyncio.gather(
        enrich_cves_batch(unique_cves),
        fetch_epss(unique_cves),
        fetch_cisa_kev(),
        return_exceptions=True,
    )

    if isinstance(nvd_data, Exception):
        nvd_data = {}
    if isinstance(epss_data, Exception):
        epss_data = {}
    if isinstance(kev_catalog, Exception):
        kev_catalog = {}

    # Apply enrichment to each finding
    for finding in findings:
        cve_ids = finding.get("cve_ids", [])
        if not cve_ids:
            continue

        # Use first CVE for primary CVSS/EPSS (most findings have one)
        primary_cve = cve_ids[0]
        nvd_info = nvd_data.get(primary_cve, {})

        if nvd_info.get("cvss_score") and not finding.get("cvss_score"):
            finding["cvss_score"] = nvd_info["cvss_score"]
            finding["cvss_vector"] = nvd_info.get("cvss_vector")

        epss_info = epss_data.get(primary_cve, {})
        if epss_info and not finding.get("epss_score"):
            finding["epss_score"] = epss_info.get("score")
            finding["epss_percentile"] = epss_info.get("percentile")

        # KEV: True if ANY of the finding's CVEs are in KEV
        finding["cisa_kev"] = any(kev_catalog.get(cve, False) for cve in cve_ids)

    return findings


def _nvd_severity_to_drift(nvd_severity: str, score: float | None) -> str:
    """Map NVD severity string (or score) to Drift severity label."""
    mapping = {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
        "NONE": "info",
    }
    if nvd_severity.upper() in mapping:
        return mapping[nvd_severity.upper()]
    # Fallback: derive from score
    if score is None:
        return "info"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0:
        return "low"
    return "info"


def _osv_severity(vuln: dict) -> str:
    """Extract severity from OSV vulnerability dict."""
    severity_list = vuln.get("severity", [])
    for entry in severity_list:
        score_type = entry.get("type", "")
        if "CVSS" in score_type.upper():
            vector = entry.get("score", "")
            # Quick parse: extract base score from vector if available
            # (full calculation would require the cvss module)
            return "high"  # conservative default when we can't calculate
    return "medium"
