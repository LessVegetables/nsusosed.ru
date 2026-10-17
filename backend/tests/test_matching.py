"""Юнит-тесты формулы совместимости (без базы)."""

from app.services.matching_service import _check_hard, _compute_compat, _hard_conflicts
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
    # остальные 9 вопросов совпадают, вес 5 каждый -> 100 * 45 / 55 = 81.8 -> 82
    cand = answers(sleep={"value": 0, "importance": 10})
    res = answers(sleep={"value": 4, "importance": 10})
    c = _compute_compat(cand, [res], occupied=1)
    assert c.score == 82
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
    # sleep: разница 3 из 4 (similarity 0.25), вес (8+10)/2 = 9; остальные 9 вопросов вес 1:
    # 100 * (9 + 0.25*9) / (9 + 9) = 62.5 -> 63 (round() дал бы 62)
    low = {k: {"importance": 1} for k in ("wake", "noise", "cleanliness", "guests", "smoking", "alcohol", "study", "airing", "temperature")}
    cand = answers(sleep={"value": 0, "importance": 8}, **low)
    res = answers(sleep={"value": 3, "importance": 10}, **low)
    c = _compute_compat(cand, [res], occupied=1)
    assert c.score_raw == 62.5
    assert c.score == 63


def test_hard_conflicts_name_the_question_and_whose_condition():
    non_smoker = answers(smoking={"value": 0, "hard": True, "allowed": [0]})
    smoker = answers(smoking={"value": 1})
    assert _hard_conflicts(non_smoker, smoker) == [("smoking", "yours")]
    assert _hard_conflicts(smoker, non_smoker) == [("smoking", "theirs")]


def test_question_missing_on_one_side_is_skipped():
    # Анкета первой версии: вопроса wake нет. Жёсткое условие по нему не срабатывает,
    # а в оценке участвуют только общие вопросы.
    old = {k: v for k, v in answers().items() if k != "wake"}
    strict = answers(wake={"value": 0, "hard": True, "allowed": [0]})
    assert _check_hard(strict, old) is True
    c = _compute_compat(answers(wake={"value": 4}), [old], occupied=1)
    assert c.score == 100
    assert "wake" not in {d.key for d in c.dimensions}
