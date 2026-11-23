from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ContactReveal(Base):
    """Who got whose contacts, and when: one row per "Показать контакты".

    For safety only: complaints and requests from the authorities. Never shown on the site.
    Kept CONTACT_REVEAL_RETENTION (3 years, as /privacy says), including after either account
    or the home is deleted. That's why the emails are copied in and home_id/room_id have no
    foreign keys: nothing here may cascade away with the account or the home.
    """

    __tablename__ = "contact_reveals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    viewer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # The residents whose contacts were shown.
    host_emails: Mapped[list[str]] = mapped_column(ARRAY(String(254)), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
