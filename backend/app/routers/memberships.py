from __future__ import annotations
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.membership import JoinRequest, JoinResponse
from app.services.membership_service import join_by_invite, leave_membership
from app.utils.deps import require_user, check_origin

router = APIRouter(prefix="/api", tags=["memberships"])


@router.post("/memberships/join", response_model=JoinResponse)
async def api_join(body: JoinRequest, user: User = Depends(require_user),
                   db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await join_by_invite(db, user, body.invite_token)


@router.delete("/membership", status_code=204)
async def api_leave(user: User = Depends(require_user),
                    db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    await leave_membership(db, user)
    return Response(status_code=204)
