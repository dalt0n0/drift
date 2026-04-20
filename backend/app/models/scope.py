from __future__ import annotations

import enum
import ipaddress
import os
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScopeType(str, enum.Enum):
    cidr = "cidr"
    domain = "domain"
    url = "url"
    ip = "ip"
    wildcard = "wildcard"


class ScopeItem(Base):
    __tablename__ = "scope_items"
    __table_args__ = (
        Index("ix_scope_items_engagement_id", "engagement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    engagement = relationship("Engagement", back_populates="scope_items")


# ---------------------------------------------------------------------------
# Scope Validator
# ---------------------------------------------------------------------------

# Hard-blocked CIDRs — cannot be overridden
BLOCKED_CIDRS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "169.254.0.0/16",
    "fe80::/10",
    "100.64.0.0/10",
    "169.254.169.254/32",
    "fd00:ec2::254/128",
]

# RFC 1918 ranges specifically — can be allowed with ALLOW_RFC1918=true
RFC1918_CIDRS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]

# Hard-blocked TLDs
BLOCKED_TLDS = [".gov", ".mil"]

# Hard-blocked domains
BLOCKED_DOMAINS = ["metadata.google.internal", "metadata.azure.com"]

_BLOCKED_NETWORKS = [ipaddress.ip_network(c, strict=False) for c in BLOCKED_CIDRS]
_RFC1918_NETWORKS = [ipaddress.ip_network(c, strict=False) for c in RFC1918_CIDRS]


class ScopeValidationError(Exception):
    """Raised when a scope item fails validation."""

    def __init__(self, message: str, blocked_reason: str = "hard_block"):
        super().__init__(message)
        self.blocked_reason = blocked_reason


class ScopeValidator:
    """Validates scope items against hard-block lists."""

    @staticmethod
    def _allow_rfc1918() -> bool:
        return os.environ.get("ALLOW_RFC1918", "").lower() in ("true", "1", "yes")

    @classmethod
    def _is_rfc1918(cls, network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
        for rfc in _RFC1918_NETWORKS:
            if network.version == rfc.version and network.subnet_of(rfc):
                return True
        return False

    @classmethod
    def _check_ip_or_cidr(cls, value: str) -> None:
        """Validate an IP address or CIDR against blocked ranges."""
        try:
            # Try as network first
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            try:
                addr = ipaddress.ip_address(value)
                network = ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}", strict=False)
            except ValueError:
                raise ScopeValidationError(f"Invalid IP/CIDR: {value}")

        for blocked in _BLOCKED_NETWORKS:
            if network.version != blocked.version:
                continue
            # Check if the target overlaps with a blocked range
            if network.overlaps(blocked):
                # If it's RFC 1918 and the flag is set, allow it
                if cls._allow_rfc1918() and cls._is_rfc1918(network):
                    continue
                raise ScopeValidationError(
                    f"Target {value} overlaps with blocked range {blocked}",
                    blocked_reason="hard_block",
                )

    @classmethod
    def _check_domain(cls, value: str) -> None:
        """Validate a domain against blocked TLDs and domains."""
        domain = value.lower().strip().rstrip(".")

        for blocked_tld in BLOCKED_TLDS:
            if domain.endswith(blocked_tld) or domain == blocked_tld.lstrip("."):
                raise ScopeValidationError(
                    f"Domain {value} uses blocked TLD {blocked_tld}",
                    blocked_reason="hard_block",
                )

        for blocked_domain in BLOCKED_DOMAINS:
            if domain == blocked_domain or domain.endswith(f".{blocked_domain}"):
                raise ScopeValidationError(
                    f"Domain {value} matches blocked domain {blocked_domain}",
                    blocked_reason="hard_block",
                )

    @classmethod
    def _check_url(cls, value: str) -> None:
        """Extract domain from URL and validate."""
        # Simple URL domain extraction
        match = re.match(r"https?://([^/:]+)", value)
        if match:
            domain = match.group(1)
            # Check if it's an IP
            try:
                ipaddress.ip_address(domain)
                cls._check_ip_or_cidr(domain)
                return
            except ValueError:
                pass
            cls._check_domain(domain)
        else:
            raise ScopeValidationError(f"Invalid URL format: {value}")

    @classmethod
    def _check_wildcard(cls, value: str) -> None:
        """Validate wildcard domain (e.g., *.example.com)."""
        # Strip wildcard prefix
        if value.startswith("*."):
            domain = value[2:]
        else:
            domain = value
        cls._check_domain(domain)

    @classmethod
    def validate(cls, scope_type: str, value: str) -> None:
        """Validate a single scope item. Raises ScopeValidationError on failure."""
        if scope_type in (ScopeType.cidr.value, ScopeType.ip.value):
            cls._check_ip_or_cidr(value)
        elif scope_type == ScopeType.domain.value:
            cls._check_domain(value)
        elif scope_type == ScopeType.url.value:
            cls._check_url(value)
        elif scope_type == ScopeType.wildcard.value:
            cls._check_wildcard(value)
        else:
            raise ScopeValidationError(f"Unknown scope type: {scope_type}")

    @classmethod
    def validate_batch(cls, items: list[dict]) -> list[dict]:
        """Validate multiple scope items. Returns list of error dicts for failures."""
        errors = []
        for item in items:
            try:
                cls.validate(item["type"], item["value"])
            except ScopeValidationError as e:
                errors.append({
                    "type": item["type"],
                    "value": item["value"],
                    "error": str(e),
                    "blocked_reason": e.blocked_reason,
                })
        return errors
