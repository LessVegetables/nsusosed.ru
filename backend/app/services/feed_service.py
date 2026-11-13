"""The seeker's side: the feed of rooms with free places and a room's page.

Who sees what:
  - a room appears once its home is reachable (a host with a phone, Telegram or VK) and it
    has a free place;
  - a hard block between the viewer and anyone living there hides the room completely, as if
    it did not exist (a 0% would give a hidden answer away);
  - scores go out only as a rounded percent and coarse badges; residents' hidden answers never.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select
from app import questionnaires
from app.config import DORMS
from app.models.home import Home, Membership, Room
from app.models.questionnaire import QuestionnaireResponse
from app.models.user import User
from app.schemas.feed import (Compatibility, Feed, FeedItem, HostContacts, OtherRoom, RoomContacts, RoomPage,
                              RoomResident)
from app.schemas.home import PhotoOut
from app.schemas.user import Contact
from app.services import image_service
from app.utils.contact import PRIMARY_TYPES, contact_url
from app.utils.errors import AppError, not_found

DORM_BY_ID = {d["id"]: d for d in DORMS}
_BADGE_ORDER = {"match": 0, "ok": 1, "discuss": 2}


def _questionnaire_required() -> AppError:
    return AppError(409, "QUESTIONNAIRE_REQUIRED", "Сначала заполните анкету.")


@dataclass
class _Scored:
    """A room's compatibility for one viewer."""
    blocked: bool = False
    room: Optional[float] = None            # unrounded, for sorting only
    public: Optional[Compatibility] = None
    per_resident: dict = None               # user_id → Compatibility


async def _answers_by_user(db, user_ids) -> dict:
    """Answers usable for scoring: current questionnaire version only."""
    if not user_ids:
        return {}
    rows = await db.execute(select(QuestionnaireResponse).where(
        QuestionnaireResponse.user_id.in_(user_ids), QuestionnaireResponse.version == questionnaires.CURRENT))
    return {r.user_id: r.answers for r in rows.scalars().all()}


def _active(home: Home) -> list[Membership]:
    return [m for m in home.memberships if m.user.deleted_at is None]


def _reachable(home: Home) -> bool:
    return any(c.type in PRIMARY_TYPES for m in _active(home) for c in m.user.contacts)


def _score(viewer_answers: dict, home: Home, answers: dict) -> _Scored:
    """The viewer against everyone living in the home (in an apartment you share the kitchen
    and the bathroom with all of them, not only with your own room)."""
    q = questionnaires.current()
    pairs, per_resident = [], {}
    for m in _active(home):
        raw = answers.get(m.user_id)
        if raw is None or not q.is_complete(raw, m.user.is_adult):
            continue
        pair = q.score_pair(viewer_answers, q.for_scoring(raw, bool(m.user.is_adult)))
        if pair is None:
            return _Scored(blocked=True, per_resident={})
        pairs.append(pair)
        per_resident[m.user_id] = Compatibility(**pair.public())
    if not pairs:
        return _Scored(per_resident={})
    room = q.score_room(pairs)
    # A room's badge per topic is its worst resident's: one clash is enough to matter.
    badges = {name: max((p.badges()[name] for p in pairs), key=_BADGE_ORDER.get) for name in q.DIMENSIONS}
    return _Scored(room=room, public=Compatibility(percent=q.round_score(room), badges=badges), per_resident=per_resident)


async def _viewer_answers(db, user: User) -> dict:
    q = questionnaires.current()
    raw = (await _answers_by_user(db, [user.id])).get(user.id, {})
    if not q.is_complete(raw, user.is_adult):
        raise _questionnaire_required()
    return q.for_scoring(raw, bool(user.is_adult))


def _visible(answers: dict | None) -> dict[str, int]:
    q = questionnaires.current()
    return {k: v for k, v in (answers or {}).items() if k in q.QUESTIONS and not q.QUESTIONS[k]["hidden"]}


