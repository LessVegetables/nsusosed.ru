"""Hosting a home: dorm rooms, apartments, emojis, photos, address search (needs Postgres)."""

import io
from pathlib import Path
import httpx
import pytest
from PIL import Image
from sqlalchemy import text
from app.config import settings
from app.services import geo_service
from app.utils import emoji

ORIGIN = {"Origin": "https://testserver"}


def dorm(**changes) -> dict:
    base = {"kind": "dorm", "building": "6", "room_label": "100б", "description": "Тихая комната",
            "rooms": [{"gender": "f", "capacity": 2, "free_places": 1, "emoji": "🐶🍕🚀"}]}
    return base | changes


def apartment(**changes) -> dict:
    base = {"kind": "apartment", "district": "Верхняя зона", "lat": 54.84512, "lon": 83.09876, "radius_m": 420,
            "utilities_mode": "split", "utilities_rub": 2500, "internet_mode": "included",
            "rooms": [{"name": "Большая", "gender": "any", "capacity": 2, "free_places": 1, "rent_rub": 14000, "emoji": "🦊🌵🎸"},
                      {"name": "Маленькая", "gender": "f", "capacity": 1, "free_places": 1, "rent_rub": 11000, "emoji": "🐙🍋🎲"}]}
    return base | changes


async def host(make_client, login, email="host@g.nsu.ru"):
    c = make_client()
    await login(c, email)
    return c


async def fields(r) -> dict:
    assert r.status_code == 422, r.text
    return r.json()["error"]["fields"]


# ── Dorm rooms ──────────────────────────────────────────

async def test_dorm_room_is_created_and_its_number_never_comes_back(db, make_client, login):
    c = await host(make_client, login)
    assert (await c.get("/api/homes/mine")).json() == {"home": None}

    r = await c.post("/api/homes", json=dorm(room_label=" 100 Б "), headers=ORIGIN)
    assert r.status_code == 201, r.text
    home = r.json()
    assert home["kind"] == "dorm" and home["building"] == "6" and home["radius_m"] == 0
    assert home["rooms"][0] | {"id": 0} == {"id": 0, "name": "", "gender": "f", "capacity": 2, "free_places": 1,
                                            "rent_rub": None, "emoji": "🐶🍕🚀", "residents": 1}
    assert home["permissions"] == {"can_edit": True, "can_photos": True, "can_invites": True, "can_residents": True}
    # Stored normalized for the duplicate check, and absent from everything the API returns.
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT room_label FROM homes"))).scalar() == "100б"
    assert "room_label" not in r.text and "100" not in r.text
    assert "100" not in (await c.get("/api/homes/mine")).text
    assert (await c.get("/api/me")).json()["home_id"] == home["id"]


