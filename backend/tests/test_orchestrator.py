"""Tests for orchestrator service and plugin registry."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import Engagement, EngagementStatus
from app.models.run import RunStatus
from app.plugins.manifest import (
    CyclicDependencyError,
    PluginManifest,
    PluginNotFoundError,
    PluginRegistry,
)
from app.services.orchestrator import AuthorizationNotConfirmedError, OrchestratorService
from tests.conftest import _create_user, get_token

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# PluginRegistry unit tests (no DB needed)
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    def test_register_and_get(self):
        reg = PluginRegistry()
        manifest = PluginManifest(
            name="test_tool",
            version="1.0",
            category="recon",
            is_intrusive=False,
            binary="test",
        )
        reg.register(manifest)
        assert reg.get("test_tool") == manifest

    def test_get_not_found(self):
        reg = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            reg.get("nonexistent")

    def test_list_all(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a"))
        reg.register(PluginManifest(name="b", version="1", category="web", is_intrusive=True, binary="b"))
        assert len(reg.list_all()) == 2

    def test_list_by_category(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a"))
        reg.register(PluginManifest(name="b", version="1", category="web", is_intrusive=True, binary="b"))
        assert len(reg.list_by_category("recon")) == 1
        assert len(reg.list_by_category("web")) == 1

    def test_list_safe_mode(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="safe", version="1", category="recon", is_intrusive=False, binary="s", safe_mode_allowed=True))
        reg.register(PluginManifest(name="unsafe", version="1", category="scan", is_intrusive=True, binary="u", safe_mode_allowed=False))
        safe = reg.list_safe_mode()
        assert len(safe) == 1
        assert safe[0].name == "safe"

    def test_topological_sort_simple(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a"))
        reg.register(PluginManifest(name="b", version="1", category="recon", is_intrusive=False, binary="b", dependencies=["a"]))
        reg.register(PluginManifest(name="c", version="1", category="recon", is_intrusive=False, binary="c", dependencies=["b"]))

        order = reg.topological_sort(["a", "b", "c"])
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_no_deps(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a"))
        reg.register(PluginManifest(name="b", version="1", category="recon", is_intrusive=False, binary="b"))

        order = reg.topological_sort(["a", "b"])
        assert set(order) == {"a", "b"}

    def test_topological_sort_detects_cycle(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a", dependencies=["b"]))
        reg.register(PluginManifest(name="b", version="1", category="recon", is_intrusive=False, binary="b", dependencies=["a"]))

        with pytest.raises(CyclicDependencyError):
            reg.topological_sort(["a", "b"])

    def test_topological_sort_missing_dependency(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a", dependencies=["missing"]))

        with pytest.raises(PluginNotFoundError):
            reg.topological_sort(["a"])

    def test_get_execution_plan_safe_mode(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="safe", version="1", category="recon", is_intrusive=False, binary="s", safe_mode_allowed=True))
        reg.register(PluginManifest(name="intrusive", version="1", category="scan", is_intrusive=True, binary="i", safe_mode_allowed=False))

        plan = reg.get_execution_plan(["safe", "intrusive"], safe_mode=True)
        assert len(plan) == 1
        assert plan[0].name == "safe"

    def test_get_execution_plan_full(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="safe", version="1", category="recon", is_intrusive=False, binary="s"))
        reg.register(PluginManifest(name="intrusive", version="1", category="scan", is_intrusive=True, binary="i"))

        plan = reg.get_execution_plan(["safe", "intrusive"], safe_mode=False)
        assert len(plan) == 2

    def test_unregister(self):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="a", version="1", category="recon", is_intrusive=False, binary="a"))
        reg.unregister("a")
        assert len(reg.list_all()) == 0


# ---------------------------------------------------------------------------
# OrchestratorService tests (with DB)
# ---------------------------------------------------------------------------


async def _create_engagement(db: AsyncSession, owner_id: uuid.UUID, **kwargs) -> Engagement:
    eng = Engagement(
        title=kwargs.get("title", "Test Engagement"),
        client_name=kwargs.get("client_name", "Test Client"),
        owner_id=owner_id,
        status=kwargs.get("status", EngagementStatus.active.value),
        authorization_confirmed=kwargs.get("authorization_confirmed", False),
    )
    db.add(eng)
    await db.commit()
    await db.refresh(eng)
    return eng


class TestOrchestratorService:
    async def test_create_run_safe_mode(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="subfinder", version="1", category="recon", is_intrusive=False, binary="subfinder", safe_mode_allowed=True))
        reg.register(PluginManifest(name="nmap", version="1", category="scan", is_intrusive=True, binary="nmap", safe_mode_allowed=False))

        eng = await _create_engagement(db, tester_user.id)
        orch = OrchestratorService(db, reg)

        run = await orch.create_run(
            engagement_id=eng.id,
            triggered_by=tester_user.id,
            safe_mode=True,
        )
        await db.commit()

        assert run.status == RunStatus.pending.value
        assert run.pipeline_config["safe_mode"] is True
        assert "subfinder" in run.pipeline_config["plugins"]
        assert "nmap" not in run.pipeline_config["plugins"]

    async def test_create_run_intrusive_requires_auth(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="nmap", version="1", category="scan", is_intrusive=True, binary="nmap", safe_mode_allowed=False))

        eng = await _create_engagement(db, tester_user.id, authorization_confirmed=False)
        orch = OrchestratorService(db, reg)

        with pytest.raises(AuthorizationNotConfirmedError):
            await orch.create_run(
                engagement_id=eng.id,
                triggered_by=tester_user.id,
                plugin_names=["nmap"],
            )

    async def test_create_run_intrusive_with_auth(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="nmap", version="1", category="scan", is_intrusive=True, binary="nmap", safe_mode_allowed=False))

        eng = await _create_engagement(db, tester_user.id, authorization_confirmed=True)
        orch = OrchestratorService(db, reg)

        run = await orch.create_run(
            engagement_id=eng.id,
            triggered_by=tester_user.id,
            plugin_names=["nmap"],
        )
        await db.commit()

        assert run.status == RunStatus.pending.value
        assert "nmap" in run.pipeline_config["plugins"]

    async def test_cancel_run(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="subfinder", version="1", category="recon", is_intrusive=False, binary="subfinder"))

        eng = await _create_engagement(db, tester_user.id)
        orch = OrchestratorService(db, reg)

        run = await orch.create_run(
            engagement_id=eng.id,
            triggered_by=tester_user.id,
            safe_mode=True,
        )
        await db.commit()

        run = await orch.cancel_run(run.id)
        await db.commit()

        assert run.status == RunStatus.cancelled.value
        assert run.completed_at is not None

    async def test_dry_run(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="subfinder", version="1", category="recon", is_intrusive=False, binary="subfinder"))
        reg.register(PluginManifest(name="nmap", version="1", category="scan", is_intrusive=True, binary="nmap", safe_mode_allowed=False))

        eng = await _create_engagement(db, tester_user.id, authorization_confirmed=False)
        orch = OrchestratorService(db, reg)

        result = await orch.dry_run(engagement_id=eng.id)
        assert result["total_plugins"] == 2
        assert len(result["authorization_issues"]) == 1

    async def test_dry_run_safe_mode(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="subfinder", version="1", category="recon", is_intrusive=False, binary="subfinder"))
        reg.register(PluginManifest(name="nmap", version="1", category="scan", is_intrusive=True, binary="nmap", safe_mode_allowed=False))

        eng = await _create_engagement(db, tester_user.id)
        orch = OrchestratorService(db, reg)

        result = await orch.dry_run(engagement_id=eng.id, safe_mode=True)
        assert result["total_plugins"] == 1
        assert result["safe_mode"] is True

    async def test_create_run_completed_engagement_fails(self, db: AsyncSession, tester_user):
        reg = PluginRegistry()
        reg.register(PluginManifest(name="subfinder", version="1", category="recon", is_intrusive=False, binary="subfinder"))

        eng = await _create_engagement(db, tester_user.id, status=EngagementStatus.completed.value)
        orch = OrchestratorService(db, reg)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await orch.create_run(
                engagement_id=eng.id,
                triggered_by=tester_user.id,
                safe_mode=True,
            )
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Run API endpoint tests
# ---------------------------------------------------------------------------


async def test_create_run_endpoint(client: AsyncClient, tester_user, db: AsyncSession):
    token = await get_token(client, "tester_user")

    # Create engagement
    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Run Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    # Create run (no plugins registered = empty plan, should still create)
    resp = await client.post(
        f"/api/engagements/{eng_id}/runs",
        json={"safe_mode": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["engagement_id"] == eng_id


async def test_list_runs_endpoint(client: AsyncClient, tester_user, db: AsyncSession):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "List Runs", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    # Create two runs
    for _ in range(2):
        await client.post(
            f"/api/engagements/{eng_id}/runs",
            json={"safe_mode": True},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        f"/api/engagements/{eng_id}/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


async def test_get_run_endpoint(client: AsyncClient, tester_user, db: AsyncSession):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Get Run", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    run_resp = await client.post(
        f"/api/engagements/{eng_id}/runs",
        json={"safe_mode": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = run_resp.json()["id"]

    resp = await client.get(
        f"/api/runs/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


async def test_cancel_run_endpoint(client: AsyncClient, tester_user, db: AsyncSession):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Cancel Run", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    run_resp = await client.post(
        f"/api/engagements/{eng_id}/runs",
        json={"safe_mode": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = run_resp.json()["id"]

    resp = await client.post(
        f"/api/runs/{run_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_modules_endpoint(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    resp = await client.get(
        "/api/modules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    # Empty registry = empty list
    assert resp.json() == []
