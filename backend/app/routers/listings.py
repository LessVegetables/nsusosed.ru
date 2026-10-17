from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.listing import ListingInput, ListingUpdate, ListingOwner, InviteRequest, InviteResponse, MineListingResponse, ConfirmRequest, PhotoOrder
from app.services.listing_service import get_mine, create_listing, update_listing, delete_listing, generate_invite, confirm_listing, to_home_dto
from app.services.membership_service import set_admin, remove_resident, get_listing_as_admin
from app.services.photo_service import add_photo, delete_photo, reorder_photos, read_upload
from app.utils.deps import require_user, check_origin, check_origin_upload

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("/mine", response_model=MineListingResponse)
async def api_get_mine(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await get_mine(db, user)


@router.post("", response_model=ListingOwner, status_code=201)
async def api_create(body: ListingInput, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await create_listing(db, user, body)


@router.put("/{listing_id}", response_model=ListingOwner)
async def api_update(listing_id: uuid.UUID, body: ListingUpdate, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await update_listing(db, user, listing_id, body)


@router.post("/{listing_id}/confirm", response_model=ListingOwner)
async def api_confirm(listing_id: uuid.UUID, body: ConfirmRequest, user: User = Depends(require_user),
                      db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await confirm_listing(db, user, listing_id, body.expected_version)


@router.delete("/{listing_id}", status_code=204)
async def api_delete(listing_id: uuid.UUID, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await delete_listing(db, user, listing_id)
    return Response(status_code=204)


@router.post("/{listing_id}/invite", response_model=InviteResponse)
async def api_invite(listing_id: uuid.UUID, body: InviteRequest, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await generate_invite(db, user, listing_id, body.expected_version)


@router.post("/{listing_id}/admins/{user_id}", status_code=204)
async def api_make_admin(listing_id: uuid.UUID, user_id: uuid.UUID, user: User = Depends(require_user),
                         db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await set_admin(db, user, listing_id, user_id, True)
    return Response(status_code=204)


@router.delete("/{listing_id}/admins/{user_id}", status_code=204)
async def api_remove_admin(listing_id: uuid.UUID, user_id: uuid.UUID, user: User = Depends(require_user),
                           db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await set_admin(db, user, listing_id, user_id, False)
    return Response(status_code=204)


@router.delete("/{listing_id}/members/{user_id}", status_code=204)
async def api_remove_member(listing_id: uuid.UUID, user_id: uuid.UUID, user: User = Depends(require_user),
                            db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await remove_resident(db, user, listing_id, user_id)
    return Response(status_code=204)


@router.post("/{listing_id}/photos", response_model=ListingOwner, status_code=201)
async def api_add_photo(listing_id: uuid.UUID, file: UploadFile = File(...), user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin_upload)):
    listing = await get_listing_as_admin(db, user, listing_id)
    await add_photo(db, listing, await read_upload(file))
    return await to_home_dto(db, listing.id, user)


@router.delete("/{listing_id}/photos/{photo_id}", response_model=ListingOwner)
async def api_delete_photo(listing_id: uuid.UUID, photo_id: uuid.UUID, user: User = Depends(require_user),
                           db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    listing = await get_listing_as_admin(db, user, listing_id)
    await delete_photo(db, listing, photo_id)
    return await to_home_dto(db, listing.id, user)


@router.put("/{listing_id}/photos/order", response_model=ListingOwner)
async def api_reorder_photos(listing_id: uuid.UUID, body: PhotoOrder, user: User = Depends(require_user),
                             db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    listing = await get_listing_as_admin(db, user, listing_id)
    await reorder_photos(db, listing, body.photo_ids)
    return await to_home_dto(db, listing.id, user)
