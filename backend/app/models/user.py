from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, String, DateTime, Integer, CheckConstraint, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

LANGUAGES = ("ru", "en", "zh")
GENDERS = ("m", "f")
# What the person came for. One person can be both a host and a seeker; this is only
# the page they land on after login.
INTENTS = ("seek_dorm", "seek_apt", "host", "join")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("language", LANGUAGES), name="ck_users_language"),
        CheckConstraint(_in("gender", GENDERS), name="ck_users_gender"),
        CheckConstraint(_in("intent", INTENTS), name="ck_users_intent"),
        Index("ix_users_deleted_at", "deleted_at", postgresql_where=text("deleted_at IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="ru")
    # Filled in during onboarding; None = not asked yet.
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    faculty: Mapped[str | None] = mapped_column(String(20), nullable=True)  # id from config/faculties.json
    # Gates the nicotine questions. We ask "are you 18?", never a birth date.
    is_adult: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bio: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    avatar_file: Mapped[str | None] = mapped_column(String(64), nullable=True)
    privacy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    privacy_accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Asked to delete the account. Hidden right away, restored by logging in during the
    # grace period, erased for good after it (purge_deleted_accounts).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
