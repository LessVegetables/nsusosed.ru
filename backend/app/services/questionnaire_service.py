from __future__ import annotations
from sqlalchemy import select
from app import questionnaires
from app.models.questionnaire import QuestionnaireResponse
from app.models.user import User
from app.schemas.questionnaire import AnswersIn, QuestionnaireOut
from app.utils.errors import AppError, validation_error


async def _row(db, user: User) -> QuestionnaireResponse | None:
    result = await db.execute(select(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user.id))
    return result.scalar_one_or_none()


def _current_answers(row: QuestionnaireResponse | None) -> dict:
    """Answers given to an older version don't carry over: the questions may have changed."""
    return dict(row.answers) if row is not None and row.version == questionnaires.CURRENT else {}


async def is_complete(db, user: User) -> bool:
    return questionnaires.current().is_complete(_current_answers(await _row(db, user)), user.is_adult)


def _out(answers: dict, user: User) -> QuestionnaireOut:
    q = questionnaires.current()
    adult = bool(user.is_adult)
    return QuestionnaireOut(
        version=q.VERSION, blocks=q.QUESTIONNAIRE["blocks"], questions=q.QUESTIONNAIRE["questions"],
        answers=answers, complete=q.is_complete(answers, user.is_adult),
        missing=q.missing_required(answers, adult) if user.is_adult is not None else [],
    )


async def get_questionnaire(db, user: User) -> QuestionnaireOut:
    return _out(_current_answers(await _row(db, user)), user)


async def save_answers(db, user: User, body: AnswersIn) -> QuestionnaireOut:
    if body.version != questionnaires.CURRENT:
        raise AppError(409, "QUESTIONNAIRE_OUTDATED", "Анкета обновилась. Перезагрузите страницу.")
    if user.is_adult is None:
        # Whether the nicotine questions apply depends on it.
        raise AppError(409, "ABOUT_REQUIRED", "Сначала ответьте, есть ли вам 18.")
    q = questionnaires.current()
    row = await _row(db, user)
    merged = {**_current_answers(row), **body.answers}
    answers, errors = q.clean(merged, user.is_adult)
    if errors:
        raise validation_error("Проверьте ответы.", {f"answers.{qid}": reason for qid, reason in errors.items()})
    if row is None:
        db.add(QuestionnaireResponse(user_id=user.id, version=q.VERSION, answers=answers))
    else:
        row.version, row.answers = q.VERSION, answers
    await db.flush()
    return _out(answers, user)
