from __future__ import annotations
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class UserHome(BaseModel):
    id: UUID
    is_admin: bool


class UserSelf(BaseModel):
    id: UUID
    email: str
    display_name: str
    language: Optional[str] = None  # None — ещё не выбран
    situation: Optional[str] = None  # seeker | host; None — анкеты нет
    profile_complete: bool  # есть анкета текущей версии
    home: Optional[UserHome] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=60)
    language: Optional[Literal["ru", "en"]] = None


class UserDeleteRequest(BaseModel):
    confirm: str

    def is_confirmed(self) -> bool:
        return self.confirm == "DELETE"
