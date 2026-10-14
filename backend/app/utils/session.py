from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request, Response
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.session import Session
from app.utils.security import generate_token, sha256_hex


async def create_session(db: AsyncSession, user_id, request: Request) -> str:
    token = generate_token()
    token_hash = sha256_hex(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    db.add(Session(user_id=user_id, token_hash=token_hash, created_at=now, expires_at=expires_at))

    result = await db.execute(select(func.count()).select_from(Session).where(Session.user_id == user_id))
    count = result.scalar() or 0
    if count >= settings.max_sessions_per_user:
        oldest = await db.execute(
            select(Session.id).where(Session.user_id == user_id)
            .order_by(Session.created_at.asc())
            .limit(count - settings.max_sessions_per_user + 1)
        )
        ids_to_delete = [row[0] for row in oldest.fetchall()]
        if ids_to_delete:
            await db.execute(delete(Session).where(Session.id.in_(ids_to_delete)))

    await db.flush()
    return token


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    result = await db.execute(delete(Session).where(Session.expires_at < datetime.now(timezone.utc)))
    return result.rowcount


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


async def get_current_session(db: AsyncSession, request: Request) -> Optional[Session]:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    token_hash = sha256_hex(token)
    result = await db.execute(select(Session).where(Session.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None:
        return None
    now = datetime.now(timezone.utc)
    if session.expires_at < now:
        await db.delete(session)
        await db.flush()
        return None
    return session
