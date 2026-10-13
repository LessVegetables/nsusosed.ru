"""Ограничение частоты запросов к входу по коду.

Счётчики хранятся в Postgres (таблица auth_events), а не в памяти процесса:
uvicorn работает с несколькими воркерами, и память у них не общая.
"""

from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.auth_event import AuthEvent
from app.utils.errors import rate_limited

HOUR = 3600


def client_ip(request: Request) -> Optional[str]:
    # За прокси uvicorn подставляет адрес из X-Forwarded-For (--proxy-headers, FORWARDED_ALLOW_IPS).
    return request.client.host if request.client else None


def _retry_after(oldest: datetime, window_seconds: int, now: datetime) -> int:
    return max(1, math.ceil((oldest + timedelta(seconds=window_seconds) - now).total_seconds()))


async def _lock_email(db: AsyncSession, email: str) -> None:
    # Сериализуем проверки по одному email между воркерами до конца транзакции.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auth:{email}"})


async def _times(db: AsyncSession, since: datetime, *, email: str | None = None,
                 kind: str | None = None, ip: str | None = None) -> list[datetime]:
    q = select(AuthEvent.created_at).where(AuthEvent.created_at > since)
    if email is not None:
        q = q.where(AuthEvent.email == email)
    if kind is not None:
        q = q.where(AuthEvent.kind == kind)
    if ip is not None:
        q = q.where(AuthEvent.ip == ip)
    result = await db.execute(q.order_by(AuthEvent.created_at.asc()))
    return [row[0] for row in result.fetchall()]


async def _check_ip(db: AsyncSession, ip: Optional[str], now: datetime) -> None:
    if not ip:
        return
    window = settings.auth_ip_window_seconds
    times = await _times(db, now - timedelta(seconds=window), ip=ip)
    if len(times) >= settings.auth_ip_max_requests:
        raise rate_limited(_retry_after(times[0], window, now))


async def check_request_code(db: AsyncSession, email: str, ip: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    await _lock_email(db, email)
    await _check_ip(db, ip, now)

    times = await _times(db, now - timedelta(seconds=HOUR), email=email, kind="code_request")
    cooldown = settings.otp_resend_cooldown_seconds
    if times and (now - times[-1]).total_seconds() < cooldown:
        raise rate_limited(_retry_after(times[-1], cooldown, now))
    if len(times) >= settings.otp_max_requests_per_hour:
        raise rate_limited(_retry_after(times[0], HOUR, now))


async def check_verify(db: AsyncSession, email: str, ip: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    await _lock_email(db, email)
    await _check_ip(db, ip, now)

    fails = await _times(db, now - timedelta(seconds=HOUR), email=email, kind="verify_fail")
    if len(fails) >= settings.otp_max_failed_verifies_per_hour:
        raise rate_limited(_retry_after(fails[0], HOUR, now))


async def record(db: AsyncSession, kind: str, email: str, ip: Optional[str]) -> None:
    db.add(AuthEvent(kind=kind, email=email, ip=ip, created_at=datetime.now(timezone.utc)))
    await db.flush()
