from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Request, Response
from sqlalchemy import delete, select, text
from app.config import settings
from app.models.user import User
from app.models.profile import Profile
from app.models.session import Session
from app.schemas.auth import (
    RequestCodeRequest, RequestCodeResponse,
    VerifyCodeRequest, AuthResponse, UserBrief,
)
from app.config import QUESTIONNAIRE
from app.schemas.user import UserSelf, UserUpdate, UserHome
from app.utils.security import normalize_email, validate_email_domain
from app.utils.session import create_session, set_session_cookie, clear_session_cookie, get_current_session, cleanup_expired_sessions
from app.utils.errors import AppError, validation_error, invalid_code
from app.services.email_service import send_otp_email
from app.services.otp_service import create_otp, verify_otp, cleanup_expired as cleanup_expired_otps
from app.services import rate_limit_service as rl

logger = logging.getLogger("nsusosed")


async def request_code(db, body: RequestCodeRequest, request: Request) -> RequestCodeResponse:
    """Запросить код подтверждения на email."""
    email = normalize_email(body.email)

    # 1. Проверка домена
    if not validate_email_domain(email, settings.email_domains):
        reason = "DOMAIN_NOT_ALLOWED" if "@" in email else "INVALID_EMAIL"
        raise validation_error("Недопустимый адрес электронной почты.", {"email": reason})

    ip = rl.client_ip(request)
    await rl.check_request_code(db, email, ip)
    await rl.record(db, "code_request", email, ip)

    # 2. Сгенерировать OTP. Пользователь создаётся только после проверки кода.
    code = await create_otp(db, email, privacy_accepted_at=datetime.now(timezone.utc))

    # 3. Отправить email
    sent = await send_otp_email(email, code)
    if not sent:
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

    ip = rl.client_ip(request)
    await rl.check_verify(db, email, ip)

    otp = await verify_otp(db, email, body.code.strip())
    if otp is None:
        await rl.record(db, "verify_fail", email, ip)
        # Сохраняем счётчик попыток и событие до ошибки: иначе get_db откатит транзакцию.
        await db.commit()
        raise invalid_code()

    await rl.record(db, "verify_ok", email, ip)

    # Находим пользователя или регистрируем нового
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            display_name="Пользователь",
            privacy_version=1,
            privacy_accepted_at=otp.privacy_accepted_at or datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

    # Вход в срок ожидания отменяет удаление аккаунта.
    account_restored = user.deleted_at is not None
    if account_restored:
        user.deleted_at = None
        await db.flush()

    # Анкета заполнена (и текущей версии)?
    prof_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = prof_result.scalar_one_or_none()
    profile_complete = profile is not None and profile.questionnaire_version == QUESTIONNAIRE["version"]

    # Создаём сессию
    token = await create_session(db, user.id, request)

    # Попутно чистим просроченное (индексы по времени есть у всех трёх таблиц)
    await cleanup_expired_sessions(db)
    await cleanup_expired_otps(db)
    await rl.cleanup_old_events(db)
    await purge_deleted_accounts(db)
    set_session_cookie(response, token)

    return AuthResponse(
        user=UserBrief(id=user.id, email=user.email, display_name=user.display_name),
        profile_complete=profile_complete,
        account_restored=account_restored,
    )


async def logout(db, request: Request, response: Response) -> None:
    session = await get_current_session(db, request)
    if session is not None:
        await db.delete(session)
        await db.flush()
    clear_session_cookie(response)


async def get_me(db, user: User) -> UserSelf:
    from app.services.membership_service import get_membership
    prof = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = prof.scalar_one_or_none()
    membership = await get_membership(db, user.id)
    return UserSelf(
        id=user.id, email=user.email, display_name=user.display_name, language=user.language,
        situation=profile.situation if profile else None,
        # Анкета старой версии годится для подбора, но новые вопросы ещё не отвечены.
        profile_complete=profile is not None and profile.questionnaire_version == QUESTIONNAIRE["version"],
        home=UserHome(id=membership.listing_id, is_admin=membership.is_admin) if membership else None,
    )


async def update_me(db, user: User, body: UserUpdate) -> UserSelf:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.language is not None:
        user.language = body.language
    await db.flush()
    return await get_me(db, user)


async def delete_me(db, user: User, response: Response) -> None:
    """Удаление аккаунта, шаг 1: скрыть сразу, стереть через ACCOUNT_DELETION_GRACE_DAYS.

    Сразу: все сессии закрыты, человек не виден соседям и кандидатам, его анкета не
    участвует в подборе, админство в жилье переходит к активному соседу. Вход по коду
    в течение срока всё отменяет (verify_code). Насовсем стирает purge_deleted_accounts.
    """
    from app.services.membership_service import ensure_active_admin, get_membership
    await db.execute(text("SELECT id FROM users WHERE id = :uid FOR UPDATE"), {"uid": user.id})
    user.deleted_at = datetime.now(timezone.utc)
    await db.execute(delete(Session).where(Session.user_id == user.id))
    await db.flush()
    membership = await get_membership(db, user.id)
    if membership is not None:
        await ensure_active_admin(db, membership.listing_id)
    clear_session_cookie(response)


async def purge_deleted_accounts(db) -> int:
    """Удаление аккаунта, шаг 2: стереть аккаунты, у которых истёк срок ожидания.
    Анкета и сессии уходят каскадом; жильё — по обычным правилам ухода жильца
    (последний ушёл — жильё и фото удаляются). Вызывается при каждом входе и при старте."""
    from app.services.membership_service import get_membership, remove_member
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.account_deletion_grace_days)
    result = await db.execute(
        select(User).where(User.deleted_at.is_not(None), User.deleted_at < cutoff).with_for_update(skip_locked=True))
    users = list(result.scalars().all())
    for user in users:
        membership = await get_membership(db, user.id)
        if membership is not None:
            await remove_member(db, membership)
        await db.delete(user)
    if users:
        await db.flush()
        logger.info("Erased %d deleted accounts", len(users))
    return len(users)
