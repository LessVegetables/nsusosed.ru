from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint("situation IN ('seeker', 'host')", name="ck_profiles_situation"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    questionnaire_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    situation: Mapped[str] = mapped_column(String(30), nullable=False)
    budget_max_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="profile")
