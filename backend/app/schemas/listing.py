from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from app.utils.contact import CONTACT_TYPES, CONTACT_VALUE_MAX, normalize_contact
from app.utils.errors import FieldErrors


class ResidentBrief(BaseModel):
    display_name: str
    profile_complete: bool


DORM_FIELDS = ("building", "room_number", "floor", "is_corner", "windows_count", "view", "layout")
DORM_REQUIRED = ("building", "room_number", "floor")
APARTMENT_FIELDS = ("district", "monthly_cost_per_person_rub")
VIEWS = ("forest", "road", "yard", "other", "unknown")


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
    contact, contact_error = normalize_contact(data.contact_type, data.contact_value)
    if contact_error:
        errors["contact_type" if data.contact_type not in CONTACT_TYPES else "contact_value"] = contact_error
    if data.status and data.status not in ("active", "paused"):
        errors["status"] = "status: active или paused"
    return errors


class ListingFields(BaseModel):
    capacity: int = Field(..., ge=1, le=10)
    occupied_count: int = Field(..., ge=1)
    contact_type: str
    contact_value: str = Field(..., min_length=1, max_length=CONTACT_VALUE_MAX)
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
    def normalize_contact_value(self) -> "ListingFields":
        # Ошибки формата контакта собирает listing_field_errors, здесь только нормализация.
        normalized, _ = normalize_contact(self.contact_type, self.contact_value)
        if normalized is not None:
            self.contact_value = normalized
        return self


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
    contact_type: str
    contact_value: str
    status: str
    version: int
    residents: List[ResidentBrief] = []
    confirmed_at: datetime
    expires_at: datetime  # confirmed_at + LISTING_TTL_DAYS: после этого карточка скрыта
    created_at: datetime


class ConfirmRequest(BaseModel):
    expected_version: int


class InviteRequest(BaseModel):
    expected_version: int


class InviteResponse(BaseModel):
    invite_url: str
    expires_at: datetime
    version: int


class MineListingResponse(BaseModel):
    item: Optional[ListingOwner] = None
