from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel


class JoinRequest(BaseModel):
    invite_token: str


class JoinResponse(BaseModel):
    listing_id: UUID
    version: int
