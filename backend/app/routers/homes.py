from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.home import EmojiRoll, HomeIn, HomeOut, PhotoOrder
from app.services import geo_service, home_service
from app.services.image_service import read_upload
from app.utils.deps import check_origin, check_origin_no_body, check_origin_upload, require_user

router = APIRouter(prefix="/api", tags=["homes"])


@router.get("/homes/mine")
async def api_my_home(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)) -> dict:
    """The home this person lives in, or {"home": null}."""
    return {"home": await home_service.get_mine(db, user)}


@router.post("/homes", response_model=HomeOut, status_code=201)
async def api_create_home(body: HomeIn, user: User = Depends(require_user), db: AsyncSession = Depends(get_db),
                          _o: None = Depends(check_origin)):
    return await home_service.create_home(db, user, body)


@router.put("/homes/{home_id}", response_model=HomeOut)
async def api_update_home(home_id: UUID, body: HomeIn, user: User = Depends(require_user),
                          db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await home_service.update_home(db, user, home_id, body)


@router.delete("/homes/mine/membership", status_code=204)
async def api_leave_home(user: User = Depends(require_user), db: AsyncSession = Depends(get_db),
                         _o: None = Depends(check_origin_no_body)):
    """Leave the home. If nobody is left in it, the home and its photos are deleted."""
    await home_service.leave_home(db, user)
    return Response(status_code=204)


@router.post("/homes/{home_id}/photos", response_model=HomeOut, status_code=201)
async def api_add_photo(home_id: UUID, file: UploadFile, user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin_upload)):
    return await home_service.add_photo(db, user, home_id, await read_upload(file))


@router.delete("/homes/{home_id}/photos/{photo_id}", response_model=HomeOut)
async def api_delete_photo(home_id: UUID, photo_id: UUID, user: User = Depends(require_user),
                           db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin_no_body)):
    return await home_service.delete_photo(db, user, home_id, photo_id)


@router.put("/homes/{home_id}/photos/order", response_model=HomeOut)
async def api_reorder_photos(home_id: UUID, body: PhotoOrder, user: User = Depends(require_user),
                             db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await home_service.reorder_photos(db, user, home_id, body.photo_ids)


@router.post("/emoji/roll")
async def api_roll_emoji(body: EmojiRoll, user: User = Depends(require_user), db: AsyncSession = Depends(get_db),
                         _o: None = Depends(check_origin)) -> dict:
    """Random emoji triples that no listing uses yet."""
    return {"emojis": await home_service.roll_emojis(db, body.count)}


class GeoQuery(BaseModel):
    query: str = Field(..., min_length=3, max_length=120)


@router.post("/geo/search")
async def api_geo_search(body: GeoQuery, user: User = Depends(require_user), _o: None = Depends(check_origin)) -> dict:
    """Find an address on the map. The query is passed on to OpenStreetMap and not kept."""
    return {"results": await geo_service.search(user.id, body.query.strip(), user.language)}
