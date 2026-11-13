"""The seeker's side: feed, room page, contacts (needs Postgres)."""

from tests.test_homes import ORIGIN, apartment, dorm
from tests.test_scoring import BASE


async def person(make_client, login, email, name="Иван", *, answers=BASE, adult=True, gender="f", faculty="mmf", contact=None):
    c = make_client()
    await login(c, email, first_name=name)
    await c.put("/api/me", json={"is_adult": adult, "gender": gender, "faculty": faculty}, headers=ORIGIN)
    if answers is not None:
        r = await c.put("/api/questionnaire", json={"version": 1, "answers": answers}, headers=ORIGIN)
        assert r.status_code == 200, r.text
    if contact:
        r = await c.put("/api/me/contacts", json={"contacts": [{"type": "telegram", "value": contact}]}, headers=ORIGIN)
        assert r.status_code == 200, r.text
    return c


async def listed(c, body) -> dict:
    r = await c.post("/api/homes", json=body, headers=ORIGIN)
    assert r.status_code == 201, r.text
    return r.json()


async def feed(c, kind="dorm", **params) -> dict:
    r = await c.get("/api/feed", params={"kind": kind, **params})
    assert r.status_code == 200, r.text
    return r.json()


def room(emoji, **changes) -> list[dict]:
    return [{"gender": "f", "capacity": 2, "free_places": 1, "emoji": emoji} | changes]


