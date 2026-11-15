from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class QuestionnaireOut(BaseModel):
    version: int
    blocks: list[dict]
    # Questions drawn together under one heading (the two bedtime questions).
    groups: list[dict]
    questions: list[dict]
    # The person's own answers for this version ({} if none yet), hidden ones included.
    answers: dict[str, Any]
    complete: bool
    # Required questions still unanswered, in order.
    missing: list[str]


class AnswersIn(BaseModel):
    version: int
    # May be partial: the page saves a draft after every answer.
    answers: dict[str, Any] = Field(..., max_length=40)
    # False: these answers are added to the stored ones. True: they replace them, so an answer
    # the person took back (the last option of a multi-select unticked) is forgotten.
    replace: bool = False
