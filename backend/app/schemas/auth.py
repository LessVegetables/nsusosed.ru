from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.utils.errors import FieldErrors


class RequestCodeRequest(BaseModel):
    email: str = Field(..., max_length=254)
    privacy_accepted: bool

    @field_validator("privacy_accepted")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise FieldErrors({"": "MUST_ACCEPT"})
        return v


class VerifyCodeRequest(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., min_length=4, max_length=10)


class RequestCodeResponse(BaseModel):
    message: str
    email_masked: str
    ttl_seconds: int


class UserBrief(BaseModel):
    id: UUID
    email: str
    display_name: str


class AuthResponse(BaseModel):
    user: UserBrief
    profile_complete: bool
