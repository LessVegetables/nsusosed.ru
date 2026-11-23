from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EmailLog(Base):
    """One row per login-code email: to catch delivery problems.

    The general app log never gets the address (it is kept up to a month); this table does,
    and housekeeping deletes rows after EMAIL_LOG_RETENTION (3 days, as /privacy promises).
    The code itself is never stored here.
    """

    __tablename__ = "email_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # sent | failed | logged (EMAIL_MODE=log)
    message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
