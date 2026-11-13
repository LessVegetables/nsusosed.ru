"""Saving and reading the questionnaire (needs Postgres)."""

from sqlalchemy import text
from tests.test_scoring import BASE

ORIGIN = {"Origin": "https://testserver"}


async def save(c, answers, version=1):
    return await c.put("/api/questionnaire", json={"version": version, "answers": answers}, headers=ORIGIN)


async def test_the_18_question_comes_first(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    q = (await c.get("/api/questionnaire")).json()
    assert q["version"] == 1 and len(q["questions"]) == 20 and q["answers"] == {} and q["complete"] is False
    r = await save(c, {"A1": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ABOUT_REQUIRED"


async def test_partial_saves_add_up_to_a_complete_questionnaire(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    await c.put("/api/me", json={"is_adult": True}, headers=ORIGIN)

    half = dict(list(BASE.items())[:8])
    r = await save(c, half)
    assert r.status_code == 200 and r.json()["complete"] is False
    assert r.json()["missing"] == [k for k in BASE if k not in half]
    assert (await c.get("/api/me")).json()["questionnaire_complete"] is False

    r = await save(c, {k: v for k, v in BASE.items() if k not in half})
    assert r.json()["complete"] is True and r.json()["missing"] == []
    assert (await c.get("/api/me")).json()["questionnaire_complete"] is True

    # Optional answers later, and changing an answer, keep it complete.
    r = await save(c, {"H1": 3, "A1": 4})
    assert r.json()["answers"] == BASE | {"H1": 3, "A1": 4}

    # Starting to use nicotine reopens it: the dependence question is now required.
    r = await save(c, {"E1": [3, 1]})
    assert r.json()["complete"] is False and r.json()["missing"] == ["E2"] and r.json()["answers"]["E1"] == [1, 3]
    # Back to "don't use": the dependence answer is dropped.
    await save(c, {"E2": 0})
    assert "E2" not in (await save(c, {"E1": [0]})).json()["answers"]


async def test_bad_answers_and_an_old_version_are_refused(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    await c.put("/api/me", json={"is_adult": True}, headers=ORIGIN)
    r = await save(c, {"A1": 9, "E1": [0, 2]})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"answers.A1": "INVALID_CHOICE", "answers.E1": "EXCLUSIVE_OPTION"}
    assert (await c.get("/api/questionnaire")).json()["answers"] == {}
    r = await save(c, BASE, version=2)
    assert r.status_code == 409 and r.json()["error"]["code"] == "QUESTIONNAIRE_OUTDATED"


async def test_under_18_never_stores_nicotine_answers(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    await c.put("/api/me", json={"is_adult": False}, headers=ORIGIN)
    r = await save(c, BASE | {"E1": [2], "E2": 0})
    assert r.json()["complete"] is True and "E1" not in r.json()["answers"] and "E2" not in r.json()["answers"]
    # Marked as 18+ later: one more required question appears.
    await c.put("/api/me", json={"is_adult": True}, headers=ORIGIN)
    q = (await c.get("/api/questionnaire")).json()
    assert q["complete"] is False and q["missing"] == ["E1"]


async def test_answers_to_an_older_version_do_not_count(db, make_client, login):
    c = make_client()
    auth = await login(c, "s@g.nsu.ru")
    assert auth["questionnaire_complete"] is False and auth["intent"] is None
    await c.put("/api/me", json={"is_adult": True}, headers=ORIGIN)
    await save(c, BASE)
    async with db.begin() as conn:
        await conn.execute(text("UPDATE questionnaire_responses SET version = 0"))
    q = (await c.get("/api/questionnaire")).json()
    assert q["answers"] == {} and q["complete"] is False
    assert (await save(c, BASE)).json()["complete"] is True
