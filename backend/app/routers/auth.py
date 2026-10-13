from __future__ import annotations
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import (
    RequestCodeRequest, RequestCodeResponse,
    VerifyCodeRequest, AuthResponse,
)
from app.services.auth_service import request_code, verify_code, logout
from app.utils.deps import check_origin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/request-code", response_model=RequestCodeResponse, status_code=200)
async def api_request_code(
    body: RequestCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _o: None = Depends(check_origin),
):
    """Запросить код подтверждения на email."""
    return await request_code(db, body, request)


@router.post("/verify-code", response_model=AuthResponse, status_code=200)
async def api_verify_code(
    body: VerifyCodeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _o: None = Depends(check_origin),
):
    """Проверить код и войти (создать сессию)."""
    return await verify_code(db, body, request, response)


@router.post("/logout", status_code=204)
async def api_logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await logout(db, request, response)
    return Response(status_code=204)
