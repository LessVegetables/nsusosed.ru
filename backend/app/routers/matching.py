from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.matching import MatchListResponse, ContactResponse, ListingDetail
from app.services.matching_service import get_matches, get_listing_detail, get_contact
from app.utils.deps import require_user

router = APIRouter(prefix="/api", tags=["matching"])


@router.get("/matches", response_model=MatchListResponse)
async def api_matches(kind: str = Query(..., pattern="^(dorm|apartment)$"),
                      offset: int = Query(0, ge=0),
                      limit: int = Query(20, ge=1, le=50),
                      user: User = Depends(require_user),
                      db: AsyncSession = Depends(get_db)):
    return await get_matches(db, user, kind, offset, limit)


@router.get("/listings/{listing_id}", response_model=ListingDetail)
async def api_detail(listing_id: uuid.UUID, user: User = Depends(require_user),
                     db: AsyncSession = Depends(get_db)):
    return await get_listing_detail(db, user, listing_id)


@router.get("/listings/{listing_id}/contact", response_model=ContactResponse)
async def api_contact(listing_id: uuid.UUID, user: User = Depends(require_user),
                      db: AsyncSession = Depends(get_db)):
    return await get_contact(db, user, listing_id)
