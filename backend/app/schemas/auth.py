from __future__ import annotations
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.utils.errors import FieldErrors

Language = Literal["ru", "en", "zh"]


def clean_name(v):
    """Collapse whitespace before the length checks, so "   " counts as empty."""
    return " ".join(v.split()) if isinstance(v, str) else v


class RequestCodeRequest(BaseModel):
    email: str = Field(..., max_length=254)
    privacy_accepted: bool
    # Language of the email; the page's current language.
    language: Optional[Language] = None

    @field_validator("privacy_accepted")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise FieldErrors({"": "MUST_ACCEPT"})
        return v


class VerifyCodeRequest(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., min_length=4, max_length=10)
    # First login only: the name asked while the code is on its way.
    first_name: Optional[str] = Field(default=None, max_length=40)
    last_name: Optional[str] = Field(default=None, max_length=40)
    # Sent when the person picked a language on the landing or login page.
    language: Optional[Language] = None

    _clean = field_validator("first_name", "last_name", mode="before")(clean_name)


class RequestCodeResponse(BaseModel):
    email_masked: str
    ttl_seconds: int
    # No account yet: the login page asks for a name before the code.
    is_new: bool


class AuthResponse(BaseModel):
    user_id: UUID
    first_name: str
    is_new: bool
    # Enough for the login page to send the person to their own page.
    questionnaire_complete: bool
    intent: Optional[str] = None
    # The account was waiting to be erased and this login restored it.
    account_restored: bool = False