async def get_feed(db, user: User, kind: str, whole_campus: bool, any_gender: bool) -> Feed:
    mine = await _viewer_answers(db, user)
    homes = list((await db.execute(select(Home).where(Home.kind == kind))).scalars().all())
    answers = await _answers_by_user(db, [m.user_id for h in homes for m in h.memberships])

    items: list[tuple[float, FeedItem]] = []
    hidden_by_faculty = hidden_by_gender = 0
    for home in homes:
        members = _active(home)
        if any(m.user_id == user.id for m in members) or not _reachable(home):
            continue
        scored = _score(mine, home, answers)
        if scored.blocked:
            continue
        outside = False
        if kind == "dorm":
            faculties = (DORM_BY_ID.get(home.building) or {}).get("faculties", [])
            # A building with no faculty list (or a person with no faculty) is not filtered.
            outside = bool(faculties and user.faculty and user.faculty not in faculties)
        for room in home.rooms:
            if room.free_places <= 0:
                continue
            wrong_gender = room.gender != "any" and user.gender is not None and room.gender != user.gender
            if wrong_gender and not any_gender:
                hidden_by_gender += 0 if (outside and not whole_campus) else 1
                continue
            if outside and not whole_campus:
                hidden_by_faculty += 1
                continue
            item = FeedItem(
                room_id=room.id, kind=home.kind, building=home.building, district=home.district, emoji=room.emoji,
                room_name=room.name, gender=room.gender, capacity=room.capacity, free_places=room.free_places,
                rent_rub=room.rent_rub,
                cover_url=image_service.home_photo_url(home.id, home.photos[0].file_name) if home.photos else None,
                residents=len(members), compatibility=scored.public, outside_faculty=outside)
            items.append((scored.room if scored.room is not None else -1.0, item))
    items.sort(key=lambda pair: -pair[0])
    return Feed(items=[item for _, item in items], hidden_by_faculty=hidden_by_faculty, hidden_by_gender=hidden_by_gender)


async def _room_for(db, user: User, room_id) -> tuple[Home, Room, bool, _Scored, dict, dict]:
    """A room this person may look at, with their compatibility. Rooms that don't exist, are
    not reachable, or are hard-blocked for this viewer all look the same: not found."""
    room = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if room is None:
        raise not_found("Комната не найдена.")
    home = (await db.execute(select(Home).where(Home.id == room.home_id))).scalar_one()
    is_mine = any(m.user_id == user.id for m in _active(home))
    answers = await _answers_by_user(db, [m.user_id for m in home.memberships] + [user.id])
    q = questionnaires.current()
    my_raw = answers.get(user.id, {})
    scored = _Scored(per_resident={})
    if not is_mine:
        if not _reachable(home):
            raise not_found("Комната не найдена.")
        if q.is_complete(my_raw, user.is_adult):
            scored = _score(q.for_scoring(my_raw, bool(user.is_adult)), home, answers)
            if scored.blocked:
                raise not_found("Комната не найдена.")
    return home, room, is_mine, scored, answers, my_raw


async def get_room(db, user: User, room_id) -> RoomPage:
    home, room, is_mine, scored, answers, my_raw = await _room_for(db, user, room_id)
    q = questionnaires.current()
    dorm = DORM_BY_ID.get(home.building) if home.kind == "dorm" else None
    residents = []
    for m in _active(home):
        raw = answers.get(m.user_id)
        complete = raw is not None and q.is_complete(raw, m.user.is_adult)
        residents.append(RoomResident(
            user_id=m.user_id, first_name=m.user.first_name, last_name=m.user.last_name,
            avatar_url=image_service.avatar_url(m.user.avatar_file), bio=m.user.bio, in_this_room=m.room_id == room.id,
            answers=_visible(raw) if complete else {}, compatibility=scored.per_resident.get(m.user_id)))
    residents.sort(key=lambda r: not r.in_this_room)
    return RoomPage(
        room_id=room.id, home_id=home.id, kind=home.kind, building=home.building, district=home.district,
        lat=dorm["lat"] if dorm else home.lat, lon=dorm["lon"] if dorm else home.lon,
        radius_m=0 if home.kind == "dorm" else home.radius_m,
        description=home.description, emoji=room.emoji, room_name=room.name, gender=room.gender,
        capacity=room.capacity, free_places=room.free_places, rent_rub=room.rent_rub,
        utilities_mode=home.utilities_mode, utilities_rub=home.utilities_rub, internet_mode=home.internet_mode,
        photos=[PhotoOut(id=p.id, url=image_service.home_photo_url(home.id, p.file_name), width=p.width, height=p.height)
                for p in home.photos],
        residents=residents,
        other_rooms=[OtherRoom(room_id=r.id, emoji=r.emoji, room_name=r.name, free_places=r.free_places, rent_rub=r.rent_rub)
                     for r in home.rooms if r.id != room.id],
        compatibility=scored.public, my_answers=_visible(my_raw), is_mine=is_mine,
        can_get_contacts=not is_mine and q.is_complete(my_raw, user.is_adult),
    )


async def get_contacts(db, user: User, room_id) -> RoomContacts:
    """The hosts' contact methods. A deliberate, separate request (a POST) so that a bot
    check can be put in front of it later; it needs a completed questionnaire."""
    home, _, is_mine, _, _, my_raw = await _room_for(db, user, room_id)
    if not is_mine and not questionnaires.current().is_complete(my_raw, user.is_adult):
        raise _questionnaire_required()
    return RoomContacts(hosts=[
        HostContacts(first_name=m.user.first_name,
                     contacts=[Contact(type=c.type, value=c.value, url=contact_url(c.type, c.value)) for c in m.user.contacts])
        for m in _active(home) if m.user.contacts])
