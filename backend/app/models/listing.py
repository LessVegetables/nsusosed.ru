from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Text, func, text, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("capacity BETWEEN 1 AND 10", name="ck_listings_capacity"),
        CheckConstraint("occupied_count BETWEEN 1 AND capacity", name="ck_listings_occupied"),
        CheckConstraint("kind IN ('dorm', 'apartment')", name="ck_listings_kind"),
        CheckConstraint("status IN ('active', 'paused')", name="ck_listings_status"),
        CheckConstraint("contact_type IN ('telegram', 'whatsapp', 'max', 'phone', 'other')", name="ck_listings_contact_type"),
        # Одна карточка на комнату общежития (у квартир building/room_number пустые).
        Index("uq_listings_dorm_addr", "building", "room_number", unique=True,
              postgresql_where=text("building IS NOT NULL AND room_number IS NOT NULL")),
        Index("ix_listings_kind_status_confirmed", "kind", "status", "confirmed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied_count: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_type: Mapped[str] = mapped_column(String(10), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    building: Mapped[str | None] = mapped_column(String(20), nullable=True)
    room_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_corner: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    windows_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view: Mapped[str | None] = mapped_column(String(10), nullable=True)
    layout: Mapped[str | None] = mapped_column(String(300), nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    monthly_cost_per_person_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="owned_listing")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
