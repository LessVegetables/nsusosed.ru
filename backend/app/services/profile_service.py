from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.profile import Profile
from app.schemas.profile import ProfileInput, ProfileSelf, ProfileResponse
from app.utils.errors import version_conflict


async def get_profile(db, user) -> ProfileResponse:
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return ProfileResponse(profile=None)
    return ProfileResponse(
        profile=ProfileSelf(
            user_id=profile.user_id,
            questionnaire_version=profile.questionnaire_version,
            answers=profile.answers,
            situation=profile.situation,
            budget_max_rub=profile.budget_max_rub,
            version=profile.version,
            updated_at=profile.updated_at,
        )
    )


async def save_profile(db, user, body: ProfileInput) -> ProfileSelf:
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        if body.expected_version != 0:
            raise version_conflict()
        profile = Profile(
            user_id=user.id,
            questionnaire_version=body.questionnaire_version,
            answers={k: v.model_dump() for k, v in body.answers.items()},
            situation=body.situation,
            budget_max_rub=body.budget_max_rub,
            version=1,
        )
        db.add(profile)
    else:
        if body.expected_version != profile.version:
            raise version_conflict()
        profile.answers = {k: v.model_dump() for k, v in body.answers.items()}
        profile.situation = body.situation
        profile.budget_max_rub = body.budget_max_rub
        profile.version += 1
        profile.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return ProfileSelf(
        user_id=profile.user_id,
        questionnaire_version=profile.questionnaire_version,
        answers=profile.answers,
        situation=profile.situation,
        budget_max_rub=profile.budget_max_rub,
        version=profile.version,
        updated_at=profile.updated_at,
    )
