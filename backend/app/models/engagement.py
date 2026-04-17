import uuid
from datetime import date, datetime
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    client: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # type: External Web App | Internal Network | Mobile App | API | Cloud | Physical

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    # status: active | paused | completed | archived

    phase: Mapped[str] = mapped_column(String(32), default="Scoping", nullable=False)
    # phase: Scoping | Recon | Discovery | Exploitation | Reporting | Review

    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    scope_in: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope_out: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rules_of_engagement: Mapped[str] = mapped_column(Text, default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["EngagementMember"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    targets: Mapped[list["Target"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    activity: Mapped[list["Activity"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")


class EngagementMember(Base):
    __tablename__ = "engagement_members"

    engagement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), default="tester", nullable=False)

    engagement: Mapped["Engagement"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()
