"""Юнит-тесты формулы совместимости (без базы)."""

from app.services.matching_service import _check_hard, _compute_compat
from tests.conftest import answers


def test_hard_condition_is_checked_in_both_directions():
    non_smoker = answers(smoking={"value": 0, "hard": True, "allowed": [0]})
    smoker = answers(smoking={"value": 1})
    assert _check_hard(non_smoker, smoker) is False  # кандидат не принимает жильца
    assert _check_hard(smoker, non_smoker) is False  # жилец не принимает кандидата
    assert _check_hard(non_smoker, answers()) is True


def test_identical_answers_score_100():
    c = _compute_compat(answers(), [answers()], occupied=1)
    assert c.score == 100
    assert c.warnings == []
    assert {d.label for d in c.dimensions} == {"similar"}


def test_weighting_by_importance_of_both_sides():
    # sleep: полностью разные ответы (similarity 0), вес (10+10)/2 = 10;
    # остальные 8 вопросов совпадают, вес 5 каждый -> 100 * 40 / 50 = 80
    cand = answers(sleep={"value": 0, "importance": 10})
    res = answers(sleep={"value": 4, "importance": 10})
    c = _compute_compat(cand, [res], occupied=1)
    assert c.score == 80
    sleep = next(d for d in c.dimensions if d.key == "sleep")
    assert sleep.similarity == 0 and sleep.weight == 10 and sleep.label == "noticeable_difference"


def test_room_profile_is_average_of_residents():
    # Жильцы ложатся в 0 и 4 -> в среднем 2, как и кандидат
    c = _compute_compat(answers(), [answers(sleep={"value": 0}), answers(sleep={"value": 4})], occupied=2)
    sleep = next(d for d in c.dimensions if d.key == "sleep")
    assert sleep.room_average == 2.0 and sleep.similarity == 1.0
    assert c.score == 100
    # ...но разброс большой, это видно в предупреждениях
    assert [w.model_dump(exclude_none=True) for w in c.warnings] == [{"code": "RESIDENTS_DISAGREE", "key": "sleep"}]


def test_partial_answers_warning():
    c = _compute_compat(answers(), [answers()], occupied=3)
    assert c.warnings[0].model_dump(exclude_none=True) == {"code": "PARTIAL_ANSWERS", "answered": 1, "occupied": 3}


def test_rounding_is_half_up_not_bankers():
    # sleep: разница 3 из 4 (similarity 0.25), вес (6+10)/2 = 8; остальные вес 1:
    # 100 * (8 + 0.25*8) / (8 + 8) = 62.5 -> 63 (round() дал бы 62)
    low = {k: {"importance": 1} for k in ("noise", "cleanliness", "guests", "smoking", "alcohol", "study", "airing", "temperature")}
    cand = answers(sleep={"value": 0, "importance": 6}, **low)
    res = answers(sleep={"value": 3, "importance": 10}, **low)
    c = _compute_compat(cand, [res], occupied=1)
    assert c.score_raw == 62.5
    assert c.score == 63
