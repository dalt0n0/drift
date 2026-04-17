import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.database import Base


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True)

    host: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="Web")
    # type: Web | API | Service | CDN | Mobile | Network | Cloud

    state: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    # state: active | skipped | complete | oos (out of scope)

    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    ports: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, nullable=False)
    tech: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    last_scan: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    engagement: Mapped["Engagement"] = relationship(back_populates="targets")
    findings: Mapped[list["Finding"]] = relationship(back_populates="target")
    vault_items: Mapped[list["VaultItem"]] = relationship(back_populates="target")
