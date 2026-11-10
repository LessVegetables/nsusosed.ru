"""Homes: what a host creates and edits. The seeker's side (feed, room page) is separate."""

from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import DORMS
from app.models.home import Home, HomePhoto, Membership, Room
from app.models.user import User
from app.schemas.home import HomeIn, HomeOut, Permissions, PhotoOut, RoomIn, RoomOut
from app.services import image_service
from app.utils import emoji as emoji_util
from app.utils.contact import PRIMARY_TYPES
from app.utils.errors import (already_in_home, emoji_taken, no_permission, not_found, room_occupied, room_taken,
                              too_many_photos, validation_error)

DORM_BY_ID = {d["id"]: d for d in DORMS}
ALL_PERMISSIONS = dict(can_edit=True, can_photos=True, can_invites=True, can_residents=True)


async def get_membership(db, user_id) -> Membership | None:
    result = await db.execute(select(Membership).where(Membership.user_id == user_id))
    return result.scalar_one_or_none()


async def _home(db, home_id) -> Home:
    home = (await db.execute(select(Home).where(Home.id == home_id))).scalar_one_or_none()
    if home is None:
        raise not_found("Жильё не найдено.")
    return home


async def _my_home(db, user: User, home_id, permission: str | None = None) -> tuple[Home, Membership]:
    """The home, if this person lives there and (optionally) holds the permission."""
    membership = await get_membership(db, user.id)
    if membership is None or membership.home_id != home_id:
        raise not_found("Жильё не найдено.")
    if permission and not getattr(membership, permission):
        raise no_permission()
    return await _home(db, home_id), membership


def _active_members(home: Home) -> list[Membership]:
    """People who asked to delete their account are already gone as far as anyone can see."""
    return [m for m in home.memberships if m.user.deleted_at is None]


def to_out(home: Home, membership: Membership) -> HomeOut:
    members = _active_members(home)
    dorm = DORM_BY_ID.get(home.building) if home.kind == "dorm" else None
    needs_contact = not any(c.type in PRIMARY_TYPES for m in members for c in m.user.contacts)
    needs_free_place = not any(r.free_places > 0 for r in home.rooms)
    return HomeOut(
        id=home.id, kind=home.kind, description=home.description, building=home.building, district=home.district,
        lat=dorm["lat"] if dorm else home.lat, lon=dorm["lon"] if dorm else home.lon,
        radius_m=0 if home.kind == "dorm" else home.radius_m,
        utilities_mode=home.utilities_mode, utilities_rub=home.utilities_rub, internet_mode=home.internet_mode,
        rooms=[RoomOut(id=r.id, name=r.name, gender=r.gender, capacity=r.capacity, free_places=r.free_places,
                       rent_rub=r.rent_rub, emoji=r.emoji,
                       residents=sum(1 for m in members if m.room_id == r.id)) for r in home.rooms],
        photos=[PhotoOut(id=p.id, url=image_service.home_photo_url(home.id, p.file_name), width=p.width, height=p.height)
                for p in home.photos],
        permissions=Permissions(can_edit=membership.can_edit, can_photos=membership.can_photos,
                                can_invites=membership.can_invites, can_residents=membership.can_residents),
        needs_contact=needs_contact, needs_free_place=needs_free_place,
        visible=not needs_contact and not needs_free_place,
    )


async def get_mine(db, user: User) -> HomeOut | None:
    membership = await get_membership(db, user.id)
    if membership is None:
        return None
    return to_out(await _home(db, membership.home_id), membership)


# ── Emojis ──────────────────────────────────────────────

async def _emoji_free(db, key: str, except_home_id=None) -> bool:
    """Is this triple unused by any other home's rooms? (Within one home the request itself
    is checked for repeats, so a room may take over the emojis of one removed in the same edit.)"""
    q = select(Room.id).where(Room.emoji_key == key)
    if except_home_id is not None:
        q = q.where(Room.home_id != except_home_id)
    return (await db.execute(q)).first() is None


async def roll_emojis(db, count: int) -> list[str]:
    """Fresh emoji triples nobody uses (and that differ from each other)."""
    out: list[str] = []
    keys: set[str] = set()
    for _ in range(200):
        candidate = emoji_util.roll()
        _, key = emoji_util.normalize(candidate)
        if key not in keys and await _emoji_free(db, key):
            out.append(candidate)
            keys.add(key)
            if len(out) == count:
                break
    return out


def _apply_room(room: Room, data: RoomIn, position: int) -> None:
    room.position, room.name, room.gender = position, data.name, data.gender
    room.capacity, room.free_places, room.rent_rub = data.capacity, data.free_places, data.rent_rub
    room.emoji, room.emoji_key = emoji_util.normalize(data.emoji)


def _apply_home(home: Home, body: HomeIn) -> None:
    home.description = body.description
    home.building = body.building
    if body.room_label is not None:
        home.room_label = body.room_label
    home.district, home.lat, home.lon, home.radius_m = body.district, body.lat, body.lon, body.radius_m
    home.utilities_mode, home.utilities_rub, home.internet_mode = body.utilities_mode, body.utilities_rub, body.internet_mode


