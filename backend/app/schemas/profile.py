from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

QUESTION_KEYS = ["sleep", "noise", "cleanliness", "guests", "smoking", "alcohol", "study", "airing", "temperature"]
SITUATIONS = ["looking", "dorm_resident", "apartment_host"]


class AnswerItem(BaseModel):
    value: int
    importance: int = Field(..., ge=1, le=10)
    hard: bool
    allowed: List[int] = []

    @model_validator(mode="after")
    def check_hard_allowed(self) -> "AnswerItem":
        if self.hard and len(self.allowed) == 0:
            raise ValueError("Для hard=true список allowed не может быть пустым")
        if not self.hard and len(self.allowed) > 0:
            raise ValueError("Для hard=false список allowed должен быть пустым")
        if len(self.allowed) != len(set(self.allowed)):
            raise ValueError("allowed должен содержать уникальные значения")
        return self


class ProfileInput(BaseModel):
    questionnaire_version: int = Field(default=1)
    expected_version: int = Field(..., ge=0)
    situation: str
    budget_max_rub: Optional[int] = Field(default=None, ge=1, le=200000)
    answers: Dict[str, AnswerItem]

    @model_validator(mode="after")
    def validate_answers(self) -> "ProfileInput":
        if self.questionnaire_version != 1:
            raise ValueError("Поддерживается только версия анкеты 1")
        if set(self.answers.keys()) != set(QUESTION_KEYS):
            raise ValueError("Неверный набор вопросов")
        from app.config import QUESTIONNAIRE_V1
        q_map = {q["key"]: q for q in QUESTIONNAIRE_V1["questions"]}
        for key, ans in self.answers.items():
            q = q_map[key]
            if not (q["min_value"] <= ans.value <= q["max_value"]):
                raise ValueError(f"{key}.value: допустимо от {q['min_value']} до {q['max_value']}")
            for a in ans.allowed:
                if not (q["min_value"] <= a <= q["max_value"]):
                    raise ValueError(f"{key}.allowed: значение {a} вне шкалы")
        return self

    @model_validator(mode="after")
    def validate_situation(self) -> "ProfileInput":
        if self.situation not in SITUATIONS:
            raise ValueError(f"situation должен быть одним из: {SITUATIONS}")
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
