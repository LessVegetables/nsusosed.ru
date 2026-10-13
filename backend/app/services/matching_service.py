from __future__ import annotations
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from sqlalchemy import select
from app.config import QUESTIONNAIRE_V1, MATCHING_CONFIG, settings
from app.models.listing import Listing
from app.models.membership import Membership
from app.models.profile import Profile
from app.models.user import User
from app.schemas.matching import MatchItem, MatchListResponse, Compatibility, DimensionDetail, ContactResponse
from app.schemas.listing import ResidentBrief
from app.utils.contact import contact_url
from app.utils.errors import not_found, profile_required, budget_required

QUESTION_KEYS = [q["key"] for q in QUESTIONNAIRE_V1["questions"]]
Q_MAP = {q["key"]: q for q in QUESTIONNAIRE_V1["questions"]}
SCORE_VERSION = MATCHING_CONFIG["score_version"]
THRESHOLDS = MATCHING_CONFIG["explanation_thresholds"]
LABELS = MATCHING_CONFIG["labels"]
DISPERSION_THRESHOLD = MATCHING_CONFIG["dispersion_threshold"]


def _normalize(key: str, value: int) -> float:
    return value / Q_MAP[key]["normalize_divisor"]


def _check_hard(candidate: Dict[str, Any], resident: Dict[str, Any]) -> bool:
    for key in QUESTION_KEYS:
        c = candidate[key]
        r = resident[key]
        if c.get("hard", False) and r["value"] not in c.get("allowed", []):
            return False
        if r.get("hard", False) and c["value"] not in r.get("allowed", []):
            return False
    return True


def _compute_compat(candidate: Dict[str, Any], residents: List[Dict[str, Any]], occupied: int) -> Compatibility:
    n = len(residents)
    dims: List[DimensionDetail] = []
    warnings: List[str] = []
    numerator = 0.0
    denominator = 0.0

    for key in QUESTION_KEYS:
        c_ans = candidate[key]
        c_norm = _normalize(key, c_ans["value"])
        c_imp = c_ans["importance"]
        r_values = [r[key]["value"] for r in residents]
        r_norms = [_normalize(key, v) for v in r_values]
        room_val = sum(r_norms) / n
        room_imp = sum(r[key]["importance"] for r in residents) / n
        weight = (c_imp + room_imp) / 2.0
        similarity = 1.0 - abs(c_norm - room_val)
        numerator += weight * similarity
        denominator += weight
        divisor = Q_MAP[key]["normalize_divisor"]

        if similarity >= THRESHOLDS["similar"]:
            label = LABELS["similar"]
        elif similarity >= THRESHOLDS["minor_difference"]:
            label = LABELS["minor_difference"]
        else:
            label = LABELS["noticeable_difference"]

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

    if n < occupied:
        warnings.append(f"Ответили {n} из {occupied} жильцов. Данные неполные")

    for key in QUESTION_KEYS:
        r_values = [r[key]["value"] for r in residents]
        if key == "smoking":
            if len(set(r_values)) > 1:
                warnings.append("У жильцов разные ответы")
                break
        else:
            if max(r_values) - min(r_values) >= DISPERSION_THRESHOLD:
                warnings.append("У жильцов разные ответы")
                break

    return Compatibility(
        score=score, score_raw=round(score_raw, 6), score_version=SCORE_VERSION,
        warnings=warnings, dimensions=dims,
    )


async def get_matches(db, user, kind: str, offset: int = 0, limit: int = 20) -> MatchListResponse:
    cp_r = await db.execute(select(Profile).where(Profile.user_id == user.id))
    cand_prof = cp_r.scalar_one_or_none()
    if cand_prof is None:
        raise profile_required()
    if kind == "apartment" and cand_prof.budget_max_rub is None:
        raise budget_required()

    mem_r = await db.execute(select(Membership.listing_id).where(Membership.user_id == user.id))
    user_listing_ids = {row[0] for row in mem_r.fetchall()}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.listing_ttl_days)
    listings_r = await db.execute(
        select(Listing).where(Listing.kind == kind, Listing.status == "active", Listing.confirmed_at >= cutoff)
    )
    all_listings = listings_r.scalars().all()
    candidates = [l for l in all_listings if (l.capacity - l.occupied_count) > 0 and l.id not in user_listing_ids]

    if kind == "apartment":
        budget = cand_prof.budget_max_rub
        candidates = [l for l in candidates if l.monthly_cost_per_person_rub is not None and l.monthly_cost_per_person_rub <= budget]

    if not candidates:
        return MatchListResponse(items=[], total=0, offset=offset, limit=limit, score_version=SCORE_VERSION)

    lids = [l.id for l in candidates]
    mem_all_r = await db.execute(select(Membership).where(Membership.listing_id.in_(lids)))
    listing_members: Dict[uuid.UUID, List[uuid.UUID]] = {}
    for m in mem_all_r.scalars().all():
        listing_members.setdefault(m.listing_id, []).append(m.user_id)

    all_member_ids = set()
    for ids in listing_members.values():
        all_member_ids.update(ids)

    profiles_map: Dict[uuid.UUID, Dict[str, Any]] = {}
    if all_member_ids:
        prof_all_r = await db.execute(select(Profile).where(Profile.user_id.in_(list(all_member_ids))))
        for p in prof_all_r.scalars().all():
            profiles_map[p.user_id] = p.answers

    scored: List[Tuple] = []
    for l in candidates:
        r_profiles = [profiles_map[uid] for uid in listing_members.get(l.id, []) if uid in profiles_map]
        if not r_profiles:
            continue
        if not all(_check_hard(cand_prof.answers, rp) for rp in r_profiles):
            continue
        compat = _compute_compat(cand_prof.answers, r_profiles, l.occupied_count)
        ratio = len(r_profiles) / l.occupied_count
        item = MatchItem(
            id=l.id, kind=l.kind,
            building=l.building, room_number=l.room_number, district=l.district,
            free_places=l.capacity - l.occupied_count,
            answered_count=len(r_profiles), occupied_count=l.occupied_count,
            compatibility=compat,
        )
        scored.append((-compat.score_raw, -ratio, -l.confirmed_at.timestamp(), str(l.id), item))

    scored.sort()
    total = len(scored)
    page_items = [s[4] for s in scored[offset:offset + limit]]
    return MatchListResponse(items=page_items, total=total, offset=offset, limit=limit, score_version=SCORE_VERSION)