async def _check_dorm_room_free(db, building: str, room_label: str, except_home_id=None) -> None:
    q = select(Home).where(Home.kind == "dorm", Home.building == building, Home.room_label == room_label)
    if except_home_id is not None:
        q = q.where(Home.id != except_home_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise room_taken(existing.rooms[0].id)


async def _check_emojis_free(db, rooms: list[RoomIn], except_home_id=None) -> None:
    for i, room in enumerate(rooms):
        if not await _emoji_free(db, emoji_util.normalize(room.emoji)[1], except_home_id):
            raise emoji_taken(i)


# ── Create, edit, delete ────────────────────────────────

async def create_home(db, user: User, body: HomeIn) -> HomeOut:
    if await get_membership(db, user.id) is not None:
        raise already_in_home()
    if body.kind == "dorm":
        if body.room_label is None:
            raise validation_error("Укажите комнату.", {"room_label": "REQUIRED"})
        await _check_dorm_room_free(db, body.building, body.room_label)
    await _check_emojis_free(db, body.rooms)

    # Collections are set here so that nothing has to be lazily loaded later (async sessions can't).
    home = Home(id=uuid.uuid4(), kind=body.kind, rooms=[], photos=[], memberships=[])
    _apply_home(home, body)
    for position, data in enumerate(body.rooms):
        room = Room(id=uuid.uuid4())
        _apply_room(room, data, position)
        home.rooms.append(room)
    db.add(home)
    await db.flush()  # rooms first: the membership points at one
    # Whoever lists the home lives in it and may do everything.
    membership = Membership(user_id=user.id, room_id=home.rooms[0].id, **ALL_PERMISSIONS)
    membership.user = user
    home.memberships.append(membership)
    await db.flush()
    return to_out(home, membership)


async def update_home(db, user: User, home_id, body: HomeIn) -> HomeOut:
    home, membership = await _my_home(db, user, home_id, "can_edit")
    if body.kind != home.kind:
        raise validation_error("Тип жилья изменить нельзя.", {"kind": "IMMUTABLE"})
    if body.kind == "dorm":
        await _check_dorm_room_free(db, body.building, body.room_label or home.room_label, except_home_id=home.id)
    existing = {r.id: r for r in home.rooms}
    for i, data in enumerate(body.rooms):
        if data.id is not None and data.id not in existing:
            raise validation_error("Комната не найдена.", {f"rooms.{i}.id": "UNKNOWN_ROOM"})
    await _check_emojis_free(db, body.rooms, except_home_id=home.id)

    kept = {data.id for data in body.rooms if data.id is not None}
    occupied = {m.room_id for m in home.memberships}
    for i, room in enumerate(list(home.rooms)):
        if room.id not in kept:
            if room.id in occupied:
                raise room_occupied(i)
            home.rooms.remove(room)
    await db.flush()  # removed rooms release their emojis before new ones claim them

    _apply_home(home, body)
    for position, data in enumerate(body.rooms):
        room = existing.get(data.id)
        if room is None:
            room = Room(id=uuid.uuid4())
            home.rooms.append(room)
        _apply_room(room, data, position)
    home.rooms.sort(key=lambda r: r.position)
    await db.flush()
    return to_out(home, membership)


async def remove_member(db, membership: Membership) -> None:
    """Someone leaves. The last one out takes the home and its photos with them."""
    home = await _home(db, membership.home_id)
    home.memberships.remove(membership)
    await db.flush()
    if not home.memberships:
        image_service.remove_home_files(db, home.id)
        await db.delete(home)
        await db.flush()


async def leave_home(db, user: User) -> None:
    membership = await get_membership(db, user.id)
    if membership is None:
        raise not_found("Вы не живёте ни в одном жилье на сайте.")
    await remove_member(db, membership)


# ── Photos ──────────────────────────────────────────────

async def add_photo(db, user: User, home_id, data: bytes) -> HomeOut:
    home, membership = await _my_home(db, user, home_id, "can_photos")
    if len(home.photos) >= image_service.MAX_HOME_PHOTOS:
        raise too_many_photos()
    jpeg, width, height = await image_service.encode_home_photo(data)
    file_name = image_service.store(db, image_service.home_dir(home.id), jpeg)
    home.photos.append(HomePhoto(id=uuid.uuid4(), position=len(home.photos), file_name=file_name, width=width, height=height))
    await db.flush()
    return to_out(home, membership)


async def delete_photo(db, user: User, home_id, photo_id) -> HomeOut:
    home, membership = await _my_home(db, user, home_id, "can_photos")
    photo = next((p for p in home.photos if p.id == photo_id), None)
    if photo is None:
        raise not_found("Фото не найдено.")
    home.photos.remove(photo)
    for position, p in enumerate(home.photos):
        p.position = position
    await db.flush()
    image_service.remove_after_commit(db, image_service.home_dir(home.id) / photo.file_name)
    return to_out(home, membership)


async def reorder_photos(db, user: User, home_id, photo_ids: list) -> HomeOut:
    home, membership = await _my_home(db, user, home_id, "can_photos")
    photos = {p.id: p for p in home.photos}
    if len(photo_ids) != len(photos) or set(photo_ids) != set(photos):
        raise validation_error("Порядок должен перечислять все фото жилья.", {"photo_ids": "INVALID_SET"})
    for position, photo_id in enumerate(photo_ids):
        photos[photo_id].position = position
    home.photos.sort(key=lambda p: p.position)
    await db.flush()
    return to_out(home, membership)
