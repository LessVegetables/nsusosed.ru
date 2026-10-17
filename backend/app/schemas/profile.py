from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from app.config import QUESTIONNAIRE
from app.utils.errors import FieldErrors

QUESTION_KEYS = [q["key"] for q in QUESTIONNAIRE["questions"]]
# seeker — ищет жильё; host — живёт в жилье и ищет соседей (участник жилья всегда host).
SITUATIONS = ["seeker", "host"]


class AnswerItem(BaseModel):
    value: int
    importance: int = Field(..., ge=1, le=10)
    hard: bool
    allowed: List[int] = []

    @model_validator(mode="after")
    def check_hard_allowed(self) -> "AnswerItem":
        if self.hard and len(self.allowed) == 0:
            raise FieldErrors({"allowed": "REQUIRED_WHEN_HARD"})
        if not self.hard and len(self.allowed) > 0:
            raise FieldErrors({"allowed": "MUST_BE_EMPTY"})
        if len(self.allowed) != len(set(self.allowed)):
            raise FieldErrors({"allowed": "DUPLICATES"})
        return self


class ProfileInput(BaseModel):
    questionnaire_version: int = Field(default=QUESTIONNAIRE["version"])
    expected_version: int = Field(..., ge=0)
    situation: str
    budget_max_rub: Optional[int] = Field(default=None, ge=1, le=200000)
    answers: Dict[str, AnswerItem]

    @model_validator(mode="after")
    def validate_answers(self) -> "ProfileInput":
        if self.questionnaire_version != QUESTIONNAIRE["version"]:
            raise FieldErrors({"questionnaire_version": "UNSUPPORTED_VERSION"})
        if set(self.answers.keys()) != set(QUESTION_KEYS):
            raise FieldErrors({"answers": "INVALID_QUESTION_SET"})
        q_map = {q["key"]: q for q in QUESTIONNAIRE["questions"]}
        errors: Dict[str, str] = {}
        for key, ans in self.answers.items():
            q = q_map[key]
            if not (q["min_value"] <= ans.value <= q["max_value"]):
                errors[f"answers.{key}.value"] = "OUT_OF_SCALE"
            if any(not (q["min_value"] <= a <= q["max_value"]) for a in ans.allowed):
                errors[f"answers.{key}.allowed"] = "OUT_OF_SCALE"
        if errors:
            raise FieldErrors(errors)
        return self

    @model_validator(mode="after")
    def validate_situation(self) -> "ProfileInput":
        if self.situation not in SITUATIONS:
            raise FieldErrors({"situation": "INVALID_CHOICE"})
        return self


class ProfileSelf(BaseModel):
    user_id: UUID
    questionnaire_version: int
    answers: Dict[str, Any]
    situation: str
    budget_max_rub: Optional[int] = None
    version: int
    updated_at: datetime


class ProfileResponse(BaseModel):
    profile: Optional[ProfileSelf] = None
