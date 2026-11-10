from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Request, Response
from sqlalchemy import delete, select, text
from app.config import FACULTY_IDS, settings
from app.models.user import User
from app.models.session import Session
from app.schemas.auth import (
    RequestCodeRequest, RequestCodeResponse,
    VerifyCodeRequest, AuthResponse,
)
from app.models.user_contact import UserContact
from app.schemas.user import Contact, ContactsUpdate, UserSelf, UserUpdate
from app.services.image_service import avatar_url, drop_avatar
from app.utils.contact import PRIMARY_TYPES, contact_url, normalize_contact
from app.utils.security import normalize_email, validate_email_domain
from app.utils.session import create_session, set_session_cookie, clear_session_cookie, get_current_session, cleanup_expired_sessions
from app.utils.errors import AppError, validation_error, invalid_code
from app.services.email_service import send_otp_email
from app.services.otp_service import create_otp, verify_otp, cleanup_expired as cleanup_expired_otps
from app.services import questionnaire_service, rate_limit_service as rl

logger = logging.getLogger("nsusosed")


async def _find_user(db, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def request_code(db, body: RequestCodeRequest, request: Request) -> RequestCodeResponse:
    """Email a login code. The account itself is created only once the code is verified."""
    email = normalize_email(body.email)

    if not validate_email_domain(email, settings.email_domains):
        reason = "DOMAIN_NOT_ALLOWED" if "@" in email else "INVALID_EMAIL"
        raise validation_error("Недопустимый адрес электронной почты.", {"email": reason})

    ip = rl.client_ip(request)
    await rl.check_request_code(db, email, ip)
    await rl.record(db, "code_request", email, ip)

    code = await create_otp(db, email, privacy_accepted_at=datetime.now(timezone.utc))

    sent = await send_otp_email(email, code, body.language or "ru")
    if not sent:
        raise AppError(503, "EMAIL_SEND_FAILED", "Не удалось отправить код. Попробуйте позже.")

    local, domain = email.rsplit("@", 1)
    masked = f"{local[0]}***@{domain}" if len(local) > 1 else f"*@{domain}"

    return RequestCodeResponse(
        email_masked=masked,
        ttl_seconds=settings.otp_ttl_seconds,
        # Tells the login page whether to ask for a name. This does reveal whether an
        # address has an account; accepted for a closed @g.nsu.ru audience.
        is_new=await _find_user(db, email) is None,
    )


async def verify_code(
    db, body: VerifyCodeRequest, request: Request, response: Response
) -> AuthResponse:
    """Check the code, create the account on first login, open a session."""
    email = normalize_email(body.email)

    ip = rl.client_ip(request)
    await rl.check_verify(db, email, ip)

    user = await _find_user(db, email)
    is_new = user is None
    # Checked before the code so that a missing name doesn't burn an attempt.
    if is_new and not (body.first_name and body.last_name):
        raise validation_error("Укажите имя и фамилию.", {
            field: "MISSING" for field in ("first_name", "last_name") if not getattr(body, field)})

    otp = await verify_otp(db, email, body.code.strip())
    if otp is None:
        await rl.record(db, "verify_fail", email, ip)
        # Keep the attempt counter and the event: get_db rolls the transaction back on error.
        await db.commit()
        raise invalid_code()

    await rl.record(db, "verify_ok", email, ip)

    if user is None:
        user = User(
            email=email,
            first_name=body.first_name,
            last_name=body.last_name,
            language=body.language or "ru",
            privacy_version=1,
            privacy_accepted_at=otp.privacy_accepted_at or datetime.now(timezone.utc),
        )
        db.add(user)
    elif body.language is not None:
        user.language = body.language

    # Logging in during the grace period cancels the deletion.
    account_restored = user.deleted_at is not None
    if account_restored:
        user.deleted_at = None
    await db.flush()

    token = await create_session(db, user.id, request)

    # Housekeeping on the way (all three tables are indexed by time).
    await cleanup_expired_sessions(db)
    await cleanup_expired_otps(db)
    await rl.cleanup_old_events(db)
    await purge_deleted_accounts(db)
    set_session_cookie(response, token)

    return AuthResponse(user_id=user.id, first_name=user.first_name, is_new=is_new,
                        questionnaire_complete=await questionnaire_service.is_complete(db, user),
                        intent=user.intent, account_restored=account_restored)


async def logout(db, request: Request, response: Response) -> None:
    session = await get_current_session(db, request)
    if session is not None:
        await db.delete(session)
        await db.flush()
    clear_session_cookie(response)


async def get_me(db, user: User) -> UserSelf:
    return UserSelf(
        id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name,
        language=user.language, gender=user.gender, faculty=user.faculty, is_adult=user.is_adult,
        intent=user.intent, bio=user.bio,
        avatar_url=avatar_url(user.avatar_file),
        contacts=[Contact(type=c.type, value=c.value, url=contact_url(c.type, c.value)) for c in user.contacts],
        questionnaire_complete=await questionnaire_service.is_complete(db, user),
    )


async def update_me(db, user: User, body: UserUpdate) -> UserSelf:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "faculty" in changes and changes["faculty"] not in FACULTY_IDS:
        raise validation_error("Неизвестный факультет.", {"faculty": "UNKNOWN"})
    for field, value in changes.items():
        setattr(user, field, value)
    await db.flush()
    return await get_me(db, user)


async def update_contacts(db, user: User, body: ContactsUpdate) -> UserSelf:
    """Replace the person's contact list. An empty list is fine (a seeker needs none);
    a non-empty one must include a phone, Telegram or VK."""
    errors: dict[str, str] = {}
    cleaned: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, item in enumerate(body.contacts):
        value, reason = normalize_contact(item.type, item.value)
        if reason is None and item.type in seen:
            reason = "DUPLICATE_TYPE"
        if reason:
            errors[f"contacts.{i}.{'type' if reason in ('INVALID_CHOICE', 'DUPLICATE_TYPE') else 'value'}"] = reason
            continue
        seen.add(item.type)
        cleaned.append((item.type, value))
    if not errors and cleaned and not seen & set(PRIMARY_TYPES):
        errors["contacts"] = "NEED_PRIMARY"
    if errors:
        raise validation_error("Проверьте контакты.", errors)

    user.contacts.clear()
    await db.flush()  # delete before insert: (user, type) is unique
    user.contacts.extend(UserContact(position=i, type=t, value=v) for i, (t, v) in enumerate(cleaned))
    await db.flush()
    return await get_me(db, user)


async def delete_me(db, user: User, response: Response) -> None:
    """Account deletion, step 1: hide now, erase after ACCOUNT_DELETION_GRACE_DAYS.

    All sessions are closed right away. Logging in with a code during the grace period
    undoes it (verify_code); purge_deleted_accounts erases for good.
    """
    await db.execute(text("SELECT id FROM users WHERE id = :uid FOR UPDATE"), {"uid": user.id})
    user.deleted_at = datetime.now(timezone.utc)
    await db.execute(delete(Session).where(Session.user_id == user.id))
    await db.flush()
    clear_session_cookie(response)


async def purge_deleted_accounts(db) -> int:
    """Account deletion, step 2: erase accounts whose grace period has run out.
    Called on every login and at startup."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.account_deletion_grace_days)
    result = await db.execute(
        select(User).where(User.deleted_at.is_not(None), User.deleted_at < cutoff).with_for_update(skip_locked=True))
    users = list(result.scalars().all())
    for user in users:
        drop_avatar(db, user)
        await db.delete(user)
    if users:
        await db.flush()
        logger.info("Erased %d deleted accounts", len(users))
    return len(users)
