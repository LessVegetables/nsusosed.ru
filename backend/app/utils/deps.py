from __future__ import annotations
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.utils.errors import AppError, auth_required, forbidden
from app.utils.session import get_current_session


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    session = await get_current_session(db, request)
    if session is None:
        raise auth_required()
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise auth_required()
    return user


async def check_origin(request: Request) -> None:
    from app.config import settings
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        content_type = request.headers.get("content-type", "")
        if origin and origin.rstrip("/") != settings.public_origin.rstrip("/"):
            raise forbidden("Неверный Origin.")
        if request.method in ("POST", "PUT", "PATCH"):
            if "application/json" not in content_type:
                raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "Неподдерживаемый формат запроса.")
