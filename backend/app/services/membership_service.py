from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.models.listing import Listing
from app.models.membership import Membership
from app.models.profile import Profile
from app.schemas.membership import JoinResponse
from app.utils.security import sha256_hex
from app.utils.errors import not_found, forbidden, membership_conflict, profile_required


async def join_by_invite(db, user, invite_token: str) -> JoinResponse:
    prof = await db.execute(select(Profile).where(Profile.user_id == user.id))
    if prof.scalar_one_or_none() is None:
        raise profile_required()

    token_hash = sha256_hex(invite_token)
    result = await db.execute(select(Listing).where(Listing.invite_token_hash == token_hash))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise not_found("Приглашение не найдено или недействительно.")

    now = datetime.now(timezone.utc)
    if listing.invite_expires_at is None or listing.invite_expires_at < now:
        raise not_found("Приглашение истекло.")

    await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing.id})

    existing_member = await db.execute(
        select(Membership).where(Membership.listing_id == listing.id, Membership.user_id == user.id)
    )
    if existing_member.scalar_one_or_none() is not None:
        return JoinResponse(listing_id=listing.id, version=listing.version)

    other = await db.execute(select(Membership).where(Membership.user_id == user.id))
    if other.scalar_one_or_none() is not None:
        raise membership_conflict("Вы уже участвуете в другой комнате.")

    if listing.owner_id == user.id:
        raise membership_conflict("Вы уже являетесь автором этой карточки.")

    mem_count_result = await db.execute(select(Membership.user_id).where(Membership.listing_id == listing.id))
    if len(mem_count_result.fetchall()) >= listing.occupied_count:
        raise membership_conflict("Достигнуто максимальное число привязанных жильцов.")

    db.add(Membership(listing_id=listing.id, user_id=user.id, joined_at=now))
    listing.version += 1
    await db.flush()
    return JoinResponse(listing_id=listing.id, version=listing.version)


async def leave_membership(db, user) -> None:
    result = await db.execute(select(Membership).where(Membership.user_id == user.id))
    membership = result.scalar_one_or_none()
    if membership is None:
        return

    listing_r = await db.execute(select(Listing).where(Listing.id == membership.listing_id))
    listing = listing_r.scalar_one_or_none()
    if listing is not None and listing.owner_id == user.id:
        raise forbidden("Автор не может выйти из своей комнаты. Удалите карточку.")

    if listing is not None:
        await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": listing.id})

    await db.delete(membership)
    if listing is not None:
        listing.version += 1
    await db.flush()
