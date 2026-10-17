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
        # Одна карточка на комнату общежития (у квартир building/room_number пустые).
        Index("uq_listings_dorm_addr", "building", "room_number", unique=True,
              postgresql_where=text("building IS NOT NULL AND room_number IS NOT NULL")),
        Index("ix_listings_kind_status_confirmed", "kind", "status", "confirmed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied_count: Mapped[int] = mapped_column(Integer, nullable=False)
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

    memberships: Mapped[list["Membership"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    contacts: Mapped[list["ListingContact"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="ListingContact.position")
    photos: Mapped[list["ListingPhoto"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="ListingPhoto.position")


class ListingContact(Base):
    __tablename__ = "listing_contacts"
    __table_args__ = (
        CheckConstraint("type IN ('telegram', 'whatsapp', 'max', 'phone', 'other')", name="ck_listing_contacts_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)

    listing: Mapped["Listing"] = relationship(back_populates="contacts")


class ListingPhoto(Base):
    """Файл лежит в MEDIA_DIR/listings/<listing_id>/<file_name>."""
    __tablename__ = "listing_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    listing: Mapped["Listing"] = relationship(back_populates="photos")
