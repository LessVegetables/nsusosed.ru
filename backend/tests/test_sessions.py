"""Сессии, выход и гонки на уникальных индексах (нужен Postgres)."""

import asyncio
from sqlalchemy import text
from app.config import settings
from tests.test_api import DORM

COOKIE = settings.cookie_name


async def test_session_is_extended_after_half_its_life(db, make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")

    # Свежая сессия: продлевать рано, cookie не ставится заново.
    r = await c.get("/api/me")
    assert r.status_code == 200 and COOKIE not in r.cookies

    # Осталось меньше половины срока: продлеваем и в базе, и в cookie.
    async with db.begin() as conn:
        await conn.execute(text("UPDATE sessions SET expires_at = now() + interval '1 hour'"))
    r = await c.get("/api/me")
    assert r.status_code == 200 and COOKIE in r.cookies
    async with db.connect() as conn:
        left = (await conn.execute(text("SELECT extract(epoch FROM expires_at - now()) FROM sessions"))).scalar()
    assert left > settings.session_ttl_seconds - 60


async def test_logout_checks_origin(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    r = await c.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert (await c.get("/api/me")).status_code == 200

    # Без тела и Content-Type — как его шлёт фронтенд.
    r = await c.post("/api/auth/logout", headers={"Origin": "https://testserver"})
    assert r.status_code == 204
    assert (await c.get("/api/me")).status_code == 401


async def test_simultaneous_create_of_the_same_room_is_409_not_500(make_client, login):
    a, b = make_client(), make_client()
    await login(a, "a@g.nsu.ru", situation="host")
    await login(b, "b@g.nsu.ru", situation="host")
    ra, rb = await asyncio.gather(a.post("/api/listings", json=DORM), b.post("/api/listings", json=DORM))
    assert sorted([ra.status_code, rb.status_code]) == [201, 409]
    loser = ra if ra.status_code == 409 else rb
    assert loser.json()["error"]["code"] == "ROOM_TAKEN"


async def test_double_click_on_create_is_409_not_500(make_client, login):
    c = make_client()
    await login(c, "a@g.nsu.ru", situation="host")
    r1, r2 = await asyncio.gather(c.post("/api/listings", json=DORM),
                                  c.post("/api/listings", json=DORM | {"room_number": 102}))
    assert sorted([r1.status_code, r2.status_code]) == [201, 409]
    loser = r1 if r1.status_code == 409 else r2
    assert loser.json()["error"]["code"] == "ALREADY_IN_ROOM"
