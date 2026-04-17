import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.database import Base


class VaultItem(Base):
    __tablename__ = "vault_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # password | token | apikey | key | file

    # All sensitive fields encrypted at rest via AES-256-GCM
    username_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    notes_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    engagement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="SET NULL"), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    engagement: Mapped["Engagement | None"] = relationship()
    target: Mapped["Target | None"] = relationship(back_populates="vault_items")
    owner: Mapped["User | None"] = relationship()
    access_log: Mapped[list["VaultAccessLog"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class VaultAccessLog(Base):
    __tablename__ = "vault_access_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vault_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # revealed | copied | rotated | created | updated | deleted | auto-locked
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    item: Mapped["VaultItem"] = relationship(back_populates="access_log")
    user: Mapped["User | None"] = relationship()
