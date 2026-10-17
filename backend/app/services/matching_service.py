from __future__ import annotations
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import QUESTIONNAIRE, MATCHING_CONFIG, settings
from app.models.listing import Listing
from app.models.membership import Membership
from app.models.profile import Profile
from app.models.user import User
from app.schemas.matching import (MatchItem, MatchWarning, MatchReason, MatchListResponse, Compatibility,
                                  DimensionDetail, ContactListResponse)
from app.schemas.listing import ResidentBrief
from app.services.listing_service import contacts_out, photos_out
from app.services.photo_service import photo_url
from app.utils.errors import not_found, profile_required, budget_required

QUESTION_KEYS = [q["key"] for q in QUESTIONNAIRE["questions"]]
Q_MAP = {q["key"]: q for q in QUESTIONNAIRE["questions"]}
SCORE_VERSION = MATCHING_CONFIG["score_version"]
THRESHOLDS = MATCHING_CONFIG["explanation_thresholds"]
DISPERSION_THRESHOLD = MATCHING_CONFIG["dispersion_threshold"]

# Анкеты старых версий отвечают не на все вопросы: вопрос, на который не ответила
# одна из сторон, просто не участвует ни в проверке условий, ни в оценке.


def _normalize(key: str, value: int) -> float:
    return value / Q_MAP[key]["normalize_divisor"]


