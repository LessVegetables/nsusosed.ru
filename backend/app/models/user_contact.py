from __future__ import annotations
import uuid
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserContact(Base):
    """One way to reach a person off the site. At most one per type."""

    __tablename__ = "user_contacts"
    __table_args__ = (UniqueConstraint("user_id", "type", name="uq_user_contacts_user_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)

    user: Mapped["User"] = relationship(back_populates="contacts")
