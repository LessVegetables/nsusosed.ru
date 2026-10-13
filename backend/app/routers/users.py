from __future__ import annotations
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserSelf, UserUpdate, UserDeleteRequest
from app.services.auth_service import get_me, update_me, delete_me
from app.utils.deps import require_user, check_origin
from app.utils.errors import AppError

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=UserSelf)
async def api_get_me(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await get_me(db, user)


@router.put("/me", response_model=UserSelf)
async def api_update_me(body: UserUpdate, user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await update_me(db, user, body)


@router.delete("/me", status_code=204)
async def api_delete_me(body: UserDeleteRequest, response: Response,
                        user: User = Depends(require_user),
                        db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    if not body.is_confirmed():
        raise AppError(422, "VALIDATION_ERROR", "Для подтверждения введите DELETE",
                       {"confirm": "Должно быть DELETE"})
    await delete_me(db, user, response)
    return Response(status_code=204)
