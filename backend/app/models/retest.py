import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, ForeignKey, Text, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Retest(Base):
    __tablename__ = "retests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    tester_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    # pending | in-progress | passed | failed | n/a

    fix_claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_claim_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    repro_script: Mapped[str | None] = mapped_column(Text, nullable=True)

    due_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    finding: Mapped["Finding"] = relationship(back_populates="retests")
    tester: Mapped["User | None"] = relationship()
    history: Mapped[list["RetestHistory"]] = relationship(back_populates="retest", cascade="all, delete-orphan")


class RetestHistory(Base):
    __tablename__ = "retest_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("retests.id", ondelete="CASCADE"), nullable=False, index=True)
    tester_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    retest: Mapped["Retest"] = relationship(back_populates="history")
    tester: Mapped["User | None"] = relationship()
