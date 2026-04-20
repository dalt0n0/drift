"""Tests for engagement CRUD endpoints."""
from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import _create_user, get_token

pytestmark = pytest.mark.asyncio


async def test_create_engagement(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    resp = await client.post(
        "/api/engagements",
        json={
            "title": "Test Engagement",
            "client_name": "Acme Corp",
            "description": "Testing engagement creation",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Engagement"
    assert data["client_name"] == "Acme Corp"
    assert data["status"] == "draft"
    assert data["authorization_confirmed"] is False


async def test_list_engagements(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    # Create two engagements
    for i in range(2):
        await client.post(
            "/api/engagements",
            json={"title": f"Engagement {i}", "client_name": "Client"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/api/engagements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_get_engagement(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Get Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/engagements/{eng_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Test"


async def test_update_engagement(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Update Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/engagements/{eng_id}",
        json={"title": "Updated Title", "status": "active"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"
    assert resp.json()["status"] == "active"


async def test_delete_engagement_requires_lead(client: AsyncClient, tester_user, lead_user):
    tester_token = await get_token(client, "tester_user")
    lead_token = await get_token(client, "lead_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Delete Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {tester_token}"},
    )
    eng_id = create_resp.json()["id"]

    # Tester can't delete
    resp = await client.delete(
        f"/api/engagements/{eng_id}",
        headers={"Authorization": f"Bearer {tester_token}"},
    )
    assert resp.status_code == 403

    # Lead can delete (archive)
    resp = await client.delete(
        f"/api/engagements/{eng_id}",
        headers={"Authorization": f"Bearer {lead_token}"},
    )
    assert resp.status_code == 204


async def test_engagement_not_found(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/engagements/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_authorization_upload_and_confirm(
    client: AsyncClient, tester_user, lead_user
):
    tester_token = await get_token(client, "tester_user")
    lead_token = await get_token(client, "lead_user")

    # Create engagement
    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Auth Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {tester_token}"},
    )
    eng_id = create_resp.json()["id"]

    # Upload authorization letter
    file_content = b"This is the authorization letter content."
    resp = await client.post(
        f"/api/engagements/{eng_id}/authorization",
        files={"file": ("auth_letter.pdf", io.BytesIO(file_content), "application/pdf")},
        headers={"Authorization": f"Bearer {tester_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authorization_hash"] is not None
    assert data["authorization_confirmed"] is False

    # Confirm requires lead role — tester can't confirm
    resp = await client.post(
        f"/api/engagements/{eng_id}/authorization/confirm",
        headers={"Authorization": f"Bearer {tester_token}"},
    )
    assert resp.status_code == 403

    # Lead can confirm
    resp = await client.post(
        f"/api/engagements/{eng_id}/authorization/confirm",
        headers={"Authorization": f"Bearer {lead_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["authorization_confirmed"] is True


async def test_confirm_without_upload_fails(client: AsyncClient, lead_user):
    lead_token = await get_token(client, "lead_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "No Auth Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {lead_token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/engagements/{eng_id}/authorization/confirm",
        headers={"Authorization": f"Bearer {lead_token}"},
    )
    assert resp.status_code == 400


async def test_scope_crud(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")

    # Create engagement
    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Scope Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    # Add scope item
    resp = await client.post(
        f"/api/engagements/{eng_id}/scope",
        json={"type": "domain", "value": "example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    scope_id = resp.json()["id"]

    # List scope items
    resp = await client.get(
        f"/api/engagements/{eng_id}/scope",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Delete scope item
    resp = await client.delete(
        f"/api/engagements/{eng_id}/scope/{scope_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_scope_blocked_ip_rejected(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Blocked Scope", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/engagements/{eng_id}/scope",
        json={"type": "ip", "value": "127.0.0.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400

    resp = await client.post(
        f"/api/engagements/{eng_id}/scope",
        json={"type": "domain", "value": "whitehouse.gov"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_scope_excluded_item_skips_validation(client: AsyncClient, tester_user):
    """Excluded scope items bypass validation (they define what NOT to hit)."""
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Excluded Scope", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    # Adding a blocked IP as excluded should succeed
    resp = await client.post(
        f"/api/engagements/{eng_id}/scope",
        json={"type": "ip", "value": "127.0.0.1", "is_excluded": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


async def test_scope_batch_add(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Batch Scope", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/engagements/{eng_id}/scope/batch",
        json={
            "items": [
                {"type": "domain", "value": "example.com"},
                {"type": "ip", "value": "8.8.8.8"},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 2


async def test_scope_batch_rejects_if_any_blocked(client: AsyncClient, tester_user):
    token = await get_token(client, "tester_user")

    create_resp = await client.post(
        "/api/engagements",
        json={"title": "Batch Blocked", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eng_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/engagements/{eng_id}/scope/batch",
        json={
            "items": [
                {"type": "domain", "value": "example.com"},
                {"type": "ip", "value": "127.0.0.1"},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_viewer_cannot_create_engagement(client: AsyncClient, viewer_user):
    token = await get_token(client, "viewer_user")
    resp = await client.post(
        "/api/engagements",
        json={"title": "Viewer Test", "client_name": "Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
