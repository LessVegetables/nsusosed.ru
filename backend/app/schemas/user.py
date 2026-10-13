from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


class UserSelf(BaseModel):
    id: UUID
    email: str
    display_name: str


class UserUpdate(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=60)


class UserDeleteRequest(BaseModel):
    confirm: str

    def is_confirmed(self) -> bool:
        return self.confirm == "DELETE"
