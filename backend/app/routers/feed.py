from __future__ import annotations
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.feed import Feed, RoomContacts, RoomPage
from app.services import feed_service
from app.utils.deps import check_origin_no_body, require_user

router = APIRouter(prefix="/api", tags=["feed"])


@router.get("/feed", response_model=Feed)
async def api_feed(kind: Literal["dorm", "apartment"], user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function")):
    """Rooms this person could move into, best match first, and every other visible listing
    (full, another gender, a dorm outside their faculty) in a separate list."""
    return await feed_service.get_feed(db, user, kind)


@router.get("/rooms/{room_id}", response_model=RoomPage)
async def api_room(room_id: UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function")):
    return await feed_service.get_room(db, user, room_id)


@router.post("/rooms/{room_id}/contacts", response_model=RoomContacts)
async def api_room_contacts(room_id: UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function"),
                            _o: None = Depends(check_origin_no_body)):
    return await feed_service.get_contacts(db, user, room_id)
