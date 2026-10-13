from __future__ import annotations
import re
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from app.utils.errors import FieldErrors


class ResidentBrief(BaseModel):
    display_name: str
    profile_complete: bool


DORM_FIELDS = ("building", "room_number", "floor", "is_corner", "windows_count", "view", "layout")
DORM_REQUIRED = ("building", "room_number", "floor")
APARTMENT_FIELDS = ("district", "monthly_cost_per_person_rub")
VIEWS = ("forest", "road", "yard", "other", "unknown")
CONTACT_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")


def listing_field_errors(kind: str, data: "ListingFields") -> Dict[str, str]:
    """Проверки, общие для создания и изменения карточки. Возвращает {поле: сообщение}."""
    errors: Dict[str, str] = {}
    if kind == "dorm":
        for f in DORM_REQUIRED:
            if getattr(data, f) in (None, ""):
                errors[f] = "Обязательно для общежития"
        for f in APARTMENT_FIELDS:
            if getattr(data, f) is not None:
                errors[f] = "Для общежития должно быть пустым"
        if data.view is not None and data.view not in VIEWS:
            errors["view"] = "Допустимо: " + ", ".join(VIEWS)
    elif kind == "apartment":
        for f in APARTMENT_FIELDS:
            if getattr(data, f) is None:
                errors[f] = "Обязательно для квартиры"
        for f in DORM_FIELDS:
            if getattr(data, f) is not None:
                errors[f] = "Для квартиры должно быть пустым"
    else:
        errors["kind"] = "kind должен быть dorm или apartment"
    if data.occupied_count > data.capacity:
        errors["occupied_count"] = "occupied_count не может превышать capacity"
    if not CONTACT_USERNAME_RE.match(data.contact_username):
        errors["contact_username"] = "5-32 символа, латинские буквы, цифры, _"
    if data.status and data.status not in ("active", "paused"):
        errors["status"] = "status: active или paused"
    return errors


class ListingFields(BaseModel):
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


class ListingInput(ListingFields):
    kind: str

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "ListingInput":
        errors = listing_field_errors(self.kind, self)
        if errors:
            raise FieldErrors(errors)
        return self


class ListingUpdate(ListingFields):
    """Полная замена полей карточки. kind не меняется — проверка по нему в сервисе."""
    expected_version: int


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
