from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import _create_user, get_token

pytestmark = pytest.mark.asyncio


async def test_register_and_login(client: AsyncClient, admin_user, db: AsyncSession):
    token = await get_token(client, "admin_user")
    assert token

    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@test.local",
            "full_name": "New User",
            "password": "NewSecurePass1!",
            "role": "tester",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["role"] == "tester"
    assert "hashed_password" not in data


async def test_login_wrong_password_same_error_as_unknown_user(client: AsyncClient, tester_user):
    resp_wrong_pw = await client.post(
        "/api/auth/login", json={"username": "tester_user", "password": "WrongPassword!"}
    )
    resp_unknown = await client.post(
        "/api/auth/login", json={"username": "nobody_exists", "password": "anything"}
    )
    assert resp_wrong_pw.status_code == 401
    assert resp_unknown.status_code == 401
    assert resp_wrong_pw.json()["detail"]["detail"] == resp_unknown.json()["detail"]["detail"]


async def test_brute_force_lockout(client: AsyncClient, tester_user):
    for _ in range(5):
        r = await client.post(
            "/api/auth/login", json={"username": "tester_user", "password": "wrong"}
        )
        assert r.status_code == 401

    r = await client.post(
        "/api/auth/login", json={"username": "tester_user", "password": "TestPass123!"}
    )
    assert r.status_code == 429


async def test_refresh_token_rotation(client: AsyncClient, tester_user):
    resp = await client.post(
        "/api/auth/login", json={"username": "tester_user", "password": "TestPass123!"}
    )
    assert resp.status_code == 200
    assert "reconstrike_refresh" in resp.cookies

    resp2 = await client.post("/api/auth/refresh")
    assert resp2.status_code == 200
    new_token = resp2.json()["access_token"]
    assert new_token

    # Old refresh cookie replaced
    assert "reconstrike_refresh" in resp2.cookies


async def test_logout_clears_cookie(client: AsyncClient, tester_user):
    await client.post("/api/auth/login", json={"username": "tester_user", "password": "TestPass123!"})
    token = (await client.post("/api/auth/refresh")).json()["access_token"]

    resp = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_api_key_create_and_use(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    headers = {"Authorization": f"Bearer {token}"}

    # Create key
    resp = await client.post(
        "/api/auth/api-keys",
        json={"name": "CI key"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    raw_key = data["raw_key"]
    key_id = data["id"]
    assert raw_key.startswith("drk_")

    # Use key to authenticate
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "tester_user"

    # Revoke key
    resp = await client.delete(f"/api/auth/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 204

    # Revoked key no longer works
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 401


async def test_change_password_revokes_sessions(client: AsyncClient, tester_user):
    await client.post("/api/auth/login", json={"username": "tester_user", "password": "TestPass123!"})
    token = await get_token(client, "tester_user")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "TestPass123!", "new_password": "NewSuperPass99!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Old refresh cookie should no longer work
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401


async def test_me_endpoint(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "tester_user"
    assert resp.json()["role"] == "tester"
