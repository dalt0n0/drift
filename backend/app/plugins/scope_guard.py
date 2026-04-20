"""ScopeGuard: validates targets against engagement scope before tool execution."""
from __future__ import annotations

import functools
import ipaddress
import re
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scope import ScopeItem, ScopeType, ScopeValidator, ScopeValidationError

logger = structlog.get_logger(__name__)


class ScopeViolationError(Exception):
    """Raised when a target is not within the engagement scope."""

    def __init__(self, target: str, reason: str):
        self.target = target
        self.reason = reason
        super().__init__(f"Scope violation for '{target}': {reason}")


async def get_engagement_scope(
    db: AsyncSession, engagement_id: Any
) -> tuple[list[ScopeItem], list[ScopeItem]]:
    """Fetch included and excluded scope items for an engagement.

    Returns:
        Tuple of (included_items, excluded_items).
    """
    result = await db.execute(
        select(ScopeItem).where(ScopeItem.engagement_id == engagement_id)
    )
    items = result.scalars().all()
    included = [i for i in items if not i.is_excluded]
    excluded = [i for i in items if i.is_excluded]
    return included, excluded


def _ip_in_scope_item(ip_str: str, item: ScopeItem) -> bool:
    """Check if an IP address falls within a scope item."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if item.type in (ScopeType.ip.value, ScopeType.cidr.value):
        try:
            network = ipaddress.ip_network(item.value, strict=False)
            return addr in network
        except ValueError:
            return False
    return False


def _domain_in_scope_item(domain: str, item: ScopeItem) -> bool:
    """Check if a domain matches a scope item."""
    domain = domain.lower().strip().rstrip(".")

    if item.type == ScopeType.domain.value:
        scope_domain = item.value.lower().strip().rstrip(".")
        return domain == scope_domain or domain.endswith(f".{scope_domain}")

    if item.type == ScopeType.wildcard.value:
        pattern = item.value.lower().strip()
        if pattern.startswith("*."):
            base = pattern[2:].rstrip(".")
            return domain == base or domain.endswith(f".{base}")

    if item.type == ScopeType.url.value:
        match = re.match(r"https?://([^/:]+)", item.value)
        if match:
            scope_domain = match.group(1).lower().rstrip(".")
            return domain == scope_domain

    return False


def _target_in_scope(target: str, included: list[ScopeItem], excluded: list[ScopeItem]) -> bool:
    """Check if a target (IP or domain) is within scope.

    A target must match at least one included item AND not match any excluded item.
    """
    # First check exclusions
    for exc in excluded:
        try:
            ipaddress.ip_address(target)
            if _ip_in_scope_item(target, exc):
                return False
        except ValueError:
            if _domain_in_scope_item(target, exc):
                return False

    # Then check inclusions
    for inc in included:
        try:
            ipaddress.ip_address(target)
            if _ip_in_scope_item(target, inc):
                return True
        except ValueError:
            if _domain_in_scope_item(target, inc):
                return True

    return False


def validate_targets(
    targets: list[str],
    included: list[ScopeItem],
    excluded: list[ScopeItem],
) -> tuple[list[str], list[str]]:
    """Validate a list of targets against the engagement scope.

    Returns:
        Tuple of (valid_targets, rejected_targets).
    """
    valid = []
    rejected = []
    for target in targets:
        # Always run hard-block check first (regardless of scope)
        try:
            # Determine target type
            try:
                ipaddress.ip_address(target)
                ScopeValidator.validate("ip", target)
            except ValueError:
                ScopeValidator.validate("domain", target)
        except ScopeValidationError:
            rejected.append(target)
            logger.warning("scope_guard.hard_blocked", target=target)
            continue

        if _target_in_scope(target, included, excluded):
            valid.append(target)
        else:
            rejected.append(target)
            logger.warning("scope_guard.out_of_scope", target=target)

    return valid, rejected


async def check_targets(
    db: AsyncSession,
    engagement_id: Any,
    targets: list[str],
) -> tuple[list[str], list[str]]:
    """Full scope check: fetch scope from DB then validate targets.

    Returns:
        Tuple of (valid_targets, rejected_targets).
    """
    included, excluded = await get_engagement_scope(db, engagement_id)
    return validate_targets(targets, included, excluded)


def scope_guard(func):
    """Decorator for plugin run methods that enforces scope validation.

    The decorated function must accept `inputs` dict with a `targets` key,
    and `engagement_id` + `db` params (or in inputs).

    Rejected targets are removed from the inputs before the function runs.
    """

    @functools.wraps(func)
    async def wrapper(self, inputs: dict, run_id: Any, publish: Any, **kwargs):
        engagement_id = inputs.get("engagement_id")
        db = kwargs.get("db")
        targets = inputs.get("targets", [])

        if not targets:
            return await func(self, inputs, run_id, publish, **kwargs)

        if db and engagement_id:
            valid, rejected = await check_targets(db, engagement_id, targets)
            if rejected:
                logger.warning(
                    "scope_guard.targets_rejected",
                    plugin=getattr(self, "manifest", {}).name
                    if hasattr(self, "manifest")
                    else "unknown",
                    rejected=rejected,
                    valid_count=len(valid),
                )
                if publish:
                    await publish({
                        "type": "output",
                        "line": f"[ScopeGuard] Rejected {len(rejected)} out-of-scope targets",
                    })
            inputs = {**inputs, "targets": valid}
        else:
            # Without DB context, at least run hard-block checks
            validated = []
            for t in targets:
                try:
                    try:
                        ipaddress.ip_address(t)
                        ScopeValidator.validate("ip", t)
                    except ValueError:
                        ScopeValidator.validate("domain", t)
                    validated.append(t)
                except ScopeValidationError:
                    logger.warning("scope_guard.hard_blocked", target=t)
            inputs = {**inputs, "targets": validated}

        if not inputs.get("targets"):
            logger.warning("scope_guard.no_valid_targets")
            if publish:
                await publish({
                    "type": "error",
                    "message": "No valid targets after scope validation",
                })
            return {"status": "skipped", "reason": "no_valid_targets"}

        return await func(self, inputs, run_id, publish, **kwargs)

    return wrapper
