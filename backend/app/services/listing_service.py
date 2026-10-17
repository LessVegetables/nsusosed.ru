from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import settings
from app.models.listing import Listing, ListingContact
from app.models.membership import Membership
from app.models.profile import Profile
from app.models.user import User
from app.schemas.listing import (listing_field_errors, ListingFields, ListingInput, ListingUpdate, ListingOwner,
                                 HomeResident, ContactOut, PhotoOut, InviteResponse, MineListingResponse)
from app.services.membership_service import get_listing_as_admin, get_membership, remove_member
from app.services.photo_service import photo_url
from app.utils.contact import contact_url
from app.utils.security import generate_token, sha256_hex, normalize_building
from app.utils.errors import version_conflict, room_taken, already_in_room, occupancy_conflict, profile_required, validation_error


def _free_places(l: Listing) -> int:
    return l.capacity - l.occupied_count


async def _load(db, listing_id: uuid.UUID) -> Listing:
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
        .options(selectinload(Listing.contacts), selectinload(Listing.photos))
        .execution_options(populate_existing=True))
    return result.scalar_one()


def contacts_out(l: Listing) -> list[ContactOut]:
    return [ContactOut(type=c.type, value=c.value, url=contact_url(c.type, c.value)) for c in l.contacts]


def photos_out(l: Listing) -> list[PhotoOut]:
    return [PhotoOut(id=p.id, url=photo_url(l.id, p.file_name), width=p.width, height=p.height) for p in l.photos]


async def _residents(db, listing_id: uuid.UUID) -> list[HomeResident]:
    result = await db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.listing_id == listing_id).order_by(Membership.joined_at, Membership.user_id))
    rows = result.all()
    prof_r = await db.execute(select(Profile.user_id).where(Profile.user_id.in_([m.user_id for m, _ in rows])))
    profile_ids = {row[0] for row in prof_r.fetchall()}
    return [
        HomeResident(user_id=m.user_id, display_name=u.display_name, profile_complete=m.user_id in profile_ids,
                     is_admin=m.is_admin, joined_at=m.joined_at)
        for m, u in rows
    ]


async def to_home_dto(db, listing_id: uuid.UUID, user: User) -> ListingOwner:
    l = await _load(db, listing_id)
    residents = await _residents(db, l.id)
    return ListingOwner(
        id=l.id, kind=l.kind,
        building=l.building, room_number=l.room_number, floor=l.floor,
        capacity=l.capacity, occupied_count=l.occupied_count,
        free_places=_free_places(l), answered_count=sum(r.profile_complete for r in residents),
        is_corner=l.is_corner, windows_count=l.windows_count,
        view=l.view, layout=l.layout,
        district=l.district, monthly_cost_per_person_rub=l.monthly_cost_per_person_rub,
        description=l.description, contacts=contacts_out(l), photos=photos_out(l),
        status=l.status, version=l.version,
        residents=residents, you_are_admin=any(r.user_id == user.id and r.is_admin for r in residents),
        confirmed_at=l.confirmed_at,
        expires_at=l.confirmed_at + timedelta(days=settings.listing_ttl_days),
        created_at=l.created_at,
    )


def _set_contacts(listing: Listing, body: ListingFields) -> None:
    listing.contacts = [ListingContact(position=i, type=c.type, value=c.value) for i, c in enumerate(body.contacts)]


async def get_mine(db, user: User) -> MineListingResponse:
    membership = await get_membership(db, user.id)
    if membership is None:
        return MineListingResponse(item=None)
    return MineListingResponse(item=await to_home_dto(db, membership.listing_id, user))


