from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.listing import ListingInput, ListingUpdate, ListingOwner, InviteRequest, InviteResponse, MineListingResponse
from app.services.listing_service import get_mine, create_listing, update_listing, delete_listing, generate_invite
from app.utils.deps import require_user, check_origin

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


@router.delete("/{listing_id}", status_code=204)
async def api_delete(listing_id: uuid.UUID, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await delete_listing(db, user, listing_id)
    return Response(status_code=204)


@router.post("/{listing_id}/invite", response_model=InviteResponse)
async def api_invite(listing_id: uuid.UUID, body: InviteRequest, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await generate_invite(db, user, listing_id, body.expected_version)