def _hard_conflicts(candidate: Dict[str, Any], resident: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Нарушенные жёсткие условия: [(вопрос, чьё условие: yours | theirs)]."""
    conflicts = []
    for key in QUESTION_KEYS:
        c = candidate.get(key)
        r = resident.get(key)
        if c is None or r is None:
            continue
        if c.get("hard", False) and r["value"] not in c.get("allowed", []):
            conflicts.append((key, "yours"))
        if r.get("hard", False) and c["value"] not in r.get("allowed", []):
            conflicts.append((key, "theirs"))
    return conflicts


def _check_hard(candidate: Dict[str, Any], resident: Dict[str, Any]) -> bool:
    return not _hard_conflicts(candidate, resident)


def _compute_compat(candidate: Dict[str, Any], residents: List[Dict[str, Any]], occupied: int) -> Compatibility:
    dims: List[DimensionDetail] = []
    warnings: List[MatchWarning] = []
    numerator = 0.0
    denominator = 0.0

    for key in QUESTION_KEYS:
        c_ans = candidate.get(key)
        r_answers = [r[key] for r in residents if key in r]
        if c_ans is None or not r_answers:
            continue
        c_norm = _normalize(key, c_ans["value"])
        c_imp = c_ans["importance"]
        room_val = sum(_normalize(key, a["value"]) for a in r_answers) / len(r_answers)
        room_imp = sum(a["importance"] for a in r_answers) / len(r_answers)
        weight = (c_imp + room_imp) / 2.0
        similarity = 1.0 - abs(c_norm - room_val)
        numerator += weight * similarity
        denominator += weight
        divisor = Q_MAP[key]["normalize_divisor"]

        if similarity >= THRESHOLDS["similar"]:
            label = "similar"
        elif similarity >= THRESHOLDS["minor_difference"]:
            label = "minor_difference"
        else:
            label = "noticeable_difference"

        dims.append(DimensionDetail(
            key=key, candidate_value=c_ans["value"],
            room_average=round(room_val * divisor, 4),
            similarity=round(similarity, 6),
            weight=round(weight, 4),
            contribution_points=0.0,
            label=label,
        ))

    score_raw = 100.0 * numerator / denominator if denominator > 0 else 0.0
    score = math.floor(score_raw + 0.5)

    for d in dims:
        d.contribution_points = round(100.0 * d.weight * d.similarity / denominator, 6) if denominator > 0 else 0.0

    if len(residents) < occupied:
        warnings.append(MatchWarning(code="PARTIAL_ANSWERS", answered=len(residents), occupied=occupied))

    for key in QUESTION_KEYS:
        r_values = [r[key]["value"] for r in residents if key in r]
        if not r_values:
            continue
        if key == "smoking":
            if len(set(r_values)) > 1:
                warnings.append(MatchWarning(code="RESIDENTS_DISAGREE", key=key))
                break
        else:
            if max(r_values) - min(r_values) >= DISPERSION_THRESHOLD:
                warnings.append(MatchWarning(code="RESIDENTS_DISAGREE", key=key))
                break

    return Compatibility(
        score=score, score_raw=round(score_raw, 6), score_version=SCORE_VERSION,
        warnings=warnings, dimensions=dims,
    )


def _reasons(cand: Profile, listing: Listing, r_profiles: List[Dict[str, Any]]) -> List[MatchReason]:
    """Все причины, по которым жильё не подходит кандидату (пусто — подходит)."""
    reasons: List[MatchReason] = []
    seen = set()
    for rp in r_profiles:
        for key, side in _hard_conflicts(cand.answers, rp):
            if (key, side) not in seen:
                seen.add((key, side))
                reasons.append(MatchReason(code="HARD_CONDITION", key=key, side=side))
    if listing.kind == "apartment":
        price = listing.monthly_cost_per_person_rub
        if price is not None and price > cand.budget_max_rub:
            reasons.append(MatchReason(code="OVER_BUDGET", price=price, budget=cand.budget_max_rub))
    return reasons


def _is_visible(l: Listing) -> bool:
    """Показывается ли жильё тем, кто в нём не живёт."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.listing_ttl_days)
    return l.status == "active" and l.confirmed_at >= cutoff and l.capacity - l.occupied_count > 0


async def _candidate_profile(db, user, kind: str) -> Profile:
    cp_r = await db.execute(select(Profile).where(Profile.user_id == user.id))
    cand = cp_r.scalar_one_or_none()
    if cand is None:
        raise profile_required()
    if kind == "apartment" and cand.budget_max_rub is None:
        raise budget_required()
    return cand


async def _resident_profiles(db, listing_ids: List[uuid.UUID]) -> Dict[uuid.UUID, List[Dict[str, Any]]]:
    result = await db.execute(
        select(Membership.listing_id, Profile.answers).join(Profile, Profile.user_id == Membership.user_id)
        .where(Membership.listing_id.in_(listing_ids)))
    by_listing: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
    for listing_id, answers in result.all():
        by_listing.setdefault(listing_id, []).append(answers)
    return by_listing


async def get_matches(db, user, kind: str, offset: int = 0, limit: int = 20,
                      include_unmatched: bool = False) -> MatchListResponse:
    cand_prof = await _candidate_profile(db, user, kind)

    mem_r = await db.execute(select(Membership.listing_id).where(Membership.user_id == user.id))
    user_listing_ids = {row[0] for row in mem_r.fetchall()}

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.listing_ttl_days)
    listings_r = await db.execute(
        select(Listing).where(Listing.kind == kind, Listing.status == "active", Listing.confirmed_at >= cutoff)
        .options(selectinload(Listing.photos))
    )
    candidates = [l for l in listings_r.scalars().all()
                  if (l.capacity - l.occupied_count) > 0 and l.id not in user_listing_ids]
    if not candidates:
        return MatchListResponse(items=[], total=0, offset=offset, limit=limit, score_version=SCORE_VERSION)

    profiles_by_listing = await _resident_profiles(db, [l.id for l in candidates])

    scored: List[Tuple] = []
    for l in candidates:
        r_profiles = profiles_by_listing.get(l.id, [])
        if not r_profiles:
            continue
        reasons = _reasons(cand_prof, l, r_profiles)
        if reasons and not include_unmatched:
            continue
        compat = _compute_compat(cand_prof.answers, r_profiles, l.occupied_count)
        ratio = len(r_profiles) / l.occupied_count
        item = MatchItem(
            id=l.id, kind=l.kind,
            building=l.building, room_number=l.room_number, district=l.district,
            monthly_cost_per_person_rub=l.monthly_cost_per_person_rub,
            cover_url=photo_url(l.id, l.photos[0].file_name) if l.photos else None,
            free_places=l.capacity - l.occupied_count,
            answered_count=len(r_profiles), occupied_count=l.occupied_count,
            fits=not reasons, reasons=reasons,
            compatibility=compat,
        )
        # Подходящие — первыми; внутри групп — по совместимости.
        scored.append((bool(reasons), -compat.score_raw, -ratio, -l.confirmed_at.timestamp(), str(l.id), item))

    scored.sort(key=lambda s: s[:5])
    total = len(scored)
    page_items = [s[5] for s in scored[offset:offset + limit]]
    return MatchListResponse(items=page_items, total=total, offset=offset, limit=limit, score_version=SCORE_VERSION)


