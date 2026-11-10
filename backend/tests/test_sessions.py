"""Сессии и выход (нужен Postgres)."""

from sqlalchemy import text
from app.config import settings

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
