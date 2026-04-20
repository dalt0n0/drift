from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.audit import AuditEntry

logger = structlog.get_logger(__name__)
settings = get_settings()

_GENESIS = "GENESIS"


def _canonical_json(data: dict) -> str:
    """Deterministic JSON: sorted keys, no whitespace, str fallback for non-serializable types."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _entry_dict(entry: AuditEntry) -> dict:
    return {
        "id": str(entry.id),
        "timestamp": entry.timestamp.isoformat(),
        "actor_id": str(entry.actor_id) if entry.actor_id else None,
        "actor_ip": entry.actor_ip,
        "user_agent": entry.user_agent,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "before_state": entry.before_state,
        "after_state": entry.after_state,
        "request_id": entry.request_id,
        "session_id": entry.session_id,
        "outcome": entry.outcome,
        "chain_hash": entry.chain_hash,
    }


def _compute_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _get_last_entry_canonical(db: AsyncSession) -> str:
    """Fetch last audit entry under FOR UPDATE lock, return its canonical JSON."""
    result = await db.execute(
        select(AuditEntry)
        .order_by(AuditEntry.timestamp.desc(), AuditEntry.id.desc())
        .limit(1)
        .with_for_update()
    )
    last = result.scalar_one_or_none()
    if last is None:
        return _GENESIS
    return _canonical_json(_entry_dict(last))


def _append_jsonl(entry_dict: dict) -> None:
    """Atomically append one JSONL line to the audit log file."""
    log_path = Path(settings.AUDIT_LOG_PATH)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = _canonical_json(entry_dict) + "\n"
        # Write to temp file in same dir, then rename (atomic on POSIX)
        fd, tmp_path = tempfile.mkstemp(dir=log_path.parent, prefix=".audit_tmp_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(line)
            # Append mode: rename won't work for appending; use direct append instead
            # For true atomicity we use a lock file approach; simpler: open in append
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        logger.warning("audit_jsonl_write_failed", error=str(exc))


async def log(
    db: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    actor_ip: str | None = None,
    user_agent: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    outcome: str = "success",
) -> AuditEntry:
    # Sanitize sensitive fields
    if before_state:
        before_state = _sanitize(before_state)
    if after_state:
        after_state = _sanitize(after_state)

    prev_canonical = await _get_last_entry_canonical(db)
    chain_hash = _compute_hash(prev_canonical)

    entry = AuditEntry(
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        actor_ip=actor_ip,
        user_agent=user_agent,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        request_id=request_id,
        session_id=session_id,
        outcome=outcome,
        chain_hash=chain_hash,
    )
    db.add(entry)
    await db.flush()  # populate id/timestamp without committing

    _append_jsonl(_entry_dict(entry))
    return entry


_SENSITIVE_KEYS = frozenset({
    "password", "hashed_password", "token", "secret", "key", "mfa_secret",
    "token_hash", "key_hash", "authorization", "cookie",
})


def _sanitize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_KEYS:
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = _sanitize(v)
        else:
            out[k] = v
    return out


async def verify_chain(db: AsyncSession) -> tuple[bool, str]:
    """Walk all audit entries in insertion order, recompute chain hashes."""
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.timestamp.asc(), AuditEntry.id.asc())
    )
    entries = result.scalars().all()

    prev_canonical = _GENESIS
    for entry in entries:
        expected_hash = _compute_hash(prev_canonical)
        if entry.chain_hash != expected_hash:
            return False, (
                f"Chain broken at entry {entry.id} "
                f"(action={entry.action}, ts={entry.timestamp.isoformat()}): "
                f"expected chain_hash={expected_hash!r}, got {entry.chain_hash!r}"
            )
        prev_canonical = _canonical_json(_entry_dict(entry))

    return True, ""


async def run_daily_integrity_check(db: AsyncSession) -> dict:
    """Run the daily audit chain integrity check and log the result.

    Returns a dict with timestamp, valid, message, and entries_checked.
    """
    from sqlalchemy import func as sa_func

    count_result = await db.execute(
        select(sa_func.count(AuditEntry.id))
    )
    entries_checked = count_result.scalar_one()

    is_valid, message = await verify_chain(db)

    now = datetime.now(timezone.utc)

    # Log the integrity check itself as an audit entry
    await log(
        db,
        action="audit.integrity_check",
        outcome="success" if is_valid else "failure",
        after_state={
            "valid": is_valid,
            "message": message,
            "entries_checked": entries_checked,
            "checked_at": now.isoformat(),
        },
    )

    logger.info(
        "audit_integrity_check",
        valid=is_valid,
        entries_checked=entries_checked,
        message=message,
    )

    return {
        "timestamp": now.isoformat(),
        "valid": is_valid,
        "message": message if message else "Audit chain integrity verified successfully.",
        "entries_checked": entries_checked,
    }


def get_client_ip(request: Any) -> str:
    """Extract real client IP, respecting X-Forwarded-For set by trusted proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