async def test_feed_needs_a_questionnaire_and_shows_reachable_rooms_with_a_free_place(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru")
    no_quiz = await person(make_client, login, "n@g.nsu.ru", answers=None)
    r = await no_quiz.get("/api/feed", params={"kind": "dorm"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "QUESTIONNAIRE_REQUIRED"

    host = await person(make_client, login, "h@g.nsu.ru", "Катя")
    home = await listed(host, dorm())
    assert (await feed(seeker))["items"] == []                       # no way to reach the host yet
    await host.put("/api/me/contacts", json={"contacts": [{"type": "telegram", "value": "@katya_nsu"}]}, headers=ORIGIN)

    items = (await feed(seeker))["items"]
    assert len(items) == 1
    item = items[0]
    assert (item["building"], item["emoji"], item["free_places"], item["residents"]) == ("6", "🐶🍕🚀", 1, 1)
    assert item["compatibility"] == {"percent": 100, "badges": dict.fromkeys(("sleep", "order", "quiet", "air", "living"), "match")}
    assert "100б" not in str(items) and "room_label" not in str(items)
    assert (await feed(host))["items"] == []                         # your own home isn't in your feed
    assert (await feed(seeker, "apartment"))["items"] == []

    full = dorm(room_label=None, rooms=[home["rooms"][0] | {"free_places": 0}])
    await host.put(f"/api/homes/{home['id']}", json=full, headers=ORIGIN)
    assert (await feed(seeker))["items"] == []


async def test_feed_is_sorted_by_compatibility_and_never_shows_exact_numbers(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru")
    night_owl = BASE | {"A1": 4, "A2": 4, "F1": 3, "C2": 3}
    await listed(await person(make_client, login, "a@g.nsu.ru", answers=night_owl, contact="@owl_nsu"), dorm(room_label="200", rooms=room("🦉🌙⭐")))
    await listed(await person(make_client, login, "b@g.nsu.ru", contact="@twin_nsu"), dorm(room_label="201", rooms=room("🐶🍕🚀")))
    await listed(await person(make_client, login, "c@g.nsu.ru", answers=None, contact="@new_nsu"), dorm(room_label="202", rooms=room("🍎🍐🍊")))

    items = (await feed(seeker))["items"]
    assert [i["emoji"] for i in items] == ["🐶🍕🚀", "🦉🌙⭐", "🍎🍐🍊"]     # best first; no data last
    owl = items[1]["compatibility"]
    assert owl["percent"] % 5 == 0 and owl["percent"] < 100 and owl["badges"]["sleep"] == "discuss"
    assert items[2]["compatibility"] is None
    assert set(owl) == {"percent", "badges"}


async def test_a_hard_block_hides_the_room_everywhere(make_client, login):
    sensitive = await person(make_client, login, "s@g.nsu.ru", answers=BASE | {"E3": 0})
    smoker = await person(make_client, login, "h@g.nsu.ru", answers=BASE | {"E1": [2], "E2": 3}, contact="@smoker_nsu")
    home = await listed(smoker, dorm())
    room_id = home["rooms"][0]["id"]

    assert (await feed(sensitive))["items"] == []
    # Not found, exactly like a room that doesn't exist: a 0% or a "blocked" would reveal the answer.
    r = await sensitive.get(f"/api/rooms/{room_id}")
    missing = await sensitive.get("/api/rooms/00000000-0000-0000-0000-000000000000")
    assert r.status_code == missing.status_code == 404 and r.json()["error"]["code"] == missing.json()["error"]["code"]
    assert (await sensitive.post(f"/api/rooms/{room_id}/contacts", headers=ORIGIN)).status_code == 404

    # One blocked resident hides the whole room, even if the other one is a perfect match.
    mate = await person(make_client, login, "m@g.nsu.ru")
    code = (await smoker.post(f"/api/homes/{home['id']}/invites", json={}, headers=ORIGIN)).json()["code"]
    await mate.post("/api/invites/join", json={"code": code}, headers=ORIGIN)
    assert (await feed(sensitive))["items"] == []
    # Someone who isn't sensitive sees it.
    assert len((await feed(await person(make_client, login, "x@g.nsu.ru")))["items"]) == 1


async def test_dorm_feed_is_limited_to_the_faculty_and_gender_until_asked(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru", gender="f", faculty="mmf")
    await listed(await person(make_client, login, "a@g.nsu.ru", contact="@a_nsu"), dorm(rooms=room("🐶🍕🚀")))                      # dorm 6: ММФ
    await listed(await person(make_client, login, "b@g.nsu.ru", contact="@b_nsu"), dorm(building="4", rooms=room("🍎🍐🍊")))        # dorm 4: ЭФ
    await listed(await person(make_client, login, "c@g.nsu.ru", contact="@c_nsu"), dorm(building="7", rooms=room("🦊🌵🎸")))        # dorm 7: no list
    await listed(await person(make_client, login, "d@g.nsu.ru", contact="@d_nsu"), dorm(room_label="300", rooms=room("🐙🍋🎲", gender="m")))

    f = await feed(seeker)
    assert sorted(i["emoji"] for i in f["items"]) == sorted(["🐶🍕🚀", "🦊🌵🎸"])
    assert (f["hidden_by_faculty"], f["hidden_by_gender"]) == (1, 1)

    f = await feed(seeker, whole_campus="true")
    assert len(f["items"]) == 3 and f["hidden_by_faculty"] == 0
    assert [i["outside_faculty"] for i in f["items"] if i["building"] == "4"] == [True]

    f = await feed(seeker, any_gender="true")
    assert "🐙🍋🎲" in [i["emoji"] for i in f["items"]] and f["hidden_by_gender"] == 0


async def test_apartment_rooms_are_separate_listings_scored_against_the_whole_flat(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru", gender="m")
    host = await person(make_client, login, "h@g.nsu.ru", contact="@flat_nsu")
    await listed(host, apartment())
    f = await feed(seeker, "apartment")
    # "Большая" is for anyone; "Маленькая" is for a woman.
    assert [(i["room_name"], i["rent_rub"]) for i in f["items"]] == [("Большая", 14000)] and f["hidden_by_gender"] == 1
    f = await feed(seeker, "apartment", any_gender="true")
    assert len(f["items"]) == 2 and {i["compatibility"]["percent"] for i in f["items"]} == {100}
    assert all(i["district"] == "Верхняя зона" and i["building"] is None for i in f["items"])


async def test_room_page_shows_residents_visible_answers_only_and_the_map(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru")
    host = await person(make_client, login, "h@g.nsu.ru", "Катя", answers=BASE | {"A1": 3, "B3": 2, "H1": 3}, contact="@katya_nsu")
    await host.put("/api/me", json={"bio": "Люблю тишину"}, headers=ORIGIN)
    home = await listed(host, apartment())
    big, small = [r["id"] for r in home["rooms"]]

    r = await seeker.get(f"/api/rooms/{small}")
    assert r.status_code == 200, r.text
    page = r.json()
    assert (page["lat"], page["lon"], page["radius_m"], page["district"]) == (54.84512, 83.09876, 420, "Верхняя зона")
    assert (page["room_name"], page["rent_rub"], page["utilities_rub"], page["internet_mode"]) == ("Маленькая", 11000, 2500, "included")
    assert [(o["room_name"], o["rent_rub"]) for o in page["other_rooms"]] == [("Большая", 14000)]
    katya = page["residents"][0]
    assert (katya["first_name"], katya["bio"], katya["in_this_room"]) == ("Катя", "Люблю тишину", False)
    # Visible answers are there; the hidden ones (B1, B3, E1, F1, H1…) are not.
    assert katya["answers"]["A1"] == 3 and not {"B1", "B3", "C3", "E1", "E2", "F1", "H1"} & katya["answers"].keys()
    assert not {"B1", "B3", "E1", "F1"} & page["my_answers"].keys() and page["my_answers"]["A1"] == 1
    assert katya["compatibility"]["percent"] == page["compatibility"]["percent"] < 100
    assert (page["is_mine"], page["can_get_contacts"]) == (False, True)

    mine = (await host.get(f"/api/rooms/{big}")).json()
    assert (mine["is_mine"], mine["can_get_contacts"], mine["compatibility"]) == (True, False, None)

    dorm_home = await listed(await person(make_client, login, "d@g.nsu.ru", contact="@d_nsu"), dorm())
    page = (await seeker.get(f"/api/rooms/{dorm_home['rooms'][0]['id']}")).json()
    assert page["radius_m"] == 0 and page["lat"] is not None and page["building"] == "6"
    assert "100б" not in str(page) and "room_label" not in str(page)


async def test_contacts_are_a_separate_request_that_needs_a_questionnaire(make_client, login):
    seeker = await person(make_client, login, "s@g.nsu.ru")
    no_quiz = await person(make_client, login, "n@g.nsu.ru", answers=None)
    host = await person(make_client, login, "h@g.nsu.ru", "Катя", contact="https://t.me/katya_nsu")
    room_id = (await listed(host, dorm()))["rooms"][0]["id"]

    assert "katya_nsu" not in (await seeker.get(f"/api/rooms/{room_id}")).text
    assert "katya_nsu" not in str(await feed(seeker))
    r = await seeker.post(f"/api/rooms/{room_id}/contacts", headers=ORIGIN)
    assert r.json() == {"hosts": [{"first_name": "Катя", "contacts": [
        {"type": "telegram", "value": "katya_nsu", "url": "https://t.me/katya_nsu"}]}]}

    # Without a questionnaire you can look at the room (the "already listed" link leads here) but not get contacts.
    page = (await no_quiz.get(f"/api/rooms/{room_id}")).json()
    assert (page["compatibility"], page["can_get_contacts"]) == (None, False)
    r = await no_quiz.post(f"/api/rooms/{room_id}/contacts", headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "QUESTIONNAIRE_REQUIRED"
    assert (await make_client().post(f"/api/rooms/{room_id}/contacts", headers=ORIGIN)).status_code == 401
