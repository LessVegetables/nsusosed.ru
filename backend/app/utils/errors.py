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


def invalid_credentials():
    return AppError(401, "INVALID_CREDENTIALS", "Неверный email или пароль.")


def forbidden(msg: str = "Действие недоступно."):
    return AppError(403, "FORBIDDEN", msg)


def not_found(msg: str = "Не найдено."):
    return AppError(404, "NOT_FOUND", msg)


def version_conflict():
    return AppError(409, "VERSION_CONFLICT", "Данные изменились. Загрузите актуальную версию.")


def listing_exists(msg: str = "Карточка уже существует."):
    return AppError(409, "LISTING_EXISTS", msg)


def membership_conflict(msg: str = "Присоединение невозможно."):
    return AppError(409, "MEMBERSHIP_CONFLICT", msg)


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
