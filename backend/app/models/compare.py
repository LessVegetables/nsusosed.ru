from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CompareGroup(Base):
    """People comparing with each other with no home: a couple, friends, future flatmates.
    Whoever has the link joins (up to compare_service.MAX_MEMBERS).

    The code is stored as is, unlike an invite's: it lets someone into a comparison, not into
    a home, and the page has to show the same link again whenever it is asked for."""

    __tablename__ = "compare_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    members: Mapped[list["CompareMember"]] = relationship(back_populates="group", cascade="all, delete-orphan",
                                                          order_by="CompareMember.joined_at", lazy="selectin")


class CompareMember(Base):
    __tablename__ = "compare_members"

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("compare_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    group: Mapped["CompareGroup"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(lazy="selectin")
