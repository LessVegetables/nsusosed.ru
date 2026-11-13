"""Questionnaire v1: validation and the compatibility math (no database needed)."""

import pytest
from app.questionnaires import v1
from app.questionnaires.v1 import PairScore, blocked, clean, is_complete, missing_required, overall, score_pair, score_room

# A calm non-smoker with every required answer. Tests change only what they are about.
BASE = {"A1": 1, "A2": 1, "A3": 1, "B1": 0, "B2": 1, "B3": 0, "C1": 1, "C2": 0, "D1": 0, "D2": 1,
        "E1": [0], "E3": 2, "F1": 0, "G1": 1, "G2": 1}


def person(**changes) -> dict:
    return {**BASE, **changes}


# ── What gets asked, and validation ─────────────────────

def test_the_questionnaire_matches_the_spec_counts():
    qs = v1.QUESTIONNAIRE["questions"]
    assert len(qs) == 20
    assert [q["id"] for q in qs if not q["required"]] == ["A4", "C3", "G3", "H1"]
    assert sorted(q["id"] for q in qs if q["hidden"]) == ["B1", "B3", "C3", "E1", "E2", "F1", "H1"]
    assert all({"ru", "en", "zh"} <= q["text"].keys() and all({"ru", "en", "zh"} <= o.keys() for o in q["options"]) for q in qs)


def test_non_user_answers_15_and_a_user_16():
    assert is_complete(BASE, True)
    vaper = person(E1=[1])
    assert missing_required(vaper, True) == ["E2"]
    assert is_complete(person(E1=[1], E2=3), True)


def test_declining_the_nicotine_question_does_not_ask_about_dependence():
    assert is_complete(person(E1=[6]), True)
    assert clean(person(E1=[6], E2=0), True)[0].get("E2") is None


def test_under_18_is_never_asked_about_nicotine_and_stored_answers_are_ignored():
    minor = {k: v for k, v in BASE.items() if k != "E1"}
    assert is_complete(minor, False)
    kept, errors = clean(person(E1=[2], E2=0), False)
    assert not errors and "E1" not in kept and "E2" not in kept
    # Turning 18 later: the nicotine question is now required.
    assert missing_required(minor, True) == ["E1"]
    assert not is_complete(BASE, None)  # the 18+ question itself hasn't been answered


@pytest.mark.parametrize("bad, reason", [
    ({"A1": 5}, "INVALID_CHOICE"), ({"A1": "1"}, "INVALID_CHOICE"), ({"A1": True}, "INVALID_CHOICE"),
    ({"E1": 1}, "INVALID_CHOICE"), ({"E1": []}, "INVALID_CHOICE"), ({"E1": [1, 1]}, "INVALID_CHOICE"),
    ({"E1": [0, 1]}, "EXCLUSIVE_OPTION"), ({"E1": [6, 2]}, "EXCLUSIVE_OPTION"), ({"Z9": 0}, "UNKNOWN_QUESTION"),
])
def test_invalid_answers(bad, reason):
    assert clean(bad, True)[1] == {next(iter(bad)): reason}


# ── Step 1: hard blocks ─────────────────────────────────

SENSITIVE = person(E3=0)


@pytest.mark.parametrize("nicotine, is_blocked", [
    (dict(E1=[2], E2=4), True),                  # any cigarette use, however rare
    (dict(E1=[6]), True),                        # declined to answer
    (dict(E1=[1], E2=1, A2=2), True),            # vape + within 30 min + awake past 01:00
    (dict(E1=[3], E2=0, A2=4), True),            # sticks, same
    (dict(E1=[1], E2=1, A2=1), False),           # dependent but asleep before 01:00
    (dict(E1=[1], E2=2, A2=4), False),           # up late but not dependent
    (dict(E1=[4], E2=0, A2=4), False),           # snus: no aerosol
    (dict(E1=[0]), False),
])
def test_hard_blocks_against_someone_smells_make_unwell(nicotine, is_blocked):
    user = person(**nicotine)
    assert blocked(user, SENSITIVE) is is_blocked
    assert blocked(SENSITIVE, user) is is_blocked          # either direction
    assert (score_pair(user, SENSITIVE) is None) is is_blocked
    assert not blocked(user, person(E3=1))                 # merely "unpleasant" is graded, not blocked


def test_a_minor_never_triggers_a_block_but_is_protected_by_one():
    minor = {k: v for k, v in person(E3=0).items() if k != "E1"}
    assert score_pair(minor, person(E3=0)) is not None     # no nicotine data ≠ "declined"
    assert score_pair(minor, person(E1=[2], E2=3)) is None  # an adult smoker next to a sensitive minor


# ── Steps 2–3: dimensions ───────────────────────────────

def test_the_worked_example_from_the_spec():
    # Аня: 23:30 / 00:30, needs darkness, everything tidy. Катя: 01:30 / 02:30, a couple of things out.
    anya = person(A1=1, A2=1, A3=2, B3=0, B2=1)
    katya = person(A1=3, A2=3, A3=1, B3=1, B2=1)
    result = score_pair(anya, katya)
    assert round(result.dimensions["sleep"]) == 67          # gap 2 h, allowance 1 h → (2 − 1) / 3
    assert result.dimensions["order"] == 100
    assert result.badges()["sleep"] == "discuss" and result.badges()["order"] == "match"
    # "Weighted mean ≈ 87, lowest dimension 67, so ≈ 81, shown as 80%."
    example = PairScore({"sleep": 67, "order": 100, "quiet": 90, "air": 95, "living": 85}, 0)
    assert v1.round_score(overall(example.dimensions)) == 80


