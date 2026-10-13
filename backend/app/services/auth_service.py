from __future__ import annotations
from datetime import datetime, timezone
from fastapi import Request, Response
from sqlalchemy import select, text
from app.config import settings
from app.models.user import User
from app.models.profile import Profile
from app.models.listing import Listing
from app.schemas.auth import (
    RequestCodeRequest, RequestCodeResponse,
    VerifyCodeRequest, AuthResponse, UserBrief,
)
from app.schemas.user import UserSelf, UserUpdate
from app.utils.security import normalize_email, validate_email_domain
from app.utils.session import create_session, set_session_cookie, clear_session_cookie, get_current_session
from app.utils.errors import AppError, validation_error, invalid_credentials
from app.services.email_service import send_otp_email
from app.services.otp_service import create_otp, verify_otp


async def request_code(db, body: RequestCodeRequest, request: Request) -> RequestCodeResponse:
    """Запросить код подтверждения на email."""
    email = normalize_email(body.email)

    # 1. Проверка домена
    if not validate_email_domain(email, settings.email_domains):
        raise validation_error(
            "Недопустимый домен электронной почты.",
            {"email": f"Требуется домен: {', '.join(settings.email_domains)}"},
        )

    # 2. Найти или создать пользователя (автоматическая регистрация)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            display_name="Пользователь",
            privacy_version=1,
            privacy_accepted_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

    # 3. Сгенерировать OTP
    code = await create_otp(db, user.id, email)

    # 4. Отправить email
    sent = await send_otp_email(email, code)
    if not sent and settings.postbox_api_key:
        raise AppError(503, "EMAIL_SEND_FAILED", "Не удалось отправить код. Попробуйте позже.")

    # Маскируем email для ответа
    local, domain = email.rsplit("@", 1)
    masked = f"{local[0]}***@{domain}" if len(local) > 1 else f"*@{domain}"

    return RequestCodeResponse(
        message="Код отправлен на почту",
        email_masked=masked,
        ttl_seconds=settings.otp_ttl_seconds,
    )


async def verify_code(
    db, body: VerifyCodeRequest, request: Request, response: Response
) -> AuthResponse:
    """Проверить код и создать сессию."""
    email = normalize_email(body.email)

    otp = await verify_otp(db, email, body.code.strip())
    if otp is None:
        raise invalid_credentials()

    # Находим пользователя
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise invalid_credentials()

    # Профиль заполнен?
    prof_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile_complete = prof_result.scalar_one_or_none() is not None

    # Создаём сессию
    token = await create_session(db, user.id, request)
    set_session_cookie(response, token)

    return AuthResponse(
        user=UserBrief(id=user.id, email=user.email, display_name=user.display_name),
        profile_complete=profile_complete,
    )


async def logout(db, request: Request, response: Response) -> None:
    session = await get_current_session(db, request)
    if session is not None:
        await db.delete(session)
        await db.flush()
    clear_session_cookie(response)


async def get_me(db, user: User) -> UserSelf:
    return UserSelf(id=user.id, email=user.email, display_name=user.display_name)


async def update_me(db, user: User, body: UserUpdate) -> UserSelf:
    user.display_name = body.display_name
    await db.flush()
    return UserSelf(id=user.id, email=user.email, display_name=user.display_name)


async def delete_me(db, user: User, response: Response) -> None:
    await db.execute(text("SELECT id FROM users WHERE id = :uid FOR UPDATE"), {"uid": user.id})
    listing_result = await db.execute(select(Listing).where(Listing.owner_id == user.id))
    owned = listing_result.scalar_one_or_none()
    if owned:
        await db.execute(text("SELECT id FROM listings WHERE id = :lid FOR UPDATE"), {"lid": owned.id})
    await db.delete(user)
    await db.flush()
    clear_session_cookie(response)