async def create_listing(db, user: User, body: ListingInput) -> ListingOwner:
    prof = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = prof.scalar_one_or_none()
    if profile is None:
        raise profile_required()
    if await get_membership(db, user.id) is not None:
        raise already_in_room()

    building = None
    room_number = body.room_number
    if body.kind == "dorm" and body.building:
        building = normalize_building(body.building)
        dup = await db.execute(select(Listing).where(Listing.building == building, Listing.room_number == room_number))
        if dup.scalar_one_or_none() is not None:
            raise room_taken(building, room_number)

    now = datetime.now(timezone.utc)
    listing = Listing(
        kind=body.kind,
        capacity=body.capacity, occupied_count=body.occupied_count, description=body.description,
        status="active", version=1, confirmed_at=now,
        building=building, room_number=room_number, floor=body.floor,
        is_corner=body.is_corner, windows_count=body.windows_count,
        view=body.view, layout=body.layout,
        district=body.district, monthly_cost_per_person_rub=body.monthly_cost_per_person_rub,
    )
    _set_contacts(listing, body)
    db.add(listing)
    await db.flush()
    db.add(Membership(listing_id=listing.id, user_id=user.id, joined_at=now, is_admin=True))
    profile.situation = "host"
    profile.budget_max_rub = None
    await db.flush()
    return await to_home_dto(db, listing.id, user)


async def update_listing(db, user: User, listing_id: uuid.UUID, body: ListingUpdate) -> ListingOwner:
    listing = await get_listing_as_admin(db, user, listing_id)
    if body.expected_version != listing.version:
        raise version_conflict()

    mem_count_result = await db.execute(select(Membership.user_id).where(Membership.listing_id == listing.id))
    if body.occupied_count < len(mem_count_result.fetchall()):
        raise occupancy_conflict()

    errors = listing_field_errors(listing.kind, body)
    if errors:
        raise validation_error("Проверьте заполненные поля", errors)

    if listing.kind == "dorm":
        building = normalize_building(body.building)
        if (building, body.room_number) != (listing.building, listing.room_number):
            dup = await db.execute(select(Listing.id).where(
                Listing.building == building, Listing.room_number == body.room_number, Listing.id != listing.id))
            if dup.scalar_one_or_none() is not None:
                raise room_taken(building, body.room_number)
        listing.building = building
        listing.room_number = body.room_number
        listing.floor = body.floor
        listing.is_corner = body.is_corner
        listing.windows_count = body.windows_count
        listing.view = body.view
        listing.layout = body.layout
    else:
        listing.district = body.district
        listing.monthly_cost_per_person_rub = body.monthly_cost_per_person_rub

    listing.capacity = body.capacity
    listing.occupied_count = body.occupied_count
    listing.description = body.description
    await db.refresh(listing, ["contacts"])
    _set_contacts(listing, body)

    free = listing.capacity - listing.occupied_count
    if free == 0:
        listing.status = "paused"
    else:
        listing.status = body.status or "active"

    if listing.status == "active":
        listing.confirmed_at = datetime.now(timezone.utc)

    listing.version += 1
    await db.flush()
    return await to_home_dto(db, listing.id, user)


async def confirm_listing(db, user: User, listing_id: uuid.UUID, expected_version: int) -> ListingOwner:
    """Админ подтверждает, что карточка актуальна: продлевает показ ещё на LISTING_TTL_DAYS."""
    listing = await get_listing_as_admin(db, user, listing_id)
    if expected_version != listing.version:
        raise version_conflict()

    listing.confirmed_at = datetime.now(timezone.utc)
    if _free_places(listing) > 0:
        listing.status = "active"
    listing.version += 1
    await db.flush()
    return await to_home_dto(db, listing.id, user)


async def delete_listing(db, user: User, listing_id: uuid.UUID) -> None:
    """Удалить жильё целиком: все жильцы уходят, последний уход удаляет карточку и фото."""
    listing = await get_listing_as_admin(db, user, listing_id)
    result = await db.execute(select(Membership).where(Membership.listing_id == listing.id))
    for membership in result.scalars().all():
        await remove_member(db, membership)


async def generate_invite(db, user: User, listing_id: uuid.UUID, expected_version: int) -> InviteResponse:
    listing = await get_listing_as_admin(db, user, listing_id)
    if expected_version != listing.version:
        raise version_conflict()

    token = generate_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.invite_ttl_days)

    listing.invite_token_hash = sha256_hex(token)
    listing.invite_expires_at = expires_at
    listing.version += 1
    await db.flush()

    invite_url = f"{settings.public_origin}/join#token={token}"
    return InviteResponse(invite_url=invite_url, expires_at=expires_at, version=listing.version)
