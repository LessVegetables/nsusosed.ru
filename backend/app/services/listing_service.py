from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from app.config import settings
from app.models.listing import Listing
from app.models.membership import Membership
from app.models.profile import Profile
from app.models.user import User
from app.schemas.listing import ListingInput, ListingUpdate, ListingOwner, ResidentBrief, InviteResponse, MineListingResponse
from app.utils.security import generate_token, sha256_hex, normalize_building
from app.utils.errors import AppError, not_found, forbidden, version_conflict, listing_exists, occupancy_conflict, profile_required


def _free_places(l: Listing) -> int:
    return l.capacity - l.occupied_count


async def _answered_count(db, listing_id: uuid.UUID) -> int:
    result = await db.execute(select(Membership.user_id).where(Membership.listing_id == listing_id))
    member_ids = [row[0] for row in result.fetchall()]
    if not member_ids:
        return 0
    prof = await db.execute(select(Profile.user_id).where(Profile.user_id.in_(member_ids)))
    return len(prof.fetchall())


async def _residents_brief(db, listing_id: uuid.UUID) -> list[ResidentBrief]:
    result = await db.execute(select(Membership.user_id).where(Membership.listing_id == listing_id))
    member_ids = [row[0] for row in result.fetchall()]
    if not member_ids:
        return []
    users_r = await db.execute(select(User).where(User.id.in_(member_ids)))
    users = {u.id: u for u in users_r.scalars().all()}
    prof_r = await db.execute(select(Profile.user_id).where(Profile.user_id.in_(member_ids)))
    profile_ids = {row[0] for row in prof_r.fetchall()}
    return [
        ResidentBrief(display_name=users[uid].display_name, profile_complete=uid in profile_ids)
        for uid in member_ids if uid in users
    ]


async def _to_owner_dto(db, l: Listing) -> ListingOwner:
    answered = await _answered_count(db, l.id)
    residents = await _residents_brief(db, l.id)
    return ListingOwner(
        id=l.id, owner_id=l.owner_id, kind=l.kind,
        building=l.building, room_number=l.room_number, floor=l.floor,
        capacity=l.capacity, occupied_count=l.occupied_count,
        free_places=_free_places(l), answered_count=answered,
        is_corner=l.is_corner, windows_count=l.windows_count,
        view=l.view, layout=l.layout,
        district=l.district, monthly_cost_per_person_rub=l.monthly_cost_per_person_rub,
        description=l.description, contact_username=l.contact_username,
        status=l.status, version=l.version,
        residents=residents, confirmed_at=l.confirmed_at, created_at=l.created_at,
    )


async def get_mine(db, user: User) -> MineListingResponse:
    result = await db.execute(select(Listing).where(Listing.owner_id == user.id))
    listing = result.scalar_one_or_none()
    if listing is None:
        return MineListingResponse(item=None)
    dto = await _to_owner_dto(db, listing)
    return MineListingResponse(item=dto)


async def create_listing(db, user: User, body: ListingInput) -> ListingOwner:
    prof = await db.execute(select(Profile).where(Profile.user_id == user.id))
    if prof.scalar_one_or_none() is None:
        raise profile_required()
    existing = await db.execute(select(Listing).where(Listing.owner_id == user.id))
    if existing.scalar_one_or_none() is not None:
        raise listing_exists("У вас уже есть карточка.")
    mem = await db.execute(select(Membership).where(Membership.user_id == user.id))
    if mem.scalar_one_or_none() is not None:
        raise AppError(409, "MEMBERSHIP_CONFLICT", "Вы уже участвуете в другой комнате.")

    building = None
    room_number = body.room_number
    if body.kind == "dorm" and body.building:
        building = normalize_building(body.building)
        dup = await db.execute(select(Listing).where(Listing.building == building, Listing.room_number == room_number))
        if dup.scalar_one_or_none() is not None:
            raise listing_exists(f"Карточка для {building}, комн. {room_number} уже существует.")

    now = datetime.now(timezone.utc)
    listing = Listing(
        owner_id=user.id, kind=body.kind,
        capacity=body.capacity, occupied_count=body.occupied_count,
        contact_username=body.contact_username, description=body.description,
        status="active", version=1, confirmed_at=now,
        building=building, room_number=room_number, floor=body.floor,
        is_corner=body.is_corner, windows_count=body.windows_count,
        view=body.view, layout=body.layout,
        district=body.district, monthly_cost_per_person_rub=body.monthly_cost_per_person_rub,
    )
    db.add(listing)
    await db.flush()
    db.add(Membership(listing_id=listing.id, user_id=user.id, joined_at=now))
    await db.flush()
    return await _to_owner_dto(db, listing)


async def update_listing(db, user: User, listing_id: uuid.UUID, body: ListingUpdate) -> ListingOwner:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise not_found("Карточка не найдена.")
    if listing.owner_id != user.id:
        raise forbidden("Только автор может изменить карточку.")

    await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing.id})

    if body.expected_version != listing.version:
        raise version_conflict()

    mem_count_result = await db.execute(select(Membership.listing_id).where(Membership.listing_id == listing.id))
    mem_count = len(mem_count_result.fetchall())
    if body.occupied_count < mem_count:
        raise occupancy_conflict()

    listing.capacity = body.capacity
    listing.occupied_count = body.occupied_count
    listing.contact_username = body.contact_username
    listing.description = body.description

    if listing.kind == "dorm":
        if body.building:
            listing.building = normalize_building(body.building)
        if body.room_number is not None:
            listing.room_number = body.room_number
        if body.floor is not None:
            listing.floor = body.floor
        listing.is_corner = body.is_corner
        listing.windows_count = body.windows_count
        listing.view = body.view
        listing.layout = body.layout
    else:
        if body.district is not None:
            listing.district = body.district
        if body.monthly_cost_per_person_rub is not None:
            listing.monthly_cost_per_person_rub = body.monthly_cost_per_person_rub

    free = listing.capacity - listing.occupied_count
    if free == 0:
        listing.status = "paused"
    else:
        listing.status = body.status or "active"

    if listing.status == "active":
        listing.confirmed_at = datetime.now(timezone.utc)

    listing.version += 1
    await db.flush()
    return await _to_owner_dto(db, listing)


async def delete_listing(db, user: User, listing_id: uuid.UUID) -> None:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise not_found("Карточка не найдена.")
    if listing.owner_id != user.id:
        raise forbidden("Только автор может удалить карточку.")
    await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing.id})
    await db.delete(listing)
    await db.flush()


async def generate_invite(db, user: User, listing_id: uuid.UUID, expected_version: int) -> InviteResponse:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise not_found("Карточка не найдена.")
    if listing.owner_id != user.id:
        raise forbidden("Только автор может создать приглашение.")

    await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing.id})

    if expected_version != listing.version:
        raise version_conflict()

    token = generate_token()
    token_hash = sha256_hex(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.invite_ttl_days)

    listing.invite_token_hash = token_hash
    listing.invite_expires_at = expires_at
    listing.version += 1
    await db.flush()

    invite_url = f"{settings.public_origin}/join#token={token}"
    return InviteResponse(invite_url=invite_url, expires_at=expires_at, version=listing.version)
