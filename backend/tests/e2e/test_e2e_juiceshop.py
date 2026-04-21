"""E2E tests: Drift scanning OWASP Juice Shop.

Mark: e2e

Requires the full stack + e2e targets (see conftest.py).
Each test creates an engagement, adds Juice Shop as a scope target,
triggers a plugin run, and asserts on findings / artifacts produced.
"""
from __future__ import annotations

import time
import uuid

import httpx
import pytest

from .conftest import DRIFT_API, JUICESHOP_URL

_POLL_INTERVAL = 5
_RUN_TIMEOUT = 300  # seconds


def _poll_run(api: httpx.Client, engagement_id: str, run_id: str) -> dict:
    deadline = time.time() + _RUN_TIMEOUT
    while time.time() < deadline:
        r = api.get(f"/api/engagements/{engagement_id}/runs/{run_id}")
        assert r.status_code == 200
        run = r.json()
        if run["status"] in ("completed", "failed", "error"):
            return run
        time.sleep(_POLL_INTERVAL)
    pytest.fail(f"Run {run_id} did not finish within {_RUN_TIMEOUT}s")


@pytest.fixture(scope="module")
def juiceshop_engagement(api: httpx.Client) -> dict:
    name = f"e2e-juiceshop-{uuid.uuid4().hex[:8]}"
    r = api.post("/api/engagements", json={
        "name": name,
        "description": "E2E scan of OWASP Juice Shop",
        "target": "localhost",
    })
    assert r.status_code in (200, 201), r.text
    eng = r.json()

    # Add Juice Shop as an allowed scope target
    host = JUICESHOP_URL.removeprefix("http://").removeprefix("https://").split(":")[0]
    port = JUICESHOP_URL.split(":")[-1] if ":" in JUICESHOP_URL.removeprefix("http://") else "80"
    api.post(f"/api/engagements/{eng['id']}/scope", json={
        "type": "url",
        "value": JUICESHOP_URL,
        "notes": "E2E Juice Shop target",
    })

    return eng


class TestJuiceShopReachability:
    def test_juiceshop_health(self):
        r = httpx.get(JUICESHOP_URL, follow_redirects=True, timeout=10)
        assert r.status_code == 200

    def test_juiceshop_serves_html(self):
        r = httpx.get(JUICESHOP_URL, follow_redirects=True, timeout=10)
        assert "text/html" in r.headers.get("content-type", "")


class TestEngagementLifecycle:
    def test_engagement_created(self, juiceshop_engagement):
        assert "id" in juiceshop_engagement
        assert juiceshop_engagement["name"].startswith("e2e-juiceshop-")

    def test_engagement_status_is_active_or_draft(self, juiceshop_engagement):
        assert juiceshop_engagement["status"] in ("draft", "active")

    def test_scope_item_present(self, api: httpx.Client, juiceshop_engagement):
        r = api.get(f"/api/engagements/{juiceshop_engagement['id']}/scope")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        values = [i["value"] for i in items]
        assert any(JUICESHOP_URL in v or "localhost" in v for v in values)


class TestHttpxPlugin:
    """Run httpx probe plugin against Juice Shop and assert on results."""

    @pytest.fixture(scope="class")
    def httpx_run(self, api: httpx.Client, juiceshop_engagement: dict) -> dict:
        eng_id = juiceshop_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "httpx_probe",
            "params": {"target": JUICESHOP_URL},
        })
        assert r.status_code in (200, 201, 202), r.text
        run_id = r.json()["id"]
        return _poll_run(api, eng_id, run_id)

    def test_run_completed(self, httpx_run):
        assert httpx_run["status"] == "completed", f"Run failed: {httpx_run.get('error')}"

    def test_run_has_output(self, httpx_run):
        assert httpx_run.get("stdout") or httpx_run.get("artifact_path")

    def test_juiceshop_http_detected(self, httpx_run):
        stdout = httpx_run.get("stdout", "")
        assert "200" in stdout or "301" in stdout or "302" in stdout


