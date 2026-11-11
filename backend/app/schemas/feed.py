from __future__ import annotations
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.schemas.home import PhotoOut
from app.schemas.user import Contact


class Compatibility(BaseModel):
    """All a browser ever gets about a score: a percent rounded to 5 and five coarse badges
    (match / ok / discuss). Exact numbers could be used to work out hidden answers."""

    percent: int
    badges: dict[str, str]


class FeedItem(BaseModel):
    room_id: UUID
    kind: str
    building: Optional[str] = None   # dorm building id; the room itself is known only by its emojis
    district: Optional[str] = None
    emoji: str
    room_name: str
    gender: str
    capacity: int
    free_places: int
    rent_rub: Optional[int] = None
    cover_url: Optional[str] = None
    residents: int
    # None: nobody living there has answered the questionnaire yet.
    compatibility: Optional[Compatibility] = None
    # Dorm outside the buildings this person's faculty is normally housed in.
    outside_faculty: bool = False


class Feed(BaseModel):
    items: list[FeedItem]
    # How many more rooms the two "show more" switches would add.
    hidden_by_faculty: int
    hidden_by_gender: int


class RoomResident(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    bio: str
    in_this_room: bool
    # Their visible answers only ({question id: option index}); hidden ones never leave the server.
    answers: dict[str, int]
    compatibility: Optional[Compatibility] = None


class OtherRoom(BaseModel):
    room_id: UUID
    emoji: str
    room_name: str
    free_places: int
    rent_rub: Optional[int] = None


class RoomPage(BaseModel):
    room_id: UUID
    home_id: UUID
    kind: str
    building: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: Optional[int] = None   # 0 = an exact point (dorm building); otherwise the approximate area
    description: str
    emoji: str
    room_name: str
    gender: str
    capacity: int
    free_places: int
    rent_rub: Optional[int] = None
    utilities_mode: Optional[str] = None
    utilities_rub: Optional[int] = None
    internet_mode: Optional[str] = None
    photos: list[PhotoOut]
    residents: list[RoomResident]
    other_rooms: list[OtherRoom]
    compatibility: Optional[Compatibility] = None
    my_answers: dict[str, int]       # the viewer's own visible answers, for the side-by-side
    is_mine: bool                    # the viewer lives here: no score, no "get contacts"
    can_get_contacts: bool


class HostContacts(BaseModel):
    first_name: str
    contacts: list[Contact]


class RoomContacts(BaseModel):
    hosts: list[HostContacts]
