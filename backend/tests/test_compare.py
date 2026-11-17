"""Comparing with friends by link (needs Postgres)."""

from app.questionnaires import v1
from tests.test_feed import person
from tests.test_homes import ORIGIN
from tests.test_scoring import BASE


async def open_link(c) -> dict:
    r = await c.post("/api/compare", headers=ORIGIN)
    assert r.status_code == 200, r.text
    return r.json()


async def join(c, code):
    return await c.post("/api/compare/join", json={"code": code}, headers=ORIGIN)


async def groups(c) -> list[dict]:
    r = await c.get("/api/compare")
    assert r.status_code == 200, r.text
    return r.json()


async def test_a_link_before_the_questionnaire_then_progress_then_the_result(make_client, login):
    # Shared from the top of the questionnaire: neither has answered anything yet.
    me = await person(make_client, login, "a@g.nsu.ru", "Даня", answers=None)
    wife = await person(make_client, login, "b@g.nsu.ru", "Маша", answers=None)
    link = await open_link(me)
    assert link["url"] == f"https://testserver/compare#code={link['code']}" and link["created_by_you"]
    assert (await open_link(me))["code"] == link["code"]            # asked again: the same link

    r = await join(wife, link["url"])
    assert r.status_code == 200, r.text
    assert (await join(wife, link["code"].lower())).status_code == 200   # opening it twice is harmless

    # Halfway through: counts only, and no score for anyone yet.
    half = {k: BASE[k] for k in list(BASE)[:5]}
    await wife.put("/api/questionnaire", json={"version": 1, "answers": half}, headers=ORIGIN)
    [g] = await groups(me)
    masha = next(m for m in g["members"] if not m["is_you"])
    assert (masha["first_name"], masha["complete"], masha["answered"]) == ("Маша", False, 5)
    assert masha["total"] == len(v1.missing_required({}, True)) and masha["compatibility"] is None
    assert "answers" not in str(g) and g["compatibility"] is None

    # One finished: still nothing to show either of them.
    await me.put("/api/questionnaire", json={"version": 1, "answers": BASE}, headers=ORIGIN)
    [g] = await groups(me)
    assert [m["compatibility"] for m in g["members"]] == [None, None]

    # Both finished: each sees the other's score, rounded, with badges.
    await wife.put("/api/questionnaire", json={"version": 1, "answers": BASE | {"A1": 4}}, headers=ORIGIN)
    for c, other in ((me, "Маша"), (wife, "Даня")):
        [g] = await groups(c)
        [them] = [m for m in g["members"] if not m["is_you"]]
        assert them["first_name"] == other and them["complete"]
        assert them["compatibility"]["percent"] % 5 == 0 and set(them["compatibility"]["badges"]) == set(v1.DIMENSIONS)
        assert g["compatibility"] is None                    # one other person: their own result is the result
    # The link is in use now: asking for a link gives a fresh one.
    assert (await open_link(me))["code"] != link["code"]


async def test_a_hard_block_still_gets_a_result_between_friends(make_client, login):
    sensitive = await person(make_client, login, "s@g.nsu.ru", answers=BASE | {"E3": 0})
    smoker = await person(make_client, login, "h@g.nsu.ru", answers=BASE | {"E1": [2], "E2": 3})
    await join(smoker, (await open_link(sensitive))["code"])
    [g] = await groups(sensitive)
    [them] = [m for m in g["members"] if not m["is_you"]]
    assert them["compatibility"] is not None and them["compatibility"]["badges"]["air"] == "discuss"


async def test_three_people_get_an_overall_score(make_client, login):
    a, b, c = [await person(make_client, login, f"{n}@g.nsu.ru", n) for n in ("a", "b", "c")]
    code = (await open_link(a))["code"]
    for other in (b, c):
        assert (await join(other, code)).status_code == 200
    [g] = await groups(a)
    assert len(g["members"]) == 3 and g["compatibility"]["percent"] % 5 == 0


async def test_limits_bad_codes_and_leaving(make_client, login):
    owner = await person(make_client, login, "o@g.nsu.ru")
    code = (await open_link(owner))["code"]
    assert (await join(owner, "NOPE2345")).json()["error"]["code"] == "COMPARE_INVALID"
    for i in range(5):
        assert (await join(await person(make_client, login, f"p{i}@g.nsu.ru", answers=None), code)).status_code == 200
    late = await person(make_client, login, "late@g.nsu.ru", answers=None)
    r = await join(late, code)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMPARE_FULL"

    [g] = await groups(owner)
    assert (await owner.delete(f"/api/compare/{g['id']}/membership", headers=ORIGIN)).status_code == 204
    assert await groups(owner) == []
    assert (await owner.delete(f"/api/compare/{g['id']}/membership", headers=ORIGIN)).status_code == 404
    assert (await join(late, code)).status_code == 200      # there is room again


async def test_compare_is_an_intent(make_client, login):
    c = await person(make_client, login, "i@g.nsu.ru", answers=None)
    r = await c.put("/api/me", json={"intent": "compare"}, headers=ORIGIN)
    assert r.status_code == 200 and r.json()["intent"] == "compare"


async def test_the_link_needs_a_login_and_the_origin(make_client, login):
    assert (await make_client().get("/api/compare")).status_code == 401
    c = await person(make_client, login, "x@g.nsu.ru", answers=None)
    assert (await c.post("/api/compare", headers={"Origin": "https://evil.example"})).status_code == 403
