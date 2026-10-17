from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from app.utils.contact import CONTACT_TYPES, CONTACT_VALUE_MAX, normalize_contact
from app.utils.errors import FieldErrors


MAX_CONTACTS = 10


class ResidentBrief(BaseModel):
    display_name: str
    profile_complete: bool
    is_admin: bool = False


class HomeResident(ResidentBrief):
    """Жилец в том виде, в каком его видят другие жильцы (с id для действий админа)."""
    user_id: UUID
    joined_at: datetime


class ContactItem(BaseModel):
    type: str
    value: str = Field(..., max_length=CONTACT_VALUE_MAX)


class ContactOut(BaseModel):
    type: str
    value: str
    url: Optional[str] = None


class PhotoOut(BaseModel):
    id: UUID
    url: str
    width: int
    height: int


DORM_FIELDS = ("building", "room_number", "floor", "is_corner", "windows_count", "view", "layout")
DORM_REQUIRED = ("building", "room_number", "floor")
APARTMENT_FIELDS = ("district", "monthly_cost_per_person_rub")
VIEWS = ("forest", "road", "yard", "other", "unknown")


def listing_field_errors(kind: str, data: "ListingFields") -> Dict[str, str]:
    """Проверки, общие для создания и изменения карточки. Возвращает {поле: КОД_ПРИЧИНЫ}."""
    errors: Dict[str, str] = {}
    if kind == "dorm":
        for f in DORM_REQUIRED:
            if getattr(data, f) in (None, ""):
                errors[f] = "REQUIRED"
        for f in APARTMENT_FIELDS:
            if getattr(data, f) is not None:
                errors[f] = "MUST_BE_EMPTY"
        if data.view is not None and data.view not in VIEWS:
            errors["view"] = "INVALID_CHOICE"
    elif kind == "apartment":
        for f in APARTMENT_FIELDS:
            if getattr(data, f) is None:
                errors[f] = "REQUIRED"
        for f in DORM_FIELDS:
            if getattr(data, f) is not None:
                errors[f] = "MUST_BE_EMPTY"
    else:
        errors["kind"] = "INVALID_CHOICE"
    if data.occupied_count > data.capacity:
        errors["occupied_count"] = "EXCEEDS_CAPACITY"
    for i, contact in enumerate(data.contacts):
        _, contact_error = normalize_contact(contact.type, contact.value)
        if contact_error:
            errors[f"contacts.{i}.{'type' if contact.type not in CONTACT_TYPES else 'value'}"] = contact_error
    if data.status and data.status not in ("active", "paused"):
        errors["status"] = "INVALID_CHOICE"
    return errors


class ListingFields(BaseModel):
    capacity: int = Field(..., ge=1, le=10)
    occupied_count: int = Field(..., ge=1)
    contacts: List[ContactItem] = Field(..., min_length=1, max_length=MAX_CONTACTS)
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
    def normalize_contact_values(self) -> "ListingFields":
        # Ошибки формата контактов собирает listing_field_errors, здесь только нормализация.
        for contact in self.contacts:
            normalized, _ = normalize_contact(contact.type, contact.value)
            if normalized is not None:
                contact.value = normalized
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
    """Жильё глазами его жильца. Менять его могут только админы (you_are_admin)."""
    id: UUID
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
    contacts: List[ContactOut] = []
    photos: List[PhotoOut] = []
    status: str
    version: int
    residents: List[HomeResident] = []
    you_are_admin: bool
    confirmed_at: datetime
    expires_at: datetime  # confirmed_at + LISTING_TTL_DAYS: после этого карточка скрыта
    created_at: datetime


class ConfirmRequest(BaseModel):
    expected_version: int


class PhotoOrder(BaseModel):
    """Все фото жилья в новом порядке; первое — обложка."""
    photo_ids: List[UUID]


class InviteRequest(BaseModel):
    expected_version: int


class InviteResponse(BaseModel):
    invite_url: str
    expires_at: datetime
    version: int


class MineListingResponse(BaseModel):
    item: Optional[ListingOwner] = None
