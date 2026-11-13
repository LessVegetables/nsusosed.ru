from __future__ import annotations
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.auth import Language, clean_name


class Contact(BaseModel):
    type: str
    value: str
    url: Optional[str] = None  # tel:, t.me/…; None where the messenger has no profile links


class ContactIn(BaseModel):
    type: str = Field(..., max_length=10)
    value: str = Field(..., max_length=200)


class ContactsUpdate(BaseModel):
    """The whole list at once, in display order."""

    contacts: list[ContactIn] = Field(..., max_length=7)


class UserSelf(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    language: str
    gender: Optional[str] = None
    faculty: Optional[str] = None
    is_adult: Optional[bool] = None
    intent: Optional[str] = None
    bio: str
    avatar_url: Optional[str] = None
    contacts: list[Contact] = []
    # The home this person lives in (as a host), if any.
    home_id: Optional[UUID] = None
    # Has answers for the current questionnaire version.
    questionnaire_complete: bool


class UserUpdate(BaseModel):
    """Partial update: only the fields that were sent change."""

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    language: Optional[Language] = None
    gender: Optional[Literal["m", "f"]] = None
    faculty: Optional[str] = Field(default=None, max_length=20)
    is_adult: Optional[bool] = None
    intent: Optional[Literal["seek_dorm", "seek_apt", "host", "join"]] = None
    bio: Optional[str] = Field(default=None, max_length=500)

    _clean = field_validator("first_name", "last_name", mode="before")(clean_name)

    @field_validator("bio")
    @classmethod
    def strip_bio(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v is not None else None


class UserDeleteRequest(BaseModel):
    confirm: str

    def is_confirmed(self) -> bool:
        return self.confirm == "DELETE"
