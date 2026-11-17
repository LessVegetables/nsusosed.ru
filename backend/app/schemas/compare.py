from __future__ import annotations
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.feed import Compatibility


class CompareCode(BaseModel):
    """The code, or the whole link pasted in."""

    code: str = Field(..., min_length=1, max_length=300)


class CompareMemberOut(BaseModel):
    user_id: UUID
    first_name: str
    avatar_url: Optional[str] = None
    is_you: bool
    # Questionnaire progress: required questions answered of those that apply. Counts only,
    # never which answers: nobody sees anything of anyone's answers before both are done.
    complete: bool
    answered: int
    total: int
    # The viewer against this person, once both have finished. None for yourself.
    compatibility: Optional[Compatibility] = None
    # Their visible answers ({question id: option index}) for the side-by-side, once both have
    # finished; hidden ones never leave the server. Empty for yourself.
    answers: dict[str, int] = {}


class CompareGroupOut(BaseModel):
    id: UUID
    code: str
    url: str
    created_by_you: bool
    members: list[CompareMemberOut]
    # The viewer against everyone else who has finished, scored like a room. Only with two or
    # more such people; with one it is the same as their own result.
    compatibility: Optional[Compatibility] = None
    # The viewer's own visible answers, once they have finished.
    my_answers: dict[str, int] = {}
