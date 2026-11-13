from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

HOME_KINDS = ("dorm", "apartment")
ROOM_GENDERS = ("m", "f", "any")


class Home(Base):
    """What a host manages as one page: a dorm room, or an apartment with one or more rooms.

    What is never stored: a street address, an apartment number, the exact point of an
    apartment. An apartment has only a district and a circle on the map that the host's
    browser moved off the real spot before sending it.
    """

    __tablename__ = "homes"
    __table_args__ = (
        CheckConstraint("kind IN ('dorm', 'apartment')", name="ck_homes_kind"),
        # A dorm room can be listed once. room_label never leaves the server.
        Index("uq_homes_dorm_room", "building", "room_label", unique=True, postgresql_where=text("kind = 'dorm'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Dorm: building id from config/dorms.json (shown) and the room as residents say it,
    # "200", "100б", "100м" (hidden; only for the duplicate check).
    building: Mapped[str | None] = mapped_column(String(20), nullable=True)
    room_label: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Apartment: district name and the obfuscated circle.
    district: Mapped[str | None] = mapped_column(String(60), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    utilities_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)   # included | split
    utilities_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)       # approx. per person a month
    internet_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)    # included | split | none

    rooms: Mapped[list["Room"]] = relationship(back_populates="home", cascade="all, delete-orphan",
                                               order_by="Room.position", lazy="selectin")
    photos: Mapped[list["HomePhoto"]] = relationship(back_populates="home", cascade="all, delete-orphan",
                                                     order_by="HomePhoto.position", lazy="selectin")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="home", cascade="all, delete-orphan",
                                                           order_by="Membership.joined_at", lazy="selectin")


class Room(Base):
    """What a seeker sees as one listing. A dorm home has exactly one."""

    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("gender IN ('m', 'f', 'any')", name="ck_rooms_gender"),
        CheckConstraint("capacity BETWEEN 1 AND 6 AND free_places BETWEEN 0 AND capacity", name="ck_rooms_places"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("homes.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    gender: Mapped[str] = mapped_column(String(3), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    free_places: Mapped[int] = mapped_column(Integer, nullable=False)
    rent_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)  # apartments: per place a month
    # Three emojis people use to tell listings apart. A label, never a key.
    emoji: Mapped[str] = mapped_column(String(40), nullable=False)
    emoji_key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)  # order-independent

    home: Mapped["Home"] = relationship(back_populates="rooms")


class Membership(Base):
    """A person living in a home (a host). One home per person."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", name="uq_memberships_user"),)

    home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("homes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # What this host may change. The person who creates the home gets everything.
    can_edit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)       # the listing's fields
    can_photos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)     # add, remove, reorder photos
    can_invites: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)    # invite links
    can_residents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # remove people, change rights

    home: Mapped["Home"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(lazy="selectin")


class Invite(Base):
    """A link a host sends to a roommate so they can attach themselves to the home.
    Works for anyone who has it until it expires or is revoked; only its hash is stored."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("homes.id", ondelete="CASCADE"), nullable=False, index=True)
    # The room the invited person lives in (apartments); None = the home's first room.
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HomePhoto(Base):
    __tablename__ = "home_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("homes.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    home: Mapped["Home"] = relationship(back_populates="photos")
