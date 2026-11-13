from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class QuestionnaireOut(BaseModel):
    version: int
    blocks: list[dict]
    questions: list[dict]
    # The person's own answers for this version ({} if none yet), hidden ones included.
    answers: dict[str, Any]
    complete: bool
    # Required questions still unanswered, in order.
    missing: list[str]


class AnswersIn(BaseModel):
    version: int
    # May be partial: the page saves the main part first and the optional questions later.
    answers: dict[str, Any] = Field(..., max_length=40)