async def get_listing_detail(db, user, listing_id: uuid.UUID) -> dict:
    r = await db.execute(select(Listing).where(Listing.id == listing_id))
    l = r.scalar_one_or_none()
    if l is None:
        raise not_found("Карточка не найдена.")

    is_author = l.owner_id == user.id
    mem_r = await db.execute(select(Membership).where(Membership.listing_id == l.id, Membership.user_id == user.id))
    is_resident = mem_r.scalar_one_or_none() is not None

    members_r = await db.execute(select(Membership.user_id).where(Membership.listing_id == l.id))
    member_ids = [row[0] for row in members_r.fetchall()]
    umap: Dict = {}
    pmap: Dict = {}
    if member_ids:
        u_r = await db.execute(select(User).where(User.id.in_(member_ids)))
        umap = {u.id: u for u in u_r.scalars().all()}
        p_r = await db.execute(select(Profile).where(Profile.user_id.in_(member_ids)))
        for p in p_r.scalars().all():
            pmap[p.user_id] = p.answers

    residents = [
        ResidentBrief(display_name=umap[uid].display_name if uid in umap else "Пользователь",
                      profile_complete=uid in pmap)
        for uid in member_ids
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
        "residents": [r.model_dump() for r in residents],
        "confirmed_at": l.confirmed_at.isoformat(),
    }

    if is_author or is_resident:
        base["compatibility"] = None
        return base

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.listing_ttl_days)
    if l.status != "active" or l.confirmed_at < cutoff or (l.capacity - l.occupied_count) <= 0:
        raise not_found("Карточка недоступна.")

    cand_r = await db.execute(select(Profile).where(Profile.user_id == user.id))
    cand = cand_r.scalar_one_or_none()
    if cand is None:
        raise profile_required()

    if l.kind == "apartment":
        if cand.budget_max_rub is None:
            raise budget_required()
        if l.monthly_cost_per_person_rub and l.monthly_cost_per_person_rub > cand.budget_max_rub:
            raise not_found("Карточка недоступна.")

    r_profiles = list(pmap.values())
    if not r_profiles:
        raise not_found("Карточка недоступна.")
    for rp in r_profiles:
        if not _check_hard(cand.answers, rp):
            raise not_found("Карточка недоступна.")

    compat = _compute_compat(cand.answers, r_profiles, l.occupied_count)
    base["compatibility"] = compat.model_dump()
    return base


async def get_contact(db, user, listing_id: uuid.UUID) -> ContactResponse:
    r = await db.execute(select(Listing).where(Listing.id == listing_id))
    l = r.scalar_one_or_none()
    if l is None:
        raise not_found("Карточка не найдена.")

    is_author = l.owner_id == user.id
    mem_r = await db.execute(select(Membership).where(Membership.listing_id == l.id, Membership.user_id == user.id))
    is_resident = mem_r.scalar_one_or_none() is not None

    if not is_author and not is_resident:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.listing_ttl_days)
        free = l.capacity - l.occupied_count
        if l.status != "active" or l.confirmed_at < cutoff or free <= 0:
            raise not_found("Карточка недоступна.")

        cand_r = await db.execute(select(Profile).where(Profile.user_id == user.id))
        cand = cand_r.scalar_one_or_none()
        if cand is None:
            raise profile_required()

        if l.kind == "apartment":
            if cand.budget_max_rub is None:
                raise budget_required()
            if l.monthly_cost_per_person_rub and l.monthly_cost_per_person_rub > cand.budget_max_rub:
                raise not_found("Карточка недоступна.")

        members_r = await db.execute(select(Membership.user_id).where(Membership.listing_id == l.id))
        mids = [row[0] for row in members_r.fetchall()]
        if mids:
            p_r = await db.execute(select(Profile).where(Profile.user_id.in_(mids)))
            for p in p_r.scalars().all():
                if not _check_hard(cand.answers, p.answers):
                    raise not_found("Карточка недоступна.")

    return ContactResponse(type=l.contact_type, value=l.contact_value,
                           url=contact_url(l.contact_type, l.contact_value))
