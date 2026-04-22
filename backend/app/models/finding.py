"""Finding model: stores vulnerabilities discovered during engagement runs."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FindingSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class FindingStatus(str, enum.Enum):
    suggested = "suggested"
    open = "open"
    confirmed = "confirmed"
    false_positive = "false_positive"
    remediated = "remediated"
    accepted_risk = "accepted_risk"


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_engagement_id", "engagement_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_status", "status"),
        Index("ix_findings_run_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engagement_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FindingSeverity.info.value
    )
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cvss_vector: Mapped[str | None] = mapped_column(String(256), nullable=True)
    epss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    epss_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    cve_ids: Mapped[list] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    cisa_kev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attack_technique_ids: Mapped[list] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    affected_target: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # JSONB: screenshots, output snippets, request/response pairs
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FindingStatus.open.value
    )
    discovered_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # UUIDs of findings that were merged into this one
    deduplicated_from: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    # Analyst notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    engagement = relationship("Engagement", foreign_keys=[engagement_id])
    run = relationship("EngagementRun", foreign_keys=[run_id])
