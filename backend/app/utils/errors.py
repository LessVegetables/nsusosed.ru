from __future__ import annotations
import uuid
from typing import Dict, Optional
from fastapi.responses import JSONResponse
from app.schemas.error import ErrorDetail, ErrorEnvelope


def make_error_response(status_code: int, code: str, message: str,
                        fields: Optional[Dict[str, str]] = None,
                        request_id: Optional[str] = None,
                        retry_after: Optional[int] = None,
                        data: Optional[dict] = None) -> JSONResponse:
    rid = request_id or str(uuid.uuid4())
    detail = ErrorDetail(code=code, message=message, fields=fields or {},
                         request_id=rid, retry_after=retry_after, data=data or {})
    envelope = ErrorEnvelope(error=detail)
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(), headers=headers)


def beta_closed() -> "AppError":
    """Closed beta and this address isn't on BETA_EMAILS. Shown under the email field."""
    return AppError(403, "BETA_CLOSED", "Сайт в закрытом тесте: войти могут только приглашённые.",
                    {"email": "BETA_CLOSED"})


class FieldErrors(ValueError):
    """Ошибка валидации с привязкой к полям. Бросается из model_validator,
    обработчик RequestValidationError раскладывает её по полям ответа."""

    def __init__(self, fields: Dict[str, str]):
        self.fields = fields
        super().__init__("; ".join(f"{k}: {v}" for k, v in fields.items()))


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str,
                 fields: Optional[Dict[str, str]] = None,
                 retry_after: Optional[int] = None,
                 data: Optional[dict] = None):
        self.data = data or {}
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


def rate_limited(retry_after: int):
    return AppError(429, "RATE_LIMITED", f"Слишком много попыток. Повторите через {retry_after} с.",
                    retry_after=retry_after)


def validation_error(message: str, fields: Optional[Dict[str, str]] = None):
    return AppError(422, "VALIDATION_ERROR", message, fields)


def photo_bad_type():
    return AppError(415, "PHOTO_BAD_TYPE", "Поддерживаются фото в форматах JPEG, PNG и WebP.")


def photo_too_large():
    return AppError(413, "PHOTO_TOO_LARGE", "Фото слишком большое.")


def too_many_photos():
    return AppError(409, "TOO_MANY_PHOTOS", "Достигнуто максимальное число фото.")


def room_taken(room_id) -> AppError:
    """The dorm room is already listed. The page offers to contact the people who listed it."""
    return AppError(409, "ROOM_TAKEN", "Эта комната уже есть на сайте.", data={"room_id": str(room_id)})


def already_in_home() -> AppError:
    return AppError(409, "ALREADY_IN_HOME", "Вы уже живёте в другом жилье на сайте.")


def emoji_taken(index: int) -> AppError:
    return AppError(409, "EMOJI_TAKEN", "Такие эмодзи уже заняты.", {f"rooms.{index}.emoji": "EMOJI_TAKEN"})


def no_permission() -> AppError:
    return AppError(403, "NO_PERMISSION", "У вас нет прав на это действие.")


def room_occupied(index: int) -> AppError:
    return AppError(409, "ROOM_OCCUPIED", "В этой комнате живут люди.", {f"rooms.{index}": "ROOM_OCCUPIED"})


def invite_invalid() -> AppError:
    return AppError(404, "INVITE_INVALID", "Приглашение не найдено, отозвано или истекло.")


def last_manager() -> AppError:
    return AppError(409, "LAST_MANAGER", "Хотя бы у одного жителя должно остаться право управлять жителями.")
