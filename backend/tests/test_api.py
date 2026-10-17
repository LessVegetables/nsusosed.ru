"""Сквозные проверки API (нужен Postgres)."""

import uuid
import pytest
from fastapi.routing import APIRoute
from app.main import app
from tests.conftest import answers

DORM = {"kind": "dorm", "capacity": 3, "occupied_count": 2, "building": "7", "room_number": 101, "floor": 1,
        "contacts": [{"type": "telegram", "value": "@owner_tg"}]}


def update_body(listing: dict, **changes) -> dict:
    return {k: v for k, v in DORM.items() if k != "kind"} | {"expected_version": listing["version"]} | changes


async def invite(client, listing_id: str) -> str:
    mine = (await client.get("/api/listings/mine")).json()["item"]
    r = await client.post(f"/api/listings/{listing_id}/invite", json={"expected_version": mine["version"]})
    assert r.status_code == 200, r.text
    return r.json()["invite_url"].split("#token=")[1]


async def test_no_route_returns_500_without_session(make_client):
    c = make_client()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path_format.format(**{p: uuid.uuid4() for p in route.param_convertors})
        for method in route.methods:
            r = await c.request(method, path, json={})
            assert r.status_code < 500, f"{method} {path} -> {r.status_code} {r.text}"


async def test_full_flow(make_client, login):
    owner, resident, cand = make_client(), make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(resident, "resident@g.nsu.ru", situation="host")
    await login(cand, "cand@g.nsu.ru")

    r = await owner.post("/api/listings", json=DORM)
    assert r.status_code == 201, r.text
    listing = r.json()
    assert listing["contacts"] == [{"type": "telegram", "value": "owner_tg", "url": "https://t.me/owner_tg"}]
    assert listing["expires_at"] > listing["confirmed_at"]
    assert listing["you_are_admin"] is True
    me = (await owner.get("/api/me")).json()
    assert me["situation"] == "host" and me["home"] == {"id": listing["id"], "is_admin": True}

    token = await invite(owner, listing["id"])
    r = await resident.post("/api/memberships/join", json={"invite_token": token})
    assert r.status_code == 200
    assert (await resident.get("/api/me")).json()["home"] == {"id": listing["id"], "is_admin": False}

    r = await cand.get("/api/matches", params={"kind": "dorm"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["id"] for i in items] == [listing["id"]]
    assert items[0]["compatibility"]["score"] == 100 and items[0]["fits"] is True

    for c in (owner, resident, cand):
        r = await c.get(f"/api/listings/{listing['id']}")
        assert r.status_code == 200, r.text
    assert r.json()["compatibility"]["score"] == 100 and r.json()["you_live_here"] is False
    assert (await owner.get(f"/api/listings/{listing['id']}")).json()["you_live_here"] is True

    r = await cand.get(f"/api/listings/{listing['id']}/contact")
    assert r.json() == {"items": [{"type": "telegram", "value": "owner_tg", "url": "https://t.me/owner_tg"}]}

    mine = (await owner.get("/api/listings/mine")).json()["item"]
    r = await owner.post(f"/api/listings/{listing['id']}/confirm", json={"expected_version": mine["version"]})
    assert r.status_code == 200
    r = await owner.put(f"/api/listings/{listing['id']}", json=update_body(r.json(), view="forest"))
    assert r.status_code == 200 and r.json()["view"] == "forest"

    assert (await resident.delete("/api/membership")).status_code == 204
    assert (await owner.put("/api/me", json={"display_name": "Аня"})).json()["display_name"] == "Аня"
    assert (await owner.delete(f"/api/listings/{listing['id']}")).status_code == 204
    assert (await owner.get("/api/me")).json()["home"] is None
    assert (await cand.request("DELETE", "/api/me", json={"confirm": "DELETE"})).status_code == 204
    assert (await cand.get("/api/me")).status_code == 401
    assert (await resident.post("/api/auth/logout")).status_code == 204
    assert (await resident.get("/api/me")).status_code == 401


async def test_me_language_and_profile_version(make_client, login):
    c = make_client()
    await login(c, "lang@g.nsu.ru", fill_profile=False)
    me = (await c.get("/api/me")).json()
    assert me["language"] is None and me["situation"] is None and me["profile_complete"] is False
    me = (await c.put("/api/me", json={"language": "en"})).json()
    assert me["language"] == "en" and me["display_name"] == "Пользователь"
    assert (await c.put("/api/me", json={"language": "de"})).status_code == 422
    r = await c.put("/api/profile", json={"expected_version": 0, "situation": "seeker", "budget_max_rub": 20000,
                                           "answers": answers()})
    assert r.status_code == 200 and r.json()["questionnaire_version"] == 2
    assert (await c.get("/api/me")).json()["profile_complete"] is True


async def test_only_admins_manage_the_home(make_client, login):
    admin, resident = make_client(), make_client()
    await login(admin, "admin@g.nsu.ru", situation="host")
    await login(resident, "res@g.nsu.ru", situation="host")
    listing = (await admin.post("/api/listings", json=DORM)).json()
    await resident.post("/api/memberships/join", json={"invite_token": await invite(admin, listing["id"])})

    mine = (await resident.get("/api/listings/mine")).json()["item"]
    assert mine["id"] == listing["id"] and mine["you_are_admin"] is False
    for r in (
        await resident.put(f"/api/listings/{listing['id']}", json=update_body(mine)),
        await resident.post(f"/api/listings/{listing['id']}/invite", json={"expected_version": mine["version"]}),
        await resident.post(f"/api/listings/{listing['id']}/confirm", json={"expected_version": mine["version"]}),
        await resident.delete(f"/api/listings/{listing['id']}"),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_ADMIN"

    res_id = next(x["user_id"] for x in mine["residents"] if not x["is_admin"])
    admin_id = next(x["user_id"] for x in mine["residents"] if x["is_admin"])
    assert (await admin.post(f"/api/listings/{listing['id']}/admins/{res_id}", json={})).status_code == 204
    mine = (await resident.get("/api/listings/mine")).json()["item"]
    assert mine["you_are_admin"] is True
    assert (await resident.put(f"/api/listings/{listing['id']}", json=update_body(mine))).status_code == 200

    # Два админа: можно снять одного, но не последнего.
    assert (await resident.delete(f"/api/listings/{listing['id']}/admins/{admin_id}")).status_code == 204
    r = await resident.delete(f"/api/listings/{listing['id']}/admins/{res_id}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "LAST_ADMIN"

    # Админ удаляет жильца.
    r = await resident.delete(f"/api/listings/{listing['id']}/members/{admin_id}")
    assert r.status_code == 204
    assert (await admin.get("/api/listings/mine")).json()["item"] is None


async def test_promoting_needs_a_filled_questionnaire(make_client, login):
    admin, newbie = make_client(), make_client()
    await login(admin, "admin@g.nsu.ru", situation="host")
    await login(newbie, "newbie@g.nsu.ru", situation="host")
    listing = (await admin.post("/api/listings", json=DORM)).json()
    await newbie.post("/api/memberships/join", json={"invite_token": await invite(admin, listing["id"])})
    newbie_id = (await newbie.get("/api/me")).json()["id"]
    from app.database import engine
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM profiles WHERE user_id = :u"), {"u": newbie_id})
    r = await admin.post(f"/api/listings/{listing['id']}/admins/{newbie_id}", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TARGET_PROFILE_REQUIRED"


async def test_last_admin_leaving_promotes_the_longest_resident(make_client, login):
    admin, first, second = make_client(), make_client(), make_client()
    await login(admin, "admin@g.nsu.ru", situation="host")
    await login(first, "first@g.nsu.ru", situation="host")
    await login(second, "second@g.nsu.ru", situation="host")
    listing = (await admin.post("/api/listings", json=DORM | {"capacity": 4, "occupied_count": 3})).json()
    token = await invite(admin, listing["id"])
    await first.post("/api/memberships/join", json={"invite_token": token})
    await second.post("/api/memberships/join", json={"invite_token": token})

    assert (await admin.delete("/api/membership")).status_code == 204
    assert (await first.get("/api/me")).json()["home"]["is_admin"] is True
    assert (await second.get("/api/me")).json()["home"]["is_admin"] is False

    # Последний жилец уходит — жилья больше нет.
    assert (await first.delete("/api/membership")).status_code == 204
    assert (await second.request("DELETE", "/api/me", json={"confirm": "DELETE"})).status_code == 204
    from app.database import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM listings"))).scalar() == 0


async def test_roles(make_client, login):
    host, seeker = make_client(), make_client()
    await login(host, "host@g.nsu.ru", situation="seeker")
    await login(seeker, "seeker@g.nsu.ru")
    listing = (await host.post("/api/listings", json=DORM)).json()
    # Создал жильё — стал хозяином, бюджет больше не нужен.
    prof = (await host.get("/api/profile")).json()["profile"]
    assert prof["situation"] == "host" and prof["budget_max_rub"] is None
    r = await host.put("/api/profile", json={"expected_version": prof["version"], "situation": "seeker",
                                              "budget_max_rub": 10000, "answers": answers()})
    assert r.status_code == 409 and r.json()["error"]["code"] == "LEAVE_HOME_FIRST"
    # Ищущий, вступив по приглашению, становится жильцом.
    await seeker.post("/api/memberships/join", json={"invite_token": await invite(host, listing["id"])})
    assert (await seeker.get("/api/me")).json()["situation"] == "host"


async def test_unmatched_places_are_shown_on_request(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "smoker@g.nsu.ru", profile=answers(smoking={"value": 1}), situation="host")
    await login(cand, "nonsmoker@g.nsu.ru", profile=answers(smoking={"value": 0, "hard": True, "allowed": [0]}))
    listing = (await owner.post("/api/listings", json=DORM)).json()
    assert (await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"] == []

    items = (await cand.get("/api/matches", params={"kind": "dorm", "include_unmatched": "true"})).json()["items"]
    assert [i["id"] for i in items] == [listing["id"]]
    assert items[0]["fits"] is False
    reasons = [{"code": "HARD_CONDITION", "key": "smoking", "side": "yours", "price": None, "budget": None}]
    assert items[0]["reasons"] == reasons
    detail = (await cand.get(f"/api/listings/{listing['id']}")).json()
    assert detail["fits"] is False and detail["reasons"] == reasons
    assert (await cand.get(f"/api/listings/{listing['id']}/contact")).status_code == 200


async def test_over_budget_apartment(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "flat@g.nsu.ru", situation="host")
    await login(cand, "cheap@g.nsu.ru", budget=10000)
    flat = {"kind": "apartment", "capacity": 2, "occupied_count": 1, "district": "Академгородок",
            "monthly_cost_per_person_rub": 15000, "contacts": [{"type": "phone", "value": "+79131234567"}]}
    listing = (await owner.post("/api/listings", json=flat)).json()
    assert (await cand.get("/api/matches", params={"kind": "apartment"})).json()["items"] == []
    item = (await cand.get("/api/matches", params={"kind": "apartment", "include_unmatched": "1"})).json()["items"][0]
    assert item["id"] == listing["id"] and item["monthly_cost_per_person_rub"] == 15000
    assert item["reasons"][0] == {"code": "OVER_BUDGET", "key": None, "side": None, "price": 15000, "budget": 10000}


async def test_update_onto_taken_room_is_409_not_500(make_client, login):
    a, b = make_client(), make_client()
    await login(a, "a@g.nsu.ru")
    await login(b, "b@g.nsu.ru")
    await a.post("/api/listings", json=DORM)
    other = (await b.post("/api/listings", json=DORM | {"room_number": 102})).json()
    r = await b.put(f"/api/listings/{other['id']}", json=update_body(other))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ROOM_TAKEN"


async def test_several_contacts(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "o@g.nsu.ru")
    await login(cand, "c@g.nsu.ru")
    contacts = [
        {"type": "telegram", "value": "https://t.me/some_user"},
        {"type": "whatsapp", "value": "8 (913) 123-45-67"},
        {"type": "phone", "value": "+7 913 123 45 67"},
        {"type": "phone", "value": "+7 913 765 43 21"},
        {"type": "max", "value": " Иван Петров "},
        {"type": "other", "value": "vk.com/ivan"},
    ]
    r = await owner.post("/api/listings", json=DORM | {"contacts": contacts})
    assert r.status_code == 201, r.text
    r = await cand.get(f"/api/listings/{r.json()['id']}/contact")
    assert r.json()["items"] == [
        {"type": "telegram", "value": "some_user", "url": "https://t.me/some_user"},
        {"type": "whatsapp", "value": "+79131234567", "url": "https://wa.me/79131234567"},
        {"type": "phone", "value": "+79131234567", "url": "tel:+79131234567"},
        {"type": "phone", "value": "+79137654321", "url": "tel:+79137654321"},
        {"type": "max", "value": "Иван Петров", "url": None},
        {"type": "other", "value": "vk.com/ivan", "url": None},
    ]

    # Замена списка контактов при изменении.
    listing = (await owner.get("/api/listings/mine")).json()["item"]
    r = await owner.put(f"/api/listings/{listing['id']}",
                        json=update_body(listing, contacts=[{"type": "other", "value": "в общаге"}]))
    assert r.status_code == 200 and [c["value"] for c in r.json()["contacts"]] == ["в общаге"]


@pytest.mark.parametrize("contacts,fields", [
    ([{"type": "telegram", "value": "@owner_tg"}, {"type": "telegram", "value": "@ab"}], {"contacts.1.value": "INVALID_TELEGRAM"}),
    ([{"type": "phone", "value": "123"}], {"contacts.0.value": "INVALID_PHONE"}),
    ([{"type": "other", "value": "   "}], {"contacts.0.value": "REQUIRED"}),
    ([{"type": "pigeon", "value": "x"}], {"contacts.0.type": "INVALID_CHOICE"}),
    ([], {"contacts": "TOO_SHORT"}),
    ([{"type": "other", "value": str(i)} for i in range(11)], {"contacts": "TOO_LONG"}),
])
async def test_invalid_contacts(make_client, login, contacts, fields):
    owner = make_client()
    await login(owner, "o@g.nsu.ru")
    r = await owner.post("/api/listings", json=DORM | {"contacts": contacts})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == fields
