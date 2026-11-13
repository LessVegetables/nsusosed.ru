from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class QuestionnaireResponse(Base):
    """A person's answers, together with the questionnaire version they answer.
    One row per person: answering a newer version replaces the old answers."""

    __tablename__ = "questionnaire_responses"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # {"A1": 2, "E1": [1, 3]}: option indices. Hidden answers live here too and never leave
    # the server except to their owner.
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())
