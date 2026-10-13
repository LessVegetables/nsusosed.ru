from __future__ import annotations
import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.routers import auth, users, profiles, listings, memberships, matching
from app.utils.errors import AppError, FieldErrors, make_error_response

logger = logging.getLogger("nsusosed")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="nsusosed API", version="1.0.0")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(listings.router)
app.include_router(memberships.router)
app.include_router(matching.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = str(uuid.uuid4())
    logger.warning("AppError %s %s: %s", exc.status_code, exc.code, rid)
    return make_error_response(exc.status_code, exc.code, exc.message, exc.fields, rid, exc.retry_after)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = str(uuid.uuid4())
    fields = {}
    for err in exc.errors():
        ctx_error = (err.get("ctx") or {}).get("error")
        if isinstance(ctx_error, FieldErrors):
            fields.update(ctx_error.fields)
            continue
        loc = ".".join(str(l) for l in err.get("loc", []) if l != "body")
        msg = err.get("msg", "Неверное значение")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        if loc:
            fields[loc] = msg
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
