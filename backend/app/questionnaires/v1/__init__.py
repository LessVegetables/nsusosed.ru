"""Questionnaire v1: 20 questions, 5 dimensions. See questions.json and scoring.json.

Answers: {"A1": 2, "E1": [1, 3], ...} — option indices; a list of indices for the one
multi-select question (E1). Under-18s have no E1/E2 at all.

Scoring follows "nsusosed: как считается совместимость":
  1. hard blocks  2. friction per item pair  3. dimension scores  4. overall score.
Hidden answers go through the same math as visible ones; hiding only limits what is shown,
which is why PairScore.public() has the rounded total and coarse badges and nothing else.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

VERSION = 1
_DIR = Path(__file__).resolve().parent
QUESTIONNAIRE: dict = json.loads((_DIR / "questions.json").read_text(encoding="utf-8"))
S: dict = json.loads((_DIR / "scoring.json").read_text(encoding="utf-8"))
QUESTIONS: dict[str, dict] = {q["id"]: q for q in QUESTIONNAIRE["questions"]}
DIMENSIONS = ("sleep", "order", "quiet", "air", "living")

Answers = dict


# ── Which questions apply, and validation ───────────────

def applies(q: dict, answers: Answers, is_adult: bool) -> bool:
    """Is this question asked of this person, given what they answered so far?"""
    if q.get("adult_only") and not is_adult:
        return False
    cond = q.get("show_if")
    if cond:
        chosen = answers.get(cond["question"])
        chosen = chosen if isinstance(chosen, list) else [chosen]
        return any(c in cond["any_of"] for c in chosen)
    return True


def clean(answers: Answers, is_adult: bool) -> tuple[Answers, dict[str, str]]:
    """Validate a (possibly partial) set of answers.

    Returns the answers that apply to this person, plus errors as {question id: reason}.
    Answers to questions that are not asked (E1/E2 under 18, E2 without nicotine) are dropped.
    """
    errors: dict[str, str] = {}
    for qid, value in answers.items():
        q = QUESTIONS.get(qid)
        if q is None:
            errors[qid] = "UNKNOWN_QUESTION"
            continue
        n = len(q["options"])
        if q["type"] == "multi":
            ok = (isinstance(value, list) and value and len(set(value)) == len(value)
                  and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n for v in value))
            if ok and len(value) > 1 and any(v in q.get("exclusive", []) for v in value):
                errors[qid] = "EXCLUSIVE_OPTION"
            elif not ok:
                errors[qid] = "INVALID_CHOICE"
        elif not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value < n):
            errors[qid] = "INVALID_CHOICE"
    if errors:
        return {}, errors
    kept: Answers = {}
    for q in QUESTIONNAIRE["questions"]:  # in order: show_if looks at earlier answers
        if q["id"] in answers and applies(q, kept, is_adult):
            value = answers[q["id"]]
            kept[q["id"]] = sorted(value) if isinstance(value, list) else value
    return kept, {}


def missing_required(answers: Answers, is_adult: bool) -> list[str]:
    return [q["id"] for q in QUESTIONNAIRE["questions"]
            if q["required"] and applies(q, answers, is_adult) and q["id"] not in answers]


def is_complete(answers: Answers, is_adult: Optional[bool]) -> bool:
    return is_adult is not None and not missing_required(answers, is_adult)


def for_scoring(answers: Answers, is_adult: bool) -> Answers:
    """What the scorer may use. Someone who is now marked under 18 has no nicotine answers,
    whatever is stored."""
    return clean(answers, is_adult)[0]


# ── Scoring ─────────────────────────────────────────────

@dataclass(frozen=True)
class PairScore:
    dimensions: dict[str, float]  # 0–100 each; internal, never sent to a browser
    overall: float                # 0–100, unrounded; internal

    def badges(self) -> dict[str, str]:
        cut = S["overall"]["badges"]
        return {name: "match" if score >= cut["match"] else "ok" if score >= cut["ok"] else "discuss"
                for name, score in self.dimensions.items()}

    def public(self) -> dict:
        """All that may leave the server: exact numbers would let someone compare several
        matches and work a hidden answer out."""
        return {"percent": round_score(self.overall), "badges": self.badges()}


def round_score(score: float) -> int:
    step = S["overall"]["round_to"]
    return int(step * round(score / step))


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _weighted(parts: list[tuple[float, Optional[float]]]) -> float:
    """Weighted mean of the frictions that could be computed (None = an optional answer is
    missing on the side that matters, so the item is left out and the rest re-weighted)."""
    present = [(w, f) for w, f in parts if f is not None]
    total = sum(w for w, _ in present)
    return sum(w * f for w, f in present) / total if total else 0.0


def _habit_vs_tolerance(table: list[list[float]], habit_q: str, tolerance_q: str, a: Answers, b: Answers) -> Optional[float]:
    """My habit against your tolerance and yours against mine; the worse direction counts,
    because it only takes one annoyed roommate."""
    frictions = [table[x[habit_q]][y[tolerance_q]] for x, y in ((a, b), (b, a)) if habit_q in x and tolerance_q in y]
    return max(frictions) if frictions else None


def _distance(q: str, a: Answers, b: Answers) -> Optional[float]:
    if q not in a or q not in b:
        return None
    return abs(a[q] - b[q]) / (len(QUESTIONS[q]["options"]) - 1)


def _nicotine(x: Answers) -> list[int]:
    return x.get("E1", [])


def blocked(a: Answers, b: Answers) -> bool:
    """Step 1. Combinations that are never shown as a match, in either direction."""
    hb = S["hard_blocks"]
    for user, other in ((a, b), (b, a)):
        if other.get("E3") != hb["sensitive_e3"]:
            continue
        e1 = _nicotine(user)
        if hb["cigarettes"] in e1 or hb["decline"] in e1:
            return True
        if (any(p in e1 for p in hb["vape_or_sticks"]) and user.get("E2") in hb["dependent_e2"]
                and user["A2"] >= hb["late_a2_from"]):
            return True
    return False


def _sleep(a: Answers, b: Answers) -> float:
    c = S["sleep"]

    def timing(q: str, hours: list[float]) -> float:
        ha, hb = hours[a[q]], hours[b[q]]
        earlier = a if ha <= hb else b
        return _clamp((abs(ha - hb) - c["allowance_by_a3"][earlier["A3"]]) / c["gap_divisor"])

    friction = c["weekday_weight"] * timing("A1", c["a1_hours"]) + c["free_day_weight"] * timing("A2", c["a2_hours"])
    # Late returns and repeated alarms disturb in proportion to how lightly the other one sleeps.
    for q, rate, weight in (("F1", c["f1_rate"], c["f1_weight"]), ("A4", c["a4_rate"], c["a4_weight"])):
        worst = max((rate[x[q]] * c["sensitivity_by_a3"][y["A3"]] for x, y in ((a, b), (b, a)) if q in x), default=0.0)
        friction += weight * worst
    return _clamp(friction)


def _order(a: Answers, b: Answers) -> float:
    c = S["order"]
    return _weighted([(c["weights"]["B3"], _habit_vs_tolerance(c["b3_vs_b2"], "B3", "B2", a, b)),
                      (c["weights"]["B1"], _habit_vs_tolerance(c["b1_vs_b2"], "B1", "B2", a, b))])


def _quiet(a: Answers, b: Answers) -> float:
    c = S["quiet"]
    friction = _weighted([(c["weights"]["C2"], _habit_vs_tolerance(c["c2_vs_a3"], "C2", "A3", a, b)),
                          (c["weights"]["C3"], _habit_vs_tolerance(c["c3_vs_a3"], "C3", "A3", a, b)),
                          (c["weights"]["D1"], _habit_vs_tolerance(c["d1_vs_d2"], "D1", "D2", a, b))])
    # A mismatch only matters on evenings both are in the room.
    return friction * c["exposure_by_c1"][min(a["C1"], b["C1"])]


def _exposure_risk(x: Answers) -> float:
    """How much nicotine smell or vapor a roommate is likely to meet. 0 for non-users and for
    under-18s (who are never asked)."""
    c, hb = S["air"], S["hard_blocks"]
    e1 = _nicotine(x)
    if not e1 or e1 == [0]:
        return 0.0
    if e1 == [hb["decline"]]:
        return c["decline_risk"]
    product = max(c["product_risk"][str(p)] for p in e1)
    night = c["night_awake"] if x["A2"] >= hb["late_a2_from"] else c["night_asleep"]
    risk = product * c["dependence_by_e2"][x["E2"]] * night
    if hb["cigarettes"] in e1:  # smell on clothes, whenever and wherever they smoke
        risk = max(risk, c["cigarette_smell_floor"])
    return risk


def _air(a: Answers, b: Answers) -> float:
    c = S["air"]
    nicotine = max(_exposure_risk(x) * c["sensitivity_by_e3"][y["E3"]] for x, y in ((a, b), (b, a)))
    # Two users of the same product: exposure stays among people who accept it.
    if set(_nicotine(a)) & set(_nicotine(b)) & {int(p) for p in c["product_risk"]}:
        nicotine *= c["shared_product_factor"]
    return _weighted([(c["weights"]["nicotine"], nicotine), (c["weights"]["G1"], _distance("G1", a, b))])


def _living(a: Answers, b: Answers) -> float:
    c = S["living"]
    h1 = c["h1_pairs"][a["H1"]][b["H1"]] if "H1" in a and "H1" in b else None
    return _weighted([(c["weights"]["G2"], _distance("G2", a, b)), (c["weights"]["G3"], _distance("G3", a, b)),
                      (c["weights"]["H1"], h1)])


def overall(dimensions: dict[str, float]) -> float:
    """Step 4. The min term keeps a pair that is perfect on four dimensions and terrible on
    one from scoring around 80."""
    c = S["overall"]
    mean = sum(c["weights"][name] * score for name, score in dimensions.items())
    return c["mean_share"] * mean + c["min_share"] * min(dimensions.values())


def score_pair(a: Answers, b: Answers) -> Optional[PairScore]:
    """Compatibility of two people who both completed this version (answers already passed
    through for_scoring). None = hard block: the pair is not shown at all, not even as 0%."""
    if blocked(a, b):
        return None
    frictions = {"sleep": _sleep(a, b), "order": _order(a, b), "quiet": _quiet(a, b),
                 "air": _air(a, b), "living": _living(a, b)}
    dimensions = {name: 100 * (1 - f) for name, f in frictions.items()}
    return PairScore(dimensions=dimensions, overall=overall(dimensions))


def score_room(pairs: list[Optional[PairScore]]) -> Optional[float]:
    """A room from the seeker's scores with each resident: mostly the average, pulled down by
    the worst pairing. A hard block with any resident hides the room."""
    if not pairs or any(p is None for p in pairs):
        return None
    scores = [p.overall for p in pairs]
    c = S["room"]
    return c["mean_share"] * sum(scores) / len(scores) + c["min_share"] * min(scores)
