from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AuthEvent(Base):
    """Журнал запросов к /api/auth/* для ограничения частоты (общий для всех воркеров)."""

    __tablename__ = "auth_events"
    __table_args__ = (
        Index("ix_auth_events_email_kind_created", "email", "kind", "created_at"),
        Index("ix_auth_events_ip_created", "ip", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # code_request | verify_ok | verify_fail
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