async def test_a_dorm_room_cannot_be_listed_twice(make_client, login):
    a, b = await host(make_client, login, "a@g.nsu.ru"), await host(make_client, login, "b@g.nsu.ru")
    first = (await a.post("/api/homes", json=dorm(), headers=ORIGIN)).json()

    r = await b.post("/api/homes", json=dorm(room_label="100Б", rooms=[{"gender": "f", "capacity": 2, "free_places": 1, "emoji": "🍎🍐🍊"}]),
                     headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ROOM_TAKEN"
    # The page uses this to send the person to the existing listing and its hosts.
    assert r.json()["error"]["data"] == {"room_id": first["rooms"][0]["id"]}

    # The other room of the same block and the same number in another building are different rooms.
    r = await b.post("/api/homes", json=dorm(room_label="100м", rooms=[{"gender": "f", "capacity": 2, "free_places": 1, "emoji": "🍎🍐🍊"}]),
                     headers=ORIGIN)
    assert r.status_code == 201, r.text
    c = await host(make_client, login, "c@g.nsu.ru")
    r = await c.post("/api/homes", json=dorm(building="5", rooms=[{"gender": "m", "capacity": 2, "free_places": 1, "emoji": "🍇🍓🍒"}]),
                     headers=ORIGIN)
    assert r.status_code == 201, r.text


async def test_dorm_validation(make_client, login):
    c = await host(make_client, login)
    room = dorm()["rooms"][0]
    assert await fields(await c.post("/api/homes", json=dorm(building="99"), headers=ORIGIN)) == {"building": "UNKNOWN_DORM"}
    assert await fields(await c.post("/api/homes", json=dorm(room_label="к. 100!"), headers=ORIGIN)) == {"room_label": "INVALID_ROOM"}
    assert await fields(await c.post("/api/homes", json=dorm(room_label=None), headers=ORIGIN)) == {"room_label": "REQUIRED"}
    assert await fields(await c.post("/api/homes", json=dorm(rooms=[room | {"gender": "any"}]), headers=ORIGIN)) == \
        {"rooms.0.gender": "DORM_ROOM_NEEDS_GENDER"}
    assert await fields(await c.post("/api/homes", json=dorm(rooms=[room, room | {"emoji": "🍎🍐🍊"}]), headers=ORIGIN)) == \
        {"rooms": "DORM_HAS_ONE_ROOM"}
    assert await fields(await c.post("/api/homes", json=dorm(rooms=[room | {"free_places": 3}]), headers=ORIGIN)) == \
        {"rooms.0.free_places": "MORE_THAN_CAPACITY"}


async def test_one_home_per_person(make_client, login):
    c = await host(make_client, login)
    assert (await c.post("/api/homes", json=dorm(), headers=ORIGIN)).status_code == 201
    r = await c.post("/api/homes", json=apartment(), headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_IN_HOME"


# ── Apartments ──────────────────────────────────────────

async def test_apartment_stores_only_the_obfuscated_circle(db, make_client, login):
    c = await host(make_client, login)
    r = await c.post("/api/homes", json=apartment(lat=54.845123456, lon=83.098765432), headers=ORIGIN)
    assert r.status_code == 201, r.text
    home = r.json()
    assert (home["lat"], home["lon"], home["radius_m"], home["district"]) == (54.84512, 83.09877, 420, "Верхняя зона")
    assert [(x["name"], x["rent_rub"], x["gender"]) for x in home["rooms"]] == [("Большая", 14000, "any"), ("Маленькая", 11000, "f")]
    assert (home["utilities_mode"], home["utilities_rub"], home["internet_mode"]) == ("split", 2500, "included")
    # There is nowhere an address could be: these are all the columns a home has.
    async with db.connect() as conn:
        cols = {row[0] for row in await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name IN ('homes', 'rooms')"))}
    assert not cols & {"address", "street", "house", "apartment", "flat", "apartment_number"}


async def test_apartment_validation(make_client, login):
    c = await host(make_client, login)
    post = lambda **kw: c.post("/api/homes", json=apartment(**kw), headers=ORIGIN)
    assert await fields(await post(radius_m=0)) == {"location": "BAD_RADIUS"}          # an exact point is refused
    assert await fields(await post(radius_m=900)) == {"location": "BAD_RADIUS"}
    assert await fields(await post(lat=55.75, lon=37.62)) == {"location": "OUTSIDE_AREA"}  # Moscow
    assert await fields(await post(lat=None)) == {"location": "REQUIRED"}
    assert await fields(await post(district="  ")) == {"district": "REQUIRED"}
    assert await fields(await post(utilities_rub=None)) == {"utilities_rub": "REQUIRED"}
    assert await fields(await post(internet_mode=None)) == {"internet_mode": "REQUIRED"}
    rooms = apartment()["rooms"]
    assert await fields(await post(rooms=[rooms[0] | {"rent_rub": None}])) == {"rooms.0.rent_rub": "REQUIRED"}
    assert await fields(await post(rooms=[rooms[0], rooms[1] | {"emoji": "🎸🦊🌵"}])) == {"rooms.1.emoji": "EMOJI_TAKEN"}
    r = await post(utilities_mode="included", utilities_rub=999)
    assert r.status_code == 201 and r.json()["utilities_rub"] is None


async def test_editing_rooms_adds_changes_and_removes(make_client, login):
    c = await host(make_client, login)
    home = (await c.post("/api/homes", json=apartment(), headers=ORIGIN)).json()
    big, small = home["rooms"]
    assert (big["residents"], small["residents"]) == (1, 0)   # the creator lives in the first room

    body = apartment(rooms=[
        {"id": big["id"], "name": "Большая", "gender": "any", "capacity": 2, "free_places": 0, "rent_rub": 15000, "emoji": "🦊🌵🎸"},
        {"name": "Новая", "gender": "m", "capacity": 1, "free_places": 1, "rent_rub": 9000, "emoji": "🐙🍋🎲"},  # the removed room's emojis
    ])
    r = await c.put(f"/api/homes/{home['id']}", json=body, headers=ORIGIN)
    assert r.status_code == 200, r.text
    rooms = r.json()["rooms"]
    assert [x["name"] for x in rooms] == ["Большая", "Новая"] and rooms[0]["id"] == big["id"] and rooms[0]["rent_rub"] == 15000
    assert rooms[1]["id"] != small["id"]

    # A room someone lives in can't be removed; the kind can't change.
    r = await c.put(f"/api/homes/{home['id']}", json=apartment(rooms=[body["rooms"][1] | {"id": rooms[1]["id"]}]), headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ROOM_OCCUPIED"
    r = await c.put(f"/api/homes/{home['id']}", json=dorm(), headers=ORIGIN)
    assert await fields(r) == {"kind": "IMMUTABLE"}


async def test_only_hosts_with_the_right_can_edit(db, make_client, login):
    owner, other = await host(make_client, login, "a@g.nsu.ru"), await host(make_client, login, "b@g.nsu.ru")
    home = (await owner.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    assert (await other.put(f"/api/homes/{home['id']}", json=dorm(), headers=ORIGIN)).status_code == 404
    async with db.begin() as conn:
        await conn.execute(text("UPDATE memberships SET can_edit = false, can_photos = false"))
    r = await owner.put(f"/api/homes/{home['id']}", json=dorm(description="x"), headers=ORIGIN)
    assert r.status_code == 403 and r.json()["error"]["code"] == "NO_PERMISSION"
    r = await owner.post(f"/api/homes/{home['id']}/photos", headers=ORIGIN, files={"file": ("a.png", picture(), "image/png")})
    assert r.status_code == 403


async def test_dorm_edit_keeps_the_room_number_unless_a_new_one_is_given(db, make_client, login):
    c = await host(make_client, login)
    home = (await c.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    room = home["rooms"][0]
    body = dorm(room_label=None, description="Новое описание",
                rooms=[{"id": room["id"], "gender": "f", "capacity": 3, "free_places": 2, "emoji": "🐶🍕🚀"}])
    r = await c.put(f"/api/homes/{home['id']}", json=body, headers=ORIGIN)
    assert r.status_code == 200 and r.json()["rooms"][0]["capacity"] == 3 and r.json()["description"] == "Новое описание"
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT room_label FROM homes"))).scalar() == "100б"


# ── Visibility ──────────────────────────────────────────

async def test_a_home_is_visible_once_a_host_is_reachable_and_there_is_a_free_place(make_client, login):
    c = await host(make_client, login)
    home = (await c.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    assert (home["needs_contact"], home["needs_free_place"], home["visible"]) == (True, False, False)
    await c.put("/api/me/contacts", json={"contacts": [{"type": "telegram", "value": "@host_one"}]}, headers=ORIGIN)
    home = (await c.get("/api/homes/mine")).json()["home"]
    assert (home["needs_contact"], home["visible"]) == (False, True)
    body = dorm(room_label=None, rooms=[home["rooms"][0] | {"free_places": 0}])
    home = (await c.put(f"/api/homes/{home['id']}", json=body, headers=ORIGIN)).json()
    assert (home["needs_free_place"], home["visible"]) == (True, False)


# ── Emojis ──────────────────────────────────────────────

@pytest.mark.parametrize("value", ["🐶🍕", "🐶🍕🚀🎸", "🐶🐶🍕", "🐶🍕🇷🇺", "🐶🍕🏁", "🐶🍕🏳️‍🌈", "abc", "🐶🍕1️⃣", ""])
def test_emojis_must_be_three_different_non_flags(value):
    assert emoji.normalize(value) is None


def test_typed_emojis_can_be_anything_else_and_order_does_not_matter():
    assert emoji.normalize("👍🏽 ❤️ 👨‍💻")[0] == "👍🏽❤️👨‍💻"
    assert emoji.normalize("🍕🐶🦊")[1] == emoji.normalize("🦊🍕🐶")[1]
    assert all(emoji.normalize(emoji.roll()) for _ in range(200))


async def test_emojis_are_unique_across_listings_and_the_roll_avoids_taken_ones(make_client, login, monkeypatch):
    a, b = await host(make_client, login, "a@g.nsu.ru"), await host(make_client, login, "b@g.nsu.ru")
    await a.post("/api/homes", json=dorm(), headers=ORIGIN)
    r = await b.post("/api/homes", json=dorm(room_label="200", rooms=[{"gender": "f", "capacity": 1, "free_places": 1, "emoji": "🚀🐶🍕"}]),
                     headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMOJI_TAKEN"
    assert r.json()["error"]["fields"] == {"rooms.0.emoji": "EMOJI_TAKEN"}

    rolls = iter(["🍕🚀🐶", "🦊🌵🎸", "🌵🎸🦊", "🐙🍋🎲"])   # taken, free, same as the second, free
    monkeypatch.setattr(emoji, "roll", lambda: next(rolls))
    r = await b.post("/api/emoji/roll", json={"count": 2}, headers=ORIGIN)
    assert r.json() == {"emojis": ["🦊🌵🎸", "🐙🍋🎲"]}


# ── Photos ──────────────────────────────────────────────

def picture(size=(2400, 1200)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(out, "PNG")
    return out.getvalue()


async def test_photos_upload_reorder_delete_and_go_with_the_home(make_client, login):
    c = await host(make_client, login)
    home = (await c.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    url = f"/api/homes/{home['id']}/photos"
    for _ in range(2):
        r = await c.post(url, headers=ORIGIN, files={"file": ("room.png", picture(), "image/png")})
        assert r.status_code == 201, r.text
    first, second = r.json()["photos"]
    assert (first["width"], first["height"]) == (1600, 800)
    folder = Path(settings.media_dir) / "homes" / home["id"]
    assert len(list(folder.glob("*.jpg"))) == 2

    r = await c.put(f"{url}/order", json={"photo_ids": [second["id"], first["id"]]}, headers=ORIGIN)
    assert [p["id"] for p in r.json()["photos"]] == [second["id"], first["id"]]
    r = await c.put(f"{url}/order", json={"photo_ids": [first["id"]]}, headers=ORIGIN)
    assert await fields(r) == {"photo_ids": "INVALID_SET"}

    r = await c.request("DELETE", f"{url}/{first['id']}", headers=ORIGIN)
    assert [p["id"] for p in r.json()["photos"]] == [second["id"]] and len(list(folder.glob("*.jpg"))) == 1

    # The last person out takes the home and its photos with them.
    assert (await c.request("DELETE", "/api/homes/mine/membership", headers=ORIGIN)).status_code == 204
    assert (await c.get("/api/homes/mine")).json() == {"home": None} and not folder.exists()
    assert (await c.post("/api/homes", json=dorm(), headers=ORIGIN)).status_code == 201   # the room is free again


# ── Address search ──────────────────────────────────────

async def test_address_search_proxies_nominatim_and_keeps_nothing(make_client, login, monkeypatch, caplog):
    seen = {}

    def nominatim(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["agent"] = request.url, request.headers["user-agent"]
        place = {"lat": "54.8431234567", "lon": "83.0931234567", "display_name": "long name",
                 "address": {"road": "улица Пирогова", "house_number": "2", "suburb": "Верхняя зона", "city": "Новосибирск"}}
        return httpx.Response(200, json=[place, place | {"lat": "54.8439"}])   # the same building twice

    monkeypatch.setattr(geo_service, "_client", lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(nominatim), headers={"User-Agent": geo_service.USER_AGENT}))
    monkeypatch.setattr(geo_service, "_last_upstream", 0.0)
    geo_service._last_by_user.clear()

    c = await host(make_client, login)
    with caplog.at_level("DEBUG"):
        r = await c.post("/api/geo/search", json={"query": "Пирогова 2"}, headers=ORIGIN)
    assert r.status_code == 200, r.text
    assert r.json() == {"results": [{"label": "улица Пирогова 2, Верхняя зона", "lat": 54.843123, "lon": 83.093123,
                                     "district": "Верхняя зона"}]}
    assert seen["url"].params["q"] == "Пирогова 2" and seen["url"].params["bounded"] == "1"
    assert "nsusosed.ru" in seen["agent"]
    # The address is not written to our logs: not as typed, not URL-encoded, not as a request line.
    assert not any(word in caplog.text for word in ("Пирогова", "%D0%9F", "nominatim", "q="))

    r = await c.post("/api/geo/search", json={"query": "Пирогова 2"}, headers=ORIGIN)
    assert r.status_code == 429                   # one search every couple of seconds per person
    assert (await make_client().post("/api/geo/search", json={"query": "Пирогова 2"}, headers=ORIGIN)).status_code == 401
