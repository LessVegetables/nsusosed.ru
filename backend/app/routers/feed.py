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
async def api_feed(kind: Literal["dorm", "apartment"], whole_campus: bool = False, any_gender: bool = False,
                   user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    """Rooms with free places, best match first. Dorm rooms are limited to the buildings of
    the person's faculty unless whole_campus is set; rooms for another gender are left out
    unless any_gender is set."""
    return await feed_service.get_feed(db, user, kind, whole_campus, any_gender)


@router.get("/rooms/{room_id}", response_model=RoomPage)
async def api_room(room_id: UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await feed_service.get_room(db, user, room_id)


@router.post("/rooms/{room_id}/contacts", response_model=RoomContacts)
async def api_room_contacts(room_id: UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db),
                            _o: None = Depends(check_origin_no_body)):
    return await feed_service.get_contacts(db, user, room_id)
