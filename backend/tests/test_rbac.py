from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import _create_user, get_token

pytestmark = pytest.mark.asyncio


async def test_admin_can_list_users(client: AsyncClient, admin_user):
    token = await get_token(client, "admin_user")
    resp = await client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_viewer_cannot_list_users(client: AsyncClient, viewer_user):
    token = await get_token(client, "viewer_user")
    resp = await client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_lead_can_list_users(client: AsyncClient, lead_user):
    token = await get_token(client, "lead_user")
    resp = await client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_viewer_can_see_own_profile(client: AsyncClient, viewer_user):
    token = await get_token(client, "viewer_user")
    user_id = viewer_user.id
    resp = await client.get(f"/api/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "viewer_user"


async def test_tester_cannot_view_other_user(client: AsyncClient, tester_user, viewer_user):
    token = await get_token(client, "tester_user")
    resp = await client.get(
        f"/api/users/{viewer_user.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_admin_can_access_audit_log(client: AsyncClient, admin_user):
    token = await get_token(client, "admin_user")
    resp = await client.get("/api/audit/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_tester_cannot_access_audit_log(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    resp = await client.get("/api/audit/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_unauthenticated_cannot_access_protected_route(client: AsyncClient):
    resp = await client.get("/api/users/")
    assert resp.status_code == 401


async def test_admin_can_change_user_role(client: AsyncClient, admin_user, tester_user):
    token = await get_token(client, "admin_user")
    resp = await client.patch(
        f"/api/users/{tester_user.id}",
        json={"role": "lead"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "lead"


async def test_tester_cannot_change_role(client: AsyncClient, tester_user, viewer_user):
    token = await get_token(client, "tester_user")
    resp = await client.patch(
        f"/api/users/{viewer_user.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_client_readonly_role_cannot_do_tester_actions(client: AsyncClient, db: AsyncSession):
    cr_user = await _create_user(db, "client_ro", "client_readonly")
    token = await get_token(client, "client_ro")
    resp = await client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