def test_identical_people_score_100_and_the_score_is_symmetric():
    assert score_pair(BASE, BASE).overall == 100
    a, b = person(A1=0, B3=3, C2=3, D1=3, G1=0, F1=3), person(A1=4, A3=3, B2=0, D2=0, G1=3, C1=2)
    assert score_pair(a, b).overall == pytest.approx(score_pair(b, a).overall)
    assert score_pair(a, b).overall < 60


def test_sleep_allowance_comes_from_the_earlier_sleeper():
    early_light, early_deep, late = person(A1=0, A2=0, A3=3), person(A1=0, A2=0, A3=0), person(A1=3, A2=3)
    assert score_pair(early_light, late).dimensions["sleep"] < score_pair(early_deep, late).dimensions["sleep"]
    # The late one being a light sleeper changes nothing about the timing clash.
    assert score_pair(early_deep, late).dimensions["sleep"] == score_pair(early_deep, person(A1=3, A2=3, A3=3)).dimensions["sleep"]


def test_late_returns_and_alarms_cost_more_next_to_a_light_sleeper():
    owl = person(F1=3, A4=2)
    assert score_pair(owl, person(A3=0)).dimensions["sleep"] == 100
    assert score_pair(owl, person(A3=3)).dimensions["sleep"] == pytest.approx(100 * (1 - 0.25 - 0.15))


def test_order_takes_the_worse_direction():
    messy, strict = person(B3=3, B2=3), person(B3=0, B2=0)
    assert score_pair(messy, strict).dimensions["order"] == pytest.approx(100 * (1 - 0.6 * 1.0))
    assert score_pair(messy, person(B3=0, B2=3)).dimensions["order"] == 100
    assert score_pair(person(B1=3), strict).dimensions["order"] == pytest.approx(100 * (1 - 0.4 * 1.0))
    assert score_pair(person(B1=4), strict).dimensions["order"] == 100  # hardly eats in the room


def test_noise_and_guests_only_matter_when_both_are_home():
    loud, light = person(C2=3, D1=3, C1=2), person(A3=3, D2=0, C1=2)
    full = 100 - score_pair(loud, light).dimensions["quiet"]
    rarely_home = 100 - score_pair(loud, {**light, "C1": 0}).dimensions["quiet"]
    assert full == pytest.approx(100.0) and rarely_home == pytest.approx(0.4 * full)


def test_air_is_graded_and_shared_products_are_compatible():
    vaper = person(E1=[1], E2=3, A2=1)
    bothered = score_pair(vaper, person(E3=1)).dimensions["air"]
    fine = score_pair(vaper, person(E3=3)).dimensions["air"]
    assert bothered < fine < 100
    assert score_pair(person(E1=[4], E2=0), person(E3=1)).dimensions["air"] > bothered   # snus barely counts
    other_vaper = person(E1=[1], E2=3, E3=1)
    assert score_pair(vaper, other_vaper).dimensions["air"] > bothered
    assert score_pair(BASE, person(G1=3)).dimensions["air"] == pytest.approx(100 * (1 - 0.3 * 2 / 3))


def test_skipped_optional_answers_drop_out_instead_of_counting_as_agreement_or_conflict():
    a, b = person(G2=0), person(G2=3)
    assert score_pair(a, b).dimensions["living"] == 0                        # only G2 answered: full distance
    with_h1 = score_pair({**a, "H1": 0}, {**b, "H1": 0}).dimensions["living"]
    assert with_h1 == pytest.approx(100 * (1 - 0.4 / 0.7))                    # H1 agrees and now shares the weight
    assert score_pair({**a, "H1": 3}, b).dimensions["living"] == 0            # one-sided H1 can't be compared
    # Same G2, so H1 alone decides: silent × same-day is the worst pair, two silent ones nearly as bad.
    assert score_pair(person(H1=3), person(H1=0)).dimensions["living"] == pytest.approx(100 * (1 - 0.3 * 1.0 / 0.7))
    assert score_pair(person(H1=3), person(H1=3)).dimensions["living"] == pytest.approx(100 * (1 - 0.3 * 0.9 / 0.7))


# ── Step 4 and what leaves the server ───────────────────

def test_one_terrible_dimension_drags_the_total_down():
    dims = {"sleep": 0, "order": 100, "quiet": 100, "air": 100, "living": 100}
    assert overall(dims) == pytest.approx(0.7 * 72 + 0.3 * 0)


def test_public_result_has_no_exact_dimension_numbers():
    public = score_pair(person(A1=3, A2=3), person(A3=2)).public()
    assert set(public) == {"percent", "badges"} and public["percent"] % 5 == 0
    assert set(public["badges"]) == set(v1.DIMENSIONS) and set(public["badges"].values()) <= {"match", "ok", "discuss"}


def test_room_score_blends_the_average_with_the_worst_resident():
    seeker = person()
    good, bad = score_pair(seeker, person()), score_pair(seeker, person(A1=4, A2=4, B3=3, B2=0))
    assert score_room([good, good]) == 100
    assert score_room([good, bad]) == pytest.approx(0.7 * (100 + bad.overall) / 2 + 0.3 * bad.overall)
    assert score_room([good, None]) is None and score_room([]) is None
