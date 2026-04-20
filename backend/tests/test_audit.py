from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit as audit_svc
from app.models.audit import AuditEntry

pytestmark = pytest.mark.asyncio


async def test_first_entry_uses_genesis_hash(db: AsyncSession):
    entry = await audit_svc.log(
        db, action="test.action", outcome="success"
    )
    await db.commit()

    expected = hashlib.sha256("GENESIS".encode()).hexdigest()
    assert entry.chain_hash == expected


async def test_chain_hash_links_entries(db: AsyncSession):
    e1 = await audit_svc.log(db, action="first.action")
    await db.commit()

    e2 = await audit_svc.log(db, action="second.action")
    await db.commit()

    # e2.chain_hash should be SHA256 of e1's canonical json
    e1_dict = {
        "id": str(e1.id),
        "timestamp": e1.timestamp.isoformat(),
        "actor_id": None,
        "actor_ip": None,
        "user_agent": None,
        "action": e1.action,
        "resource_type": None,
        "resource_id": None,
        "before_state": None,
        "after_state": None,
        "request_id": None,
        "session_id": None,
        "outcome": "success",
        "chain_hash": e1.chain_hash,
    }
    canonical = json.dumps(e1_dict, sort_keys=True, separators=(",", ":"), default=str)
    expected = hashlib.sha256(canonical.encode()).hexdigest()
    assert e2.chain_hash == expected


async def test_verify_chain_valid(db: AsyncSession):
    for i in range(5):
        await audit_svc.log(db, action=f"event.{i}")
    await db.commit()

    ok, msg = await audit_svc.verify_chain(db)
    assert ok is True
    assert msg == ""


async def test_verify_chain_detects_tamper(db: AsyncSession):
    for i in range(3):
        await audit_svc.log(db, action=f"event.{i}")
    await db.commit()

    # Tamper: mutate second entry's action directly
    result = await db.execute(select(AuditEntry).order_by(AuditEntry.timestamp.asc()))
    entries = result.scalars().all()
    assert len(entries) == 3

    # Mutate the middle entry without updating chain hashes
    entries[1].action = "TAMPERED"
    await db.commit()

    ok, msg = await audit_svc.verify_chain(db)
    assert ok is False
    assert "Chain broken" in msg


async def test_sensitive_fields_redacted(db: AsyncSession):
    entry = await audit_svc.log(
        db,
        action="test.sensitive",
        before_state={"password": "secret123", "username": "alice"},
        after_state={"token": "abc", "email": "a@b.com"},
    )
    await db.commit()

    assert entry.before_state["password"] == "[REDACTED]"
    assert entry.before_state["username"] == "alice"
    assert entry.after_state["token"] == "[REDACTED]"
    assert entry.after_state["email"] == "a@b.com"


async def test_audit_log_all_fields(db: AsyncSession):
    import uuid
    actor = uuid.uuid4()
    entry = await audit_svc.log(
        db,
        action="user.login",
        actor_id=actor,
        actor_ip="1.2.3.4",
        user_agent="TestAgent/1.0",
        resource_type="user",
        resource_id="some-id",
        request_id="req-123",
        session_id="sess-456",
        outcome="success",
    )
    await db.commit()

    assert entry.actor_ip == "1.2.3.4"
    assert entry.user_agent == "TestAgent/1.0"
    assert entry.resource_type == "user"
    assert entry.outcome == "success"
    assert entry.request_id == "req-123"
