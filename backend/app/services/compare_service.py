"""Comparing with friends: a link anyone can open to take the questionnaire and see how they
match, with no home involved (a couple, friends, people about to rent together).

Who sees what:
  - members see each other's first name, photo and questionnaire progress as counts
    ("12 of 20"), never any answers;
  - once both people have finished, each sees their score with the other: the rounded percent
    and the topic badges, the same as on a room page. Hard blocks don't apply here (see
    score_pair's ignore_blocks).
"""

from __future__ import annotations
import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import delete, exists, func, select
from app import questionnaires
from app.config import settings
from app.models.compare import CompareGroup, CompareMember
from app.models.questionnaire import QuestionnaireResponse
from app.models.user import User
from app.schemas.compare import CompareGroupOut, CompareMemberOut
from app.schemas.feed import Compatibility
from app.services import image_service
from app.services.home_service import _CODE_ALPHABET, _CODE_LENGTH, parse_invite_code
from app.utils.errors import compare_full, compare_invalid, not_found, too_many_compares

MAX_MEMBERS = 6          # the biggest room on the site
MAX_GROUPS = 20          # per person; leaving old ones makes room


def _url(code: str) -> str:
    return f"{settings.public_origin.rstrip('/')}/compare#code={code}"


def _active(group: CompareGroup) -> list[CompareMember]:
    """Accounts waiting to be erased are left out, as everywhere else."""
    return [m for m in group.members if m.user.deleted_at is None]


async def _answers(db, user_ids) -> dict:
    if not user_ids:
        return {}
    rows = await db.execute(select(QuestionnaireResponse).where(
        QuestionnaireResponse.user_id.in_(user_ids), QuestionnaireResponse.version == questionnaires.CURRENT))
    return {r.user_id: r.answers for r in rows.scalars().all()}


def _progress(answers: dict | None, user: User) -> tuple[bool, int, int]:
    """(complete, answered, total) over the required questions that apply to this person.
    Before "are you 18?" is answered, counted as for an adult (the longer list)."""
    q = questionnaires.current()
    answers = answers or {}
    adult = user.is_adult if user.is_adult is not None else True
    required = [x["id"] for x in q.QUESTIONNAIRE["questions"] if x["required"] and q.applies(x, answers, adult)]
    return q.is_complete(answers, user.is_adult), sum(1 for qid in required if qid in answers), len(required)


async def _out(db, group: CompareGroup, viewer: User) -> CompareGroupOut:
    q = questionnaires.current()
    members = _active(group)
    answers = await _answers(db, [m.user_id for m in members])
    progress = {m.user_id: _progress(answers.get(m.user_id), m.user) for m in members}
    mine = (q.for_scoring(answers[viewer.id], bool(viewer.is_adult))
            if progress.get(viewer.id, (False,))[0] else None)

    out, pairs = [], []
    for m in members:
        complete, answered, total = progress[m.user_id]
        compatibility = None
        if mine is not None and complete and m.user_id != viewer.id:
            pair = q.score_pair(mine, q.for_scoring(answers[m.user_id], bool(m.user.is_adult)), ignore_blocks=True)
            pairs.append(pair)
            compatibility = Compatibility(**pair.public())
        out.append(CompareMemberOut(
            user_id=m.user_id, first_name=m.user.first_name, avatar_url=image_service.avatar_url(m.user.avatar_file),
            is_you=m.user_id == viewer.id, complete=complete, answered=answered, total=total,
            compatibility=compatibility))

    overall = None
    if len(pairs) >= 2:
        badges = {name: max((p.badges()[name] for p in pairs), key={"match": 0, "ok": 1, "discuss": 2}.get)
                  for name in q.DIMENSIONS}
        overall = Compatibility(percent=q.round_score(q.score_room(pairs)), badges=badges)
    return CompareGroupOut(id=group.id, code=group.code, url=_url(group.code), created_by_you=group.created_by == viewer.id,
                           members=out, compatibility=overall)


async def _mine(db, user: User) -> list[CompareGroup]:
    result = await db.execute(select(CompareGroup).join(CompareMember).where(CompareMember.user_id == user.id)
                              .order_by(CompareGroup.created_at.desc()))
    return list(result.scalars().unique().all())


async def list_groups(db, user: User) -> list[CompareGroupOut]:
    """The person's comparisons, newest first."""
    return [await _out(db, g, user) for g in await _mine(db, user)]


async def _count(db, user: User) -> int:
    return (await db.execute(select(func.count()).select_from(CompareMember)
                             .where(CompareMember.user_id == user.id))).scalar_one()


async def open_group(db, user: User) -> CompareGroupOut:
    """The person's link to send. One they made that nobody has joined yet is reused, so the
    link stays the same however many times it is asked for."""
    for group in await _mine(db, user):
        if group.created_by == user.id and [m.user_id for m in _active(group)] == [user.id]:
            return await _out(db, group, user)
    if await _count(db, user) >= MAX_GROUPS:
        raise too_many_compares()
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if not (await db.execute(select(exists().where(CompareGroup.code == code)))).scalar():
            break
    group = CompareGroup(id=uuid.uuid4(), code=code, created_by=user.id, created_at=datetime.now(timezone.utc))
    member = CompareMember(user_id=user.id, joined_at=datetime.now(timezone.utc))
    member.user = user
    group.members.append(member)
    db.add(group)
    await db.flush()
    return await _out(db, group, user)


async def _by_code(db, text: str) -> CompareGroup:
    code = parse_invite_code(text)
    group = (await db.execute(select(CompareGroup).where(CompareGroup.code == code))).scalar_one_or_none() if code else None
    if group is None:
        raise compare_invalid()
    return group


async def join(db, user: User, text: str) -> CompareGroupOut:
    """Join by link or code. Opening a link you are already in is not an error."""
    group = await _by_code(db, text)
    if any(m.user_id == user.id for m in group.members):
        return await _out(db, group, user)
    if len(_active(group)) >= MAX_MEMBERS:
        raise compare_full()
    if await _count(db, user) >= MAX_GROUPS:
        raise too_many_compares()
    member = CompareMember(user_id=user.id, joined_at=datetime.now(timezone.utc))
    member.user = user
    group.members.append(member)
    await db.flush()
    return await _out(db, group, user)


async def leave(db, user: User, group_id) -> None:
    """Leave a comparison. The last one out takes the link with them."""
    group = (await db.execute(select(CompareGroup).where(CompareGroup.id == group_id))).scalar_one_or_none()
    member = next((m for m in group.members if m.user_id == user.id), None) if group else None
    if member is None:
        raise not_found("Сравнение не найдено.")
    group.members.remove(member)
    await db.flush()
    if not group.members:
        await db.delete(group)
        await db.flush()


async def drop_empty(db) -> None:
    """Groups whose last member's account was erased."""
    await db.execute(delete(CompareGroup).where(~exists().where(CompareMember.group_id == CompareGroup.id)))
