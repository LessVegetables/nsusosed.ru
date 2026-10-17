from __future__ import annotations
import uuid
from typing import Dict, Optional
from fastapi.responses import JSONResponse
from app.schemas.error import ErrorDetail, ErrorEnvelope


def make_error_response(status_code: int, code: str, message: str,
                        fields: Optional[Dict[str, str]] = None,
                        request_id: Optional[str] = None,
                        retry_after: Optional[int] = None) -> JSONResponse:
    rid = request_id or str(uuid.uuid4())
    detail = ErrorDetail(code=code, message=message, fields=fields or {},
                         request_id=rid, retry_after=retry_after)
    envelope = ErrorEnvelope(error=detail)
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(), headers=headers)


class FieldErrors(ValueError):
    """Ошибка валидации с привязкой к полям. Бросается из model_validator,
    обработчик RequestValidationError раскладывает её по полям ответа."""

    def __init__(self, fields: Dict[str, str]):
        self.fields = fields
        super().__init__("; ".join(f"{k}: {v}" for k, v in fields.items()))


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str,
                 fields: Optional[Dict[str, str]] = None,
                 retry_after: Optional[int] = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.retry_after = retry_after
        super().__init__(message)


def auth_required():
    return AppError(401, "AUTH_REQUIRED", "Нет действующей сессии. Войдите.")


def invalid_code():
    return AppError(401, "INVALID_CODE", "Неверный или просроченный код.")


def forbidden(msg: str = "Действие недоступно."):
    return AppError(403, "FORBIDDEN", msg)


def not_found(msg: str = "Не найдено."):
    return AppError(404, "NOT_FOUND", msg)


def version_conflict():
    return AppError(409, "VERSION_CONFLICT", "Данные изменились. Загрузите актуальную версию.")


def room_taken(building: str, room_number: int):
    return AppError(409, "ROOM_TAKEN", f"Карточка для {building}, комн. {room_number} уже существует.")


def already_in_room():
    return AppError(409, "ALREADY_IN_ROOM", "Вы уже участвуете в другой комнате.")


def room_full():
    return AppError(409, "ROOM_FULL", "Достигнуто максимальное число привязанных жильцов.")


def invite_invalid():
    return AppError(404, "INVITE_INVALID", "Приглашение не найдено или недействительно.")


def invite_expired():
    return AppError(404, "INVITE_EXPIRED", "Приглашение истекло.")


def occupancy_conflict():
    return AppError(409, "OCCUPANCY_CONFLICT", "Занятых мест не может быть меньше числа жильцов.")


def profile_required():
    return AppError(422, "PROFILE_REQUIRED", "Заполните анкету.")


def budget_required():
    return AppError(422, "BUDGET_REQUIRED", "Укажите месячный бюджет.")


def rate_limited(retry_after: int):
    return AppError(429, "RATE_LIMITED", f"Слишком много попыток. Повторите через {retry_after} с.",
                    retry_after=retry_after)


def validation_error(message: str, fields: Optional[Dict[str, str]] = None):
    return AppError(422, "VALIDATION_ERROR", message, fields)


def not_admin():
    return AppError(403, "NOT_ADMIN", "Это могут сделать только админы жилья.")


def not_member():
    return AppError(404, "NOT_MEMBER", "Этот человек не живёт в этом жилье.")


def last_admin():
    return AppError(409, "LAST_ADMIN", "В жилье должен остаться хотя бы один админ.")


def target_profile_required():
    return AppError(422, "TARGET_PROFILE_REQUIRED", "Админом можно сделать только того, кто заполнил анкету.")


def leave_home_first():
    return AppError(409, "LEAVE_HOME_FIRST", "Чтобы искать жильё, сначала покиньте своё.")


def photo_bad_type():
    return AppError(415, "PHOTO_BAD_TYPE", "Поддерживаются фото в форматах JPEG, PNG и WebP.")


def photo_too_large():
    return AppError(413, "PHOTO_TOO_LARGE", "Фото слишком большое.")


def too_many_photos():
    return AppError(409, "TOO_MANY_PHOTOS", "Достигнуто максимальное число фото.")
