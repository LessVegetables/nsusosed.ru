from __future__ import annotations
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.routers import auth, homes, meta, questionnaire, users
from app.utils.errors import AppError, FieldErrors, make_error_response

logger = logging.getLogger("nsusosed")
logging.basicConfig(level=logging.INFO)



@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import async_session_factory
    from app.services.auth_service import purge_deleted_accounts
    try:
        async with async_session_factory() as db:
            await purge_deleted_accounts(db)
            await db.commit()
    except Exception:
        logger.exception("Purging deleted accounts failed")
    yield


app = FastAPI(title="nsusosed API", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(meta.router)
app.include_router(questionnaire.router)
app.include_router(homes.router)


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = str(uuid.uuid4())
    logger.warning("AppError %s %s: %s", exc.status_code, exc.code, rid)
    return make_error_response(exc.status_code, exc.code, exc.message, exc.fields, rid, exc.retry_after, exc.data)


# Проверки в сервисах («комната уже есть», «уже живёт в жилье») не спасают от гонки:
# два одновременных запроса проходят проверку, и второй упирается в уникальный индекс.
# Такой отказ — тот же конфликт, что и при проверке, а не 500.
_UNIQUE_CONFLICTS: dict[str, tuple[str, str]] = {
    "uq_homes_dorm_room": ("ROOM_TAKEN", "Эта комната уже есть на сайте."),
    "uq_memberships_user": ("ALREADY_IN_HOME", "Вы уже живёте в другом жилье на сайте."),
    "rooms_emoji_key_key": ("EMOJI_TAKEN", "Такие эмодзи уже заняты."),
}


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    rid = str(uuid.uuid4())
    # asyncpg кладёт исходную ошибку Postgres в __cause__ ошибки DBAPI.
    constraint = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
    code, message = _UNIQUE_CONFLICTS.get(constraint, ("CONFLICT", "Данные изменились. Повторите действие."))
    logger.warning("IntegrityError on %s -> 409 %s: %s", constraint, code, rid)
    return make_error_response(409, code, message, request_id=rid)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = str(uuid.uuid4())
    fields = {}
    # fields: {"путь.к.полю": "КОД_ПРИЧИНЫ"}. Коды стабильны, фронтенд переводит их сам.
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []) if l != "body")
        ctx_error = (err.get("ctx") or {}).get("error")
        if isinstance(ctx_error, FieldErrors):
            # Ключи FieldErrors заданы относительно места, где сработал валидатор.
            for key, reason in ctx_error.fields.items():
                path = ".".join(p for p in (loc, key) if p)
                fields[path or "_"] = reason
            continue
        # Встроенные ошибки pydantic: missing → MISSING, less_than_equal → LESS_THAN_EQUAL и т.п.
        fields[loc or "_"] = str(err.get("type", "invalid")).upper()
    logger.warning("Validation error %s: %s", rid, fields)
    return make_error_response(422, "VALIDATION_ERROR", "Проверьте заполненные поля", fields, rid)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    rid = str(uuid.uuid4())
    code_map = {
        401: "AUTH_REQUIRED", 403: "FORBIDDEN", 404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE", 429: "RATE_LIMITED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return make_error_response(
        exc.status_code, code,
        str(exc.detail) if exc.detail else "Ошибка",
        request_id=rid,
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = str(uuid.uuid4())
    logger.exception("Unhandled error %s: %s", rid, exc)
    return make_error_response(500, "INTERNAL_ERROR", "Не удалось выполнить действие.", request_id=rid)
