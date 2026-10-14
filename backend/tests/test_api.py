"""Сквозные проверки API (нужен Postgres)."""

import uuid
import pytest
from fastapi.routing import APIRoute
from app.main import app
from tests.conftest import answers

DORM = {"kind": "dorm", "capacity": 3, "occupied_count": 2, "building": "7", "room_number": 101, "floor": 1,
        "contact_type": "telegram", "contact_value": "@owner_tg"}


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
    await login(owner, "owner@g.nsu.ru", situation="dorm_resident")
    await login(resident, "resident@g.nsu.ru", situation="dorm_resident")
    await login(cand, "cand@g.nsu.ru")

    r = await owner.post("/api/listings", json=DORM)
    assert r.status_code == 201, r.text
    listing = r.json()
    assert listing["contact_value"] == "owner_tg"
    assert listing["expires_at"] > listing["confirmed_at"]

    r = await owner.post(f"/api/listings/{listing['id']}/invite", json={"expected_version": listing["version"]})
    assert r.status_code == 200
    token = r.json()["invite_url"].split("#token=")[1]
    r = await resident.post("/api/memberships/join", json={"invite_token": token})
    assert r.status_code == 200

    r = await cand.get("/api/matches", params={"kind": "dorm"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["id"] for i in items] == [listing["id"]]
    assert items[0]["compatibility"]["score"] == 100

    for c in (owner, resident, cand):  # раньше здесь был 500 (NameError: User)
        r = await c.get(f"/api/listings/{listing['id']}")
        assert r.status_code == 200, r.text
    assert r.json()["compatibility"]["score"] == 100

    r = await cand.get(f"/api/listings/{listing['id']}/contact")
    assert r.json() == {"type": "telegram", "value": "owner_tg", "url": "https://t.me/owner_tg"}

    mine = (await owner.get("/api/listings/mine")).json()["item"]
    r = await owner.post(f"/api/listings/{listing['id']}/confirm", json={"expected_version": mine["version"]})
    assert r.status_code == 200
    update = {k: v for k, v in DORM.items() if k != "kind"} | {"expected_version": r.json()["version"], "view": "forest"}
    r = await owner.put(f"/api/listings/{listing['id']}", json=update)
    assert r.status_code == 200 and r.json()["view"] == "forest"

    assert (await owner.delete("/api/membership")).json()["error"]["code"] == "OWNER_CANNOT_LEAVE"
    assert (await resident.delete("/api/membership")).status_code == 204
    assert (await owner.put("/api/me", json={"display_name": "Аня"})).json()["display_name"] == "Аня"
    assert (await owner.delete(f"/api/listings/{listing['id']}")).status_code == 204
    assert (await cand.request("DELETE", "/api/me", json={"confirm": "DELETE"})).status_code == 204
    assert (await cand.get("/api/me")).status_code == 401
    assert (await resident.post("/api/auth/logout")).status_code == 204
    assert (await resident.get("/api/me")).status_code == 401


async def test_hard_condition_hides_room(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "smoker@g.nsu.ru", profile=answers(smoking={"value": 1}))
    await login(cand, "nonsmoker@g.nsu.ru", profile=answers(smoking={"value": 0, "hard": True, "allowed": [0]}))
    listing = (await owner.post("/api/listings", json=DORM)).json()
    assert (await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"] == []
    assert (await cand.get(f"/api/listings/{listing['id']}")).status_code == 404
    assert (await cand.get(f"/api/listings/{listing['id']}/contact")).status_code == 404


async def test_update_onto_taken_room_is_409_not_500(make_client, login):
    a, b = make_client(), make_client()
    await login(a, "a@g.nsu.ru")
    await login(b, "b@g.nsu.ru")
    await a.post("/api/listings", json=DORM)
    other = (await b.post("/api/listings", json=DORM | {"room_number": 102})).json()
    update = {k: v for k, v in DORM.items() if k != "kind"} | {"expected_version": other["version"]}
    r = await b.put(f"/api/listings/{other['id']}", json=update)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ROOM_TAKEN"


@pytest.mark.parametrize("contact_type,value,expected_value,expected_url", [
    ("telegram", "https://t.me/some_user", "some_user", "https://t.me/some_user"),
    ("whatsapp", "8 (913) 123-45-67", "+79131234567", "https://wa.me/79131234567"),
    ("phone", "+7 913 123 45 67", "+79131234567", "tel:+79131234567"),
    ("max", " Иван Петров ", "Иван Петров", None),
    ("other", "vk.com/ivan", "vk.com/ivan", None),
])
async def test_contact_types(make_client, login, contact_type, value, expected_value, expected_url):
    owner, cand = make_client(), make_client()
    await login(owner, "o@g.nsu.ru")
    await login(cand, "c@g.nsu.ru")
    r = await owner.post("/api/listings", json=DORM | {"contact_type": contact_type, "contact_value": value})
    assert r.status_code == 201, r.text
    r = await cand.get(f"/api/listings/{r.json()['id']}/contact")
    assert r.json() == {"type": contact_type, "value": expected_value, "url": expected_url}


@pytest.mark.parametrize("contact_type,value,reason", [
    ("telegram", "@ab", "INVALID_TELEGRAM"),
    ("phone", "123", "INVALID_PHONE"),
    ("other", "   ", "REQUIRED"),
])
async def test_invalid_contacts(make_client, login, contact_type, value, reason):
    owner = make_client()
    await login(owner, "o@g.nsu.ru")
    r = await owner.post("/api/listings", json=DORM | {"contact_type": contact_type, "contact_value": value})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"contact_value": reason}
