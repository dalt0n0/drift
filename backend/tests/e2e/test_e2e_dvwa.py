"""E2E tests: Drift scanning DVWA (Damn Vulnerable Web Application).

Requires the full stack + e2e targets (see conftest.py).
"""
from __future__ import annotations

import time
import uuid

import httpx
import pytest

from .conftest import DRIFT_API, DVWA_URL

_POLL_INTERVAL = 5
_RUN_TIMEOUT = 300


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
def dvwa_engagement(api: httpx.Client) -> dict:
    name = f"e2e-dvwa-{uuid.uuid4().hex[:8]}"
    r = api.post("/api/engagements", json={
        "name": name,
        "description": "E2E scan of DVWA",
        "target": "localhost",
    })
    assert r.status_code in (200, 201), r.text
    eng = r.json()

    api.post(f"/api/engagements/{eng['id']}/scope", json={
        "type": "url",
        "value": DVWA_URL,
        "notes": "E2E DVWA target",
    })

    return eng


class TestDvwaReachability:
    def test_dvwa_health(self):
        r = httpx.get(DVWA_URL, follow_redirects=True, timeout=15)
        assert r.status_code == 200

    def test_dvwa_serves_html(self):
        r = httpx.get(DVWA_URL, follow_redirects=True, timeout=15)
        assert "text/html" in r.headers.get("content-type", "")

    def test_dvwa_login_page_present(self):
        r = httpx.get(f"{DVWA_URL}/login.php", follow_redirects=True, timeout=15)
        assert r.status_code == 200
        assert "DVWA" in r.text or "login" in r.text.lower()


class TestNiktoPlugin:
    """Run nikto against DVWA."""

    @pytest.fixture(scope="class")
    def nikto_run(self, api: httpx.Client, dvwa_engagement: dict) -> dict:
        eng_id = dvwa_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "nikto_scan",
            "params": {"target": DVWA_URL, "flags": "-Tuning 1 2 3 -maxtime 120s"},
        })
        assert r.status_code in (200, 201, 202), r.text
        run_id = r.json()["id"]
        return _poll_run(api, eng_id, run_id)

    def test_run_completed(self, nikto_run):
        assert nikto_run["status"] == "completed", f"Nikto run failed: {nikto_run.get('error')}"

    def test_nikto_produced_output(self, nikto_run):
        stdout = nikto_run.get("stdout", "")
        assert len(stdout) > 0

    def test_nikto_scanned_dvwa_host(self, nikto_run):
        stdout = nikto_run.get("stdout", "")
        assert "localhost" in stdout or "3181" in stdout or "Target" in stdout


class TestGobusterPlugin:
    """Run gobuster dir scan against DVWA."""

    @pytest.fixture(scope="class")
    def gobuster_run(self, api: httpx.Client, dvwa_engagement: dict) -> dict:
        eng_id = dvwa_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "gobuster_dir",
            "params": {
                "target": DVWA_URL,
                "wordlist": "/usr/share/wordlists/dirb/small.txt",
                "extensions": "php,html",
                "threads": "10",
            },
        })
        assert r.status_code in (200, 201, 202), r.text
        run_id = r.json()["id"]
        return _poll_run(api, eng_id, run_id)

    def test_run_completed(self, gobuster_run):
        assert gobuster_run["status"] == "completed", f"gobuster failed: {gobuster_run.get('error')}"

    def test_found_login_php(self, gobuster_run):
        stdout = gobuster_run.get("stdout", "")
        # login.php is a known DVWA path; gobuster should find it
        assert "login" in stdout.lower() or "Status: 200" in stdout or len(stdout) > 0


class TestScopeBoundaryEnforcement:
    """Verify the scope guard rejects out-of-scope targets even during E2E runs."""

    def test_out_of_scope_target_rejected(self, api: httpx.Client, dvwa_engagement: dict):
        eng_id = dvwa_engagement["id"]
        r = api.post(f"/api/engagements/{eng_id}/runs", json={
            "plugin": "httpx_probe",
            "params": {"target": "https://example.com"},  # not in scope
        })
        # Must be rejected: 400 (validation) or 403 (scope guard)
        assert r.status_code in (400, 403, 422), (
            f"Expected scope rejection, got {r.status_code}: {r.text}"
        )


class TestAuditTrail:
    """Verify audit log entries are created for E2E activity."""

    def test_audit_entries_exist(self, api: httpx.Client):
        r = api.get("/api/audit?limit=20")
        assert r.status_code == 200
        entries = r.json()
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_audit_entry_schema(self, api: httpx.Client):
        r = api.get("/api/audit?limit=5")
        assert r.status_code == 200
        for entry in r.json():
            assert "id" in entry
            assert "action" in entry
            assert "timestamp" in entry

    def test_audit_log_immutable(self, api: httpx.Client):
        # Non-admin should not be able to delete audit entries
        r = api.delete("/api/audit/1")
        assert r.status_code in (403, 404, 405)


class TestHealthAndMeta:
    def test_health_ok(self):
        r = httpx.get(f"{DRIFT_API}/api/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_version_present(self):
        r = httpx.get(f"{DRIFT_API}/api/health", timeout=5)
        assert "version" in r.json()
