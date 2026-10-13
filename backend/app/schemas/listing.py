from __future__ import annotations
import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class ResidentBrief(BaseModel):
    display_name: str
    profile_complete: bool


class ListingInput(BaseModel):
    kind: str
    capacity: int = Field(..., ge=1, le=10)
    occupied_count: int = Field(..., ge=1)
    contact_username: str = Field(..., min_length=5, max_length=32)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default="active")
    building: Optional[str] = Field(default=None, max_length=20)
    room_number: Optional[int] = Field(default=None, ge=1, le=999)
    floor: Optional[int] = Field(default=None, ge=1, le=999)
    is_corner: Optional[bool] = None
    windows_count: Optional[int] = Field(default=None, ge=1, le=5)
    view: Optional[str] = None
    layout: Optional[str] = Field(default=None, max_length=300)
    district: Optional[str] = Field(default=None, max_length=80)
    monthly_cost_per_person_rub: Optional[int] = Field(default=None, ge=1, le=200000)

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "ListingInput":
        if self.kind == "dorm":
            if not self.building or not self.room_number or self.floor is None:
                raise ValueError("Для общежития обязательны building, room_number, floor")
            if self.view and self.view not in ("forest", "road", "yard", "other", "unknown"):
                raise ValueError("view: forest|road|yard|other|unknown")
            if self.district is not None or self.monthly_cost_per_person_rub is not None:
                raise ValueError("Для общежития поля квартиры должны быть null")
        elif self.kind == "apartment":
            if not self.district or self.monthly_cost_per_person_rub is None:
                raise ValueError("Для квартиры обязательны district и monthly_cost_per_person_rub")
            if any(v is not None for v in [self.building, self.room_number, self.floor, self.is_corner, self.windows_count, self.view, self.layout]):
                raise ValueError("Для квартиры поля общежития должны быть null")
        else:
            raise ValueError("kind должен быть dorm или apartment")
        if self.occupied_count > self.capacity:
            raise ValueError("occupied_count не может превышать capacity")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", self.contact_username):
            raise ValueError("contact_username: 5-32 символа, латинские буквы, цифры, _")
        if self.status and self.status not in ("active", "paused"):
            raise ValueError("status: active или paused")
        return self


class ListingUpdate(BaseModel):
    capacity: int = Field(..., ge=1, le=10)
    occupied_count: int = Field(..., ge=1)
    contact_username: str = Field(..., min_length=5, max_length=32)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default="active")
    expected_version: int
    building: Optional[str] = Field(default=None, max_length=20)
    room_number: Optional[int] = Field(default=None, ge=1, le=999)
    floor: Optional[int] = Field(default=None, ge=1, le=999)
    is_corner: Optional[bool] = None
    windows_count: Optional[int] = Field(default=None, ge=1, le=5)
    view: Optional[str] = None
    layout: Optional[str] = Field(default=None, max_length=300)
    district: Optional[str] = Field(default=None, max_length=80)
    monthly_cost_per_person_rub: Optional[int] = Field(default=None, ge=1, le=200000)

    @model_validator(mode="after")
    def validate(self) -> "ListingUpdate":
        if self.occupied_count > self.capacity:
            raise ValueError("occupied_count не может превышать capacity")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", self.contact_username):
            raise ValueError("contact_username: неверный формат")
        return self


class ListingOwner(BaseModel):
    id: UUID
    owner_id: UUID
    kind: str
    building: Optional[str] = None
    room_number: Optional[int] = None
    floor: Optional[int] = None
    capacity: int
    occupied_count: int
    free_places: int
    answered_count: int
    is_corner: Optional[bool] = None
    windows_count: Optional[int] = None
    view: Optional[str] = None
    layout: Optional[str] = None
    district: Optional[str] = None
    monthly_cost_per_person_rub: Optional[int] = None
    description: Optional[str] = None
    contact_username: str
    status: str
    version: int
    residents: List[ResidentBrief] = []
    confirmed_at: datetime
    created_at: datetime


class InviteRequest(BaseModel):
    expected_version: int


class InviteResponse(BaseModel):
    invite_url: str
    expires_at: datetime
    version: int


class MineListingResponse(BaseModel):
    item: Optional[ListingOwner] = None
