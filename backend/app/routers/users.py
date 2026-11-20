from __future__ import annotations
from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.user import ContactsUpdate, UserSelf, UserUpdate, UserDeleteRequest
from app.services.auth_service import get_me, update_me, update_contacts, delete_me
from app.services.image_service import drop_avatar, read_upload, set_avatar
from app.utils.deps import require_user, check_origin, check_origin_no_body, check_origin_upload
from app.utils.errors import AppError

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=UserSelf)
async def api_get_me(user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function")):
    return await get_me(db, user)


@router.put("/me", response_model=UserSelf)
async def api_update_me(body: UserUpdate, user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db, scope="function"), _o: None = Depends(check_origin)):
    return await update_me(db, user, body)


@router.put("/me/contacts", response_model=UserSelf)
async def api_update_contacts(body: ContactsUpdate, user: User = Depends(require_user),
                              db: AsyncSession = Depends(get_db, scope="function"), _o: None = Depends(check_origin)):
    return await update_contacts(db, user, body)


@router.post("/me/avatar", response_model=UserSelf)
async def api_set_avatar(file: UploadFile, user: User = Depends(require_user),
                         db: AsyncSession = Depends(get_db, scope="function"), _o: None = Depends(check_origin_upload)):
    await set_avatar(db, user, await read_upload(file))
    return await get_me(db, user)


@router.delete("/me/avatar", response_model=UserSelf)
async def api_drop_avatar(user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function"),
                          _o: None = Depends(check_origin_no_body)):
    drop_avatar(db, user)
    await db.flush()
    return await get_me(db, user)


@router.delete("/me", status_code=204)
async def api_delete_me(body: UserDeleteRequest,
                        user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db, scope="function"), _o: None = Depends(check_origin)):
    if not body.is_confirmed():
        raise AppError(422, "VALIDATION_ERROR", "Для подтверждения введите DELETE",
                       {"confirm": "MUST_BE_DELETE"})
    # The cookie is cleared on the response that is sent: a new Response would drop it.
    sent = Response(status_code=204)
    await delete_me(db, user, sent)
    return sent
