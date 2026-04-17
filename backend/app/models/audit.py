import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class AuditLog(Base):
    """Immutable security audit trail — never update, never delete."""
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)  # snapshot at time of action

    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # auth.login | auth.logout | auth.login_failed | auth.mfa_failed |
    # finding.create | finding.update | finding.delete |
    # vault.reveal | vault.create | vault.rotate |
    # report.publish | report.export |
    # user.create | user.update | user.delete | user.role_change |
    # apikey.create | apikey.delete | ...

    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # sanitized — no passwords/secrets
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
