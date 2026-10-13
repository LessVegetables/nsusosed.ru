"""Генерация и проверка OTP-кодов."""

from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.otp_code import OtpCode
from app.utils.security import sha256_hex, normalize_email


def generate_code() -> str:
    """Сгенерировать N-значный числовой код."""
    n = settings.otp_code_length
    upper = 10 ** n - 1
    return str(secrets.randbelow(upper + 1)).zfill(n)


async def create_otp(db: AsyncSession, user_id, email: str) -> str:
    """
    Создать новый OTP для пользователя. Инвалидирует все предыдущие коды.
    Возвращает plaintext-код (отправляется пользователю, не хранится).
    """
    email = normalize_email(email)
    now = datetime.now(timezone.utc)

    # Удаляем все предыдущие коды для этого email
    await db.execute(delete(OtpCode).where(OtpCode.email == email))

    code = generate_code()
    code_hash = sha256_hex(code)
    expires_at = now + timedelta(seconds=settings.otp_ttl_seconds)

    otp = OtpCode(
        user_id=user_id,
        email=email,
        code_hash=code_hash,
        attempts=0,
        created_at=now,
        expires_at=expires_at,
        verified=False,
    )
    db.add(otp)
    await db.flush()
    return code


async def verify_otp(db: AsyncSession, email: str, code: str):
    """
    Проверить код. Возвращает объект OtpCode при успехе или None.
    Инкрементирует счётчик попыток; аннулирует код при превышении лимита.
    """
    email = normalize_email(email)
    code_hash = sha256_hex(code)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OtpCode).where(
            and_(
                OtpCode.email == email,
                OtpCode.code_hash == code_hash,
                OtpCode.verified == False,  # noqa: E712
            )
        )
    )
    otp = result.scalar_one_or_none()

    if otp is None:
        # Неверный код — инкрементируем счётчик у последнего активного кода
        last_result = await db.execute(
            select(OtpCode).where(
                and_(OtpCode.email == email, OtpCode.verified == False)  # noqa: E712
            ).order_by(OtpCode.created_at.desc()).limit(1)
        )
        last_otp = last_result.scalar_one_or_none()
        if last_otp:
            last_otp.attempts += 1
            if last_otp.attempts >= settings.otp_max_attempts:
                await db.delete(last_otp)  # Код аннулирован после 5 попыток
            await db.flush()
        return None

    # Истёк ли срок?
    if otp.expires_at < now:
        await db.delete(otp)
        await db.flush()
        return None

    # Успех
    otp.verified = True
    otp.attempts += 1
    await db.flush()
    return otp


async def cleanup_expired(db: AsyncSession) -> int:
    """Удалить просроченные коды."""
    now = datetime.now(timezone.utc)
    result = await db.execute(delete(OtpCode).where(OtpCode.expires_at < now))
    return result.rowcount
