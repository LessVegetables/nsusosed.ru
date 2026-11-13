from __future__ import annotations
import re
import unicodedata
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from app.config import DORMS
from app.utils import emoji as emoji_util
from app.utils.errors import FieldErrors

DORM_IDS = {d["id"] for d in DORMS}
MAX_ROOMS = 6
# The obfuscated circle. The browser picks the radius and moves the center off the real spot;
# the server only checks the result is plausible and inside the Novosibirsk area.
RADIUS_MIN_M, RADIUS_MAX_M = 300, 500
LAT_RANGE, LON_RANGE = (54.5, 55.4), (82.3, 83.9)
_ROOM_LABEL = re.compile(r"^[0-9a-zа-яё/\-]{1,10}$")


def normalize_room_label(value: str) -> str:
    """ "100 Б" → "100б": one spelling per room, so the duplicate check works."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).lower()


class RoomIn(BaseModel):
    id: Optional[UUID] = None  # set when editing an existing room
    name: str = Field(default="", max_length=40)
    gender: Literal["m", "f", "any"]
    capacity: int = Field(..., ge=1, le=6)
    free_places: int = Field(..., ge=0, le=6)
    rent_rub: Optional[int] = Field(default=None, ge=0, le=300_000)
    emoji: str = Field(..., max_length=60)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return " ".join(v.split())

    @model_validator(mode="after")
    def check(self) -> "RoomIn":
        errors = {}
        if self.free_places > self.capacity:
            errors["free_places"] = "MORE_THAN_CAPACITY"
        if emoji_util.normalize(self.emoji) is None:
            errors["emoji"] = "INVALID_EMOJI"
        if errors:
            raise FieldErrors(errors)
        return self


class HomeIn(BaseModel):
    kind: Literal["dorm", "apartment"]
    description: str = Field(default="", max_length=1000)
    rooms: list[RoomIn] = Field(..., min_length=1, max_length=MAX_ROOMS)

    # Dorm. room_label may be left out when editing: the stored one is kept.
    building: Optional[str] = Field(default=None, max_length=20)
    room_label: Optional[str] = Field(default=None, max_length=20)

    # Apartment
    district: Optional[str] = Field(default=None, max_length=60)
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: Optional[int] = None
    utilities_mode: Optional[Literal["included", "split"]] = None
    utilities_rub: Optional[int] = Field(default=None, ge=0, le=50_000)
    internet_mode: Optional[Literal["included", "split", "none"]] = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def check(self) -> "HomeIn":
        errors: dict[str, str] = {}
        if self.kind == "dorm":
            if self.building not in DORM_IDS:
                errors["building"] = "UNKNOWN_DORM" if self.building else "REQUIRED"
            if self.room_label is not None:
                self.room_label = normalize_room_label(self.room_label)
                if not _ROOM_LABEL.match(self.room_label):
                    errors["room_label"] = "INVALID_ROOM"
            if len(self.rooms) != 1:
                errors["rooms"] = "DORM_HAS_ONE_ROOM"
            for i, room in enumerate(self.rooms):
                if room.gender == "any":
                    errors[f"rooms.{i}.gender"] = "DORM_ROOM_NEEDS_GENDER"
                room.rent_rub, room.name = None, ""
            self.district = self.lat = self.lon = self.radius_m = None
            self.utilities_mode = self.utilities_rub = self.internet_mode = None
        else:
            self.district = " ".join((self.district or "").split())
            if not self.district:
                errors["district"] = "REQUIRED"
            if self.lat is None or self.lon is None or self.radius_m is None:
                errors["location"] = "REQUIRED"
            elif not (LAT_RANGE[0] <= self.lat <= LAT_RANGE[1] and LON_RANGE[0] <= self.lon <= LON_RANGE[1]):
                errors["location"] = "OUTSIDE_AREA"
            elif not RADIUS_MIN_M <= self.radius_m <= RADIUS_MAX_M:
                errors["location"] = "BAD_RADIUS"
            else:
                # ~1 m is plenty for a circle that is deliberately hundreds of meters off.
                self.lat, self.lon = round(self.lat, 5), round(self.lon, 5)
            if self.utilities_mode is None:
                errors["utilities_mode"] = "REQUIRED"
            elif self.utilities_mode == "split" and self.utilities_rub is None:
                errors["utilities_rub"] = "REQUIRED"
            elif self.utilities_mode == "included":
                self.utilities_rub = None
            if self.internet_mode is None:
                errors["internet_mode"] = "REQUIRED"
            for i, room in enumerate(self.rooms):
                if room.rent_rub is None:
                    errors[f"rooms.{i}.rent_rub"] = "REQUIRED"
            self.building = self.room_label = None
        keys = [emoji_util.normalize(r.emoji)[1] for r in self.rooms]
        for i, key in enumerate(keys):
            if key in keys[:i]:
                errors[f"rooms.{i}.emoji"] = "EMOJI_TAKEN"
        if errors:
            raise FieldErrors(errors)
        return self


class RoomOut(BaseModel):
    id: UUID
    name: str
    gender: str
    capacity: int
    free_places: int
    rent_rub: Optional[int] = None
    emoji: str
    residents: int  # hosts on the site who live in this room


class PhotoOut(BaseModel):
    id: UUID
    url: str
    width: int
    height: int


class Permissions(BaseModel):
    can_edit: bool
    can_photos: bool
    can_invites: bool
    can_residents: bool


class Resident(BaseModel):
    """A host, as the other hosts of the same home see them."""

    user_id: UUID
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    room_id: Optional[UUID] = None
    is_you: bool
    permissions: Permissions


class ResidentUpdate(BaseModel):
    """Only the fields that were sent change. Rights need can_residents; anyone may set
    their own room."""

    room_id: Optional[UUID] = None
    can_edit: Optional[bool] = None
    can_photos: Optional[bool] = None
    can_invites: Optional[bool] = None
    can_residents: Optional[bool] = None


class InviteIn(BaseModel):
    room_id: Optional[UUID] = None


class InviteOut(BaseModel):
    id: UUID
    room_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    uses: int
    # Only in the response that creates the invite: the code is not stored and can't be shown again.
    code: Optional[str] = None
    url: Optional[str] = None


class InviteCode(BaseModel):
    code: str = Field(..., min_length=4, max_length=300)


class InvitePreview(BaseModel):
    """What someone holding an invite sees before joining: enough to recognize the place."""

    kind: str
    building: Optional[str] = None
    district: Optional[str] = None
    emoji: str
    room_name: str
    hosts: list[str]


class HomeOut(BaseModel):
    """A home as its hosts see it. Note what is absent: room_label is never sent to anyone."""

    id: UUID
    kind: str
    description: str
    building: Optional[str] = None
    district: Optional[str] = None
    # Dorm: the building's exact point, radius 0 (None until the building list has coordinates).
    # Apartment: the obfuscated circle.
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: Optional[int] = None
    utilities_mode: Optional[str] = None
    utilities_rub: Optional[int] = None
    internet_mode: Optional[str] = None
    rooms: list[RoomOut]
    photos: list[PhotoOut]
    residents: list[Resident]
    permissions: Permissions
    # What still keeps seekers from seeing this home.
    needs_contact: bool      # no host has a phone, Telegram or VK yet
    needs_free_place: bool   # every room is full
    visible: bool


class EmojiRoll(BaseModel):
    count: int = Field(default=1, ge=1, le=MAX_ROOMS)


class PhotoOrder(BaseModel):
    photo_ids: list[UUID] = Field(..., max_length=20)