async def _listing_for_viewer(db, user, listing_id: uuid.UUID) -> Tuple[Listing, bool]:
    """Жильё и признак «пользователь в нём живёт». Чужое — только если оно сейчас показывается."""
    r = await db.execute(select(Listing).where(Listing.id == listing_id)
                         .options(selectinload(Listing.contacts), selectinload(Listing.photos)))
    l = r.scalar_one_or_none()
    if l is None:
        raise not_found("Жильё не найдено.")
    mem_r = await db.execute(select(Membership).where(Membership.listing_id == l.id, Membership.user_id == user.id))
    lives_here = mem_r.scalar_one_or_none() is not None
    if not lives_here and not _is_visible(l):
        raise not_found("Жильё недоступно.")
    return l, lives_here


async def get_listing_detail(db, user, listing_id: uuid.UUID) -> dict:
    l, lives_here = await _listing_for_viewer(db, user, listing_id)

    members_r = await db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.listing_id == l.id).order_by(Membership.joined_at, Membership.user_id))
    members = members_r.all()
    p_r = await db.execute(select(Profile).where(Profile.user_id.in_([m.user_id for m, _ in members])))
    pmap = {p.user_id: p.answers for p in p_r.scalars().all()}

    residents = [
        ResidentBrief(display_name=u.display_name, profile_complete=m.user_id in pmap, is_admin=m.is_admin)
        for m, u in members
    ]

    base = {
        "id": l.id, "kind": l.kind,
        "building": l.building, "room_number": l.room_number, "floor": l.floor,
        "capacity": l.capacity, "occupied_count": l.occupied_count,
        "free_places": l.capacity - l.occupied_count,
        "answered_count": len(pmap),
        "is_corner": l.is_corner, "windows_count": l.windows_count,
        "view": l.view, "layout": l.layout,
        "district": l.district, "monthly_cost_per_person_rub": l.monthly_cost_per_person_rub,
        "description": l.description, "status": l.status,
        "photos": [p.model_dump() for p in photos_out(l)],
        "residents": [r.model_dump() for r in residents],
        "confirmed_at": l.confirmed_at.isoformat(),
        "you_live_here": lives_here,
    }

    if lives_here:
        base["compatibility"] = None
        return base

    cand = await _candidate_profile(db, user, l.kind)
    r_profiles = list(pmap.values())
    if not r_profiles:
        raise not_found("Жильё недоступно.")

    reasons = _reasons(cand, l, r_profiles)
    base["fits"] = not reasons
    base["reasons"] = [r.model_dump() for r in reasons]
    base["compatibility"] = _compute_compat(cand.answers, r_profiles, l.occupied_count).model_dump()
    return base


async def get_contact(db, user, listing_id: uuid.UUID) -> ContactListResponse:
    l, lives_here = await _listing_for_viewer(db, user, listing_id)
    if not lives_here:
        await _candidate_profile(db, user, l.kind)
    return ContactListResponse(items=contacts_out(l))
