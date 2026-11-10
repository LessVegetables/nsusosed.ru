from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.questionnaire import AnswersIn, QuestionnaireOut
from app.services.questionnaire_service import get_questionnaire, save_answers
from app.utils.deps import check_origin, require_user

router = APIRouter(prefix="/api", tags=["questionnaire"])


@router.get("/questionnaire", response_model=QuestionnaireOut)
async def api_get_questionnaire(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    """The current questionnaire and the person's own answers to it."""
    return await get_questionnaire(db, user)


@router.put("/questionnaire", response_model=QuestionnaireOut)
async def api_save_answers(body: AnswersIn, user: User = Depends(require_user),
                           db: AsyncSession = Depends(get_db), _o: None = Depends(check_origin)):
    return await save_answers(db, user, body)
