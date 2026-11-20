from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.compare import CompareCode, CompareGroupOut
from app.services import compare_service
from app.utils.deps import check_origin, check_origin_no_body, require_user

router = APIRouter(prefix="/api", tags=["compare"])


@router.get("/compare", response_model=list[CompareGroupOut])
async def api_list(user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function")):
    """The person's comparisons, newest first."""
    return await compare_service.list_groups(db, user)


@router.post("/compare", response_model=CompareGroupOut)
async def api_open(user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function"),
                   _o: None = Depends(check_origin_no_body)):
    """The link to send a friend: one nobody has joined yet is reused."""
    return await compare_service.open_group(db, user)


@router.post("/compare/join", response_model=CompareGroupOut)
async def api_join(body: CompareCode, user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function"),
                   _o: None = Depends(check_origin)):
    """Takes the code or the whole link. Works before the questionnaire is done."""
    return await compare_service.join(db, user, body.code)


@router.delete("/compare/{group_id}/membership", status_code=204)
async def api_leave(group_id: UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db, scope="function"),
                    _o: None = Depends(check_origin_no_body)):
    await compare_service.leave(db, user, group_id)
    return Response(status_code=204)
