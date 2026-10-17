"""Жильцы жилья: вступление по приглашению, выход, админы.

У жилья нет единственного владельца. Оно существует, пока в нём есть хотя бы
один жилец, и в нём всегда есть хотя бы один админ:
- ушёл последний админ — админом становится самый давний жилец (сначала из тех,
  кто заполнил анкету);
- ушёл последний жилец — жильё удаляется.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.models.listing import Listing
from app.models.membership import Membership
from app.models.profile import Profile
from app.schemas.membership import JoinResponse
from app.utils.security import sha256_hex
from app.utils.errors import (profile_required, invite_invalid, invite_expired, already_in_room, room_full,
                              not_found, not_admin, not_member, last_admin, target_profile_required)


async def lock_listing(db, listing_id: uuid.UUID) -> None:
    await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing_id})


async def get_membership(db, user_id: uuid.UUID) -> Membership | None:
    result = await db.execute(select(Membership).where(Membership.user_id == user_id))
    return result.scalar_one_or_none()


async def get_listing_as_admin(db, user, listing_id: uuid.UUID) -> Listing:
    """Жильё, которым user вправе управлять, уже заблокированное FOR UPDATE."""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise not_found("Жильё не найдено.")
    membership = await get_membership(db, user.id)
    if membership is None or membership.listing_id != listing.id or not membership.is_admin:
        raise not_admin()
    await lock_listing(db, listing.id)
    return listing


async def _members(db, listing_id: uuid.UUID) -> list[Membership]:
    result = await db.execute(
        select(Membership).where(Membership.listing_id == listing_id).order_by(Membership.joined_at, Membership.user_id))
    return list(result.scalars().all())


async def remove_member(db, membership: Membership) -> None:
    """Убрать жильца (сам ушёл, его удалили, он удалил аккаунт) и сохранить правила выше."""
    from app.services.photo_service import delete_listing_files

    listing_id = membership.listing_id
    await lock_listing(db, listing_id)
    await db.delete(membership)
    await db.flush()

    remaining = await _members(db, listing_id)
    listing = (await db.execute(select(Listing).where(Listing.id == listing_id))).scalar_one()
    if not remaining:
        await db.delete(listing)
        await db.flush()
        delete_listing_files(listing_id)
        return

    if not any(m.is_admin for m in remaining):
        prof = await db.execute(select(Profile.user_id).where(Profile.user_id.in_([m.user_id for m in remaining])))
        with_profile = {row[0] for row in prof.fetchall()}
        heir = next((m for m in remaining if m.user_id in with_profile), remaining[0])
        heir.is_admin = True
    listing.version += 1
    await db.flush()


async def join_by_invite(db, user, invite_token: str) -> JoinResponse:
    prof = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = prof.scalar_one_or_none()
    if profile is None:
        raise profile_required()

    token_hash = sha256_hex(invite_token)
    result = await db.execute(select(Listing).where(Listing.invite_token_hash == token_hash))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise invite_invalid()

    now = datetime.now(timezone.utc)
    if listing.invite_expires_at is None or listing.invite_expires_at < now:
        raise invite_expired()

    await lock_listing(db, listing.id)

    current = await get_membership(db, user.id)
    if current is not None:
        if current.listing_id == listing.id:
            return JoinResponse(listing_id=listing.id, version=listing.version)
        raise already_in_room()

    if len(await _members(db, listing.id)) >= listing.occupied_count:
        raise room_full()

    db.add(Membership(listing_id=listing.id, user_id=user.id, joined_at=now, is_admin=False))
    # Кто живёт в жилье, тот уже не ищет его.
    profile.situation = "host"
    profile.budget_max_rub = None
    listing.version += 1
    await db.flush()
    return JoinResponse(listing_id=listing.id, version=listing.version)


async def leave_membership(db, user) -> None:
    membership = await get_membership(db, user.id)
    if membership is not None:
        await remove_member(db, membership)


async def _target_membership(db, listing: Listing, user_id: uuid.UUID) -> Membership:
    result = await db.execute(
        select(Membership).where(Membership.listing_id == listing.id, Membership.user_id == user_id))
    membership = result.scalar_one_or_none()
    if membership is None:
        raise not_member()
    return membership


async def set_admin(db, user, listing_id: uuid.UUID, target_id: uuid.UUID, is_admin: bool) -> None:
    listing = await get_listing_as_admin(db, user, listing_id)
    target = await _target_membership(db, listing, target_id)
    if target.is_admin == is_admin:
        return
    if is_admin:
        prof = await db.execute(select(Profile.user_id).where(Profile.user_id == target_id))
        if prof.scalar_one_or_none() is None:
            raise target_profile_required()
    elif not any(m.is_admin and m.user_id != target_id for m in await _members(db, listing.id)):
        raise last_admin()
    target.is_admin = is_admin
    listing.version += 1
    await db.flush()


async def remove_resident(db, user, listing_id: uuid.UUID, target_id: uuid.UUID) -> None:
    listing = await get_listing_as_admin(db, user, listing_id)
    target = await _target_membership(db, listing, target_id)
    await remove_member(db, target)
