from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import QUESTIONNAIRE_V1
from app.database import get_db
from app.models.user import User
from app.schemas.profile import ProfileInput, ProfileSelf, ProfileResponse
from app.services.profile_service import get_profile, save_profile
from app.utils.deps import require_user, check_origin

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/questions")
async def api_get_questions():
    return {"version": QUESTIONNAIRE_V1["version"], "questions": QUESTIONNAIRE_V1["questions"]}


@router.get("/profile", response_model=ProfileResponse)
async def api_get_profile(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await get_profile(db, user)


@router.put("/profile", response_model=ProfileSelf)
async def api_save_profile(body: ProfileInput, user: User = Depends(require_user),
                           db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await save_profile(db, user, body)
