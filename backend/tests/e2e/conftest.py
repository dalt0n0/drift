"""E2E test configuration.

These tests require the full Drift stack + e2e targets to be running:

    docker compose -f deploy/docker-compose.yml \
                   -f deploy/docker-compose.e2e.yml up -d

Set environment variables to override defaults:
    DRIFT_API_URL      — default http://localhost:8000
    DRIFT_ADMIN_PASS   — admin password printed by setup.sh
    JUICESHOP_URL      — default http://localhost:3180
    DVWA_URL           — default http://localhost:3181
"""
from __future__ import annotations

import os
import time

import httpx
import pytest


DRIFT_API = os.getenv("DRIFT_API_URL", "http://localhost:8000")
ADMIN_PASS = os.getenv("DRIFT_ADMIN_PASS", "changeme")
JUICESHOP_URL = os.getenv("JUICESHOP_URL", "http://localhost:3180")
DVWA_URL = os.getenv("DVWA_URL", "http://localhost:3181")

_WAIT_TIMEOUT = 120
_WAIT_INTERVAL = 3


def _wait_for(url: str, label: str, timeout: int = _WAIT_TIMEOUT) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=5, follow_redirects=True)
            if r.status_code < 500:
                return
        except httpx.TransportError:
            pass
        time.sleep(_WAIT_INTERVAL)
    pytest.skip(f"{label} not reachable at {url} after {timeout}s — skipping E2E suite")


@pytest.fixture(scope="session", autouse=True)
def wait_for_services():
    _wait_for(f"{DRIFT_API}/api/health", "Drift API")
    _wait_for(JUICESHOP_URL, "Juice Shop")
    _wait_for(DVWA_URL, "DVWA")


@pytest.fixture(scope="session")
def api_token(wait_for_services) -> str:
    r = httpx.post(
        f"{DRIFT_API}/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASS},
        timeout=10,
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def api(api_token) -> httpx.Client:
    return httpx.Client(
        base_url=DRIFT_API,
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=30,
    )