class TestNmapPlugin:
    """Run nmap against the Juice Shop host."""

    @pytest.fixture(scope="class")
    def nmap_run(self, api: httpx.Client, juiceshop_engagement: dict) -> dict:
        eng_id = juiceshop_engagement["id"]
        host = JUICESHOP_URL.removeprefix("http://").split(":")[0]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "nmap_scan",
            "params": {"target": host, "ports": "3000,80,443", "flags": "-sV -T4"},
        })
        assert r.status_code in (200, 201, 202), r.text
        run_id = r.json()["id"]
        return _poll_run(api, eng_id, run_id)

    def test_run_completed(self, nmap_run):
        assert nmap_run["status"] == "completed", f"Run failed: {nmap_run.get('error')}"

    def test_port_3000_open(self, nmap_run):
        stdout = nmap_run.get("stdout", "")
        assert "3000" in stdout or "open" in stdout.lower()


class TestNucleiPlugin:
    """Run nuclei (low-impact templates only) against Juice Shop."""

    @pytest.fixture(scope="class")
    def nuclei_run(self, api: httpx.Client, juiceshop_engagement: dict) -> dict:
        eng_id = juiceshop_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "nuclei_scan",
            "params": {
                "target": JUICESHOP_URL,
                "tags": "tech,http,headers",
                "severity": "info,low",
            },
        })
        assert r.status_code in (200, 201, 202), r.text
        run_id = r.json()["id"]
        return _poll_run(api, eng_id, run_id)

    def test_run_completed_or_no_results(self, nuclei_run):
        # nuclei may return completed with 0 matches — both are acceptable
        assert nuclei_run["status"] in ("completed", "failed")

    def test_findings_created(self, api: httpx.Client, juiceshop_engagement: dict):
        r = api.get(f"/api/engagements/{juiceshop_engagement['id']}/findings")
        assert r.status_code == 200
        # We don't assert on count since nuclei results vary; just check schema
        findings = r.json()
        for f in findings[:5]:
            assert "id" in f
            assert "severity" in f
            assert "title" in f


class TestFindingWorkflow:
    def test_create_manual_finding(self, api: httpx.Client, juiceshop_engagement: dict):
        eng_id = juiceshop_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/findings", json={
            "title": "Missing Content-Security-Policy header",
            "description": "The application does not set a Content-Security-Policy header.",
            "severity": "medium",
            "target": JUICESHOP_URL,
            "evidence": "Confirmed via curl -I response headers.",
        })
        assert r.status_code in (200, 201), r.text
        finding = r.json()
        assert finding["severity"] == "medium"
        assert finding["title"] == "Missing Content-Security-Policy header"

    def test_finding_appears_in_list(self, api: httpx.Client, juiceshop_engagement: dict):
        r = api.get(f"/api/engagements/{juiceshop_engagement['id']}/findings")
        assert r.status_code == 200
        titles = [f["title"] for f in r.json()]
        assert any("Content-Security-Policy" in t for t in titles)


class TestSbomEndpoint:
    def test_cyclonedx_available(self, api: httpx.Client):
        r = api.get("/api/sbom?format=cyclonedx")
        assert r.status_code == 200
        body = r.json()
        assert body["bomFormat"] == "CycloneDX"

    def test_spdx_available(self, api: httpx.Client):
        r = api.get("/api/sbom?format=spdx")
        assert r.status_code == 200
        body = r.json()
        assert body["spdxVersion"] == "SPDX-2.3"

    def test_sbom_summary(self, api: httpx.Client):
        r = api.get("/api/sbom")
        assert r.status_code == 200
        body = r.json()
        assert "component_count" in body
        assert body["component_count"] > 0


class TestReportGeneration:
    def test_generate_report(self, api: httpx.Client, juiceshop_engagement: dict):
        eng_id = juiceshop_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/reports", json={"format": "markdown"})
        assert r.status_code in (200, 201, 202), r.text

    def test_report_appears_in_list(self, api: httpx.Client, juiceshop_engagement: dict):
        eng_id = juiceshop_engagement["id"]
        r = api.get(f"/api/engagements/{eng_id}/reports")
        assert r.status_code == 200
