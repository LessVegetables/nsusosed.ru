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


async def test_logout_and_account_deletion_clear_the_cookie(make_client, login):
    """The 204 these routes send must carry the cookie removal, or the browser keeps a dead token."""
    origin = {"Origin": "https://testserver"}
    for email, leave in (("out@g.nsu.ru", lambda c: c.post("/api/auth/logout", headers=origin)),
                         ("gone@g.nsu.ru", lambda c: c.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=origin))):
        c = make_client()
        await login(c, email)
        r = await leave(c)
        assert r.status_code == 204
        cleared = [h for h in r.headers.get_list("set-cookie") if h.startswith(f"{COOKIE}=")]
        assert cleared and "max-age=0" in cleared[0].lower(), r.headers
        assert COOKIE not in c.cookies


async def test_the_session_is_saved_before_the_login_answer_is_sent(make_client, login, monkeypatch):
    """The commit comes before the response starts: the /api/me the page sends right away must see it."""
    import httpx
    from app import database
    from app.main import app

    order = []
    real = database.AsyncSession.commit

    async def commit(self):
        order.append("commit")
        return await real(self)

    monkeypatch.setattr(database.AsyncSession, "commit", commit)

    async def watched(scope, receive, send):
        if scope.get("path") == "/api/auth/verify-code":
            order.clear()  # only this request's commits count

        async def send_and_note(message):
            if message["type"] == "http.response.start" and scope["path"] == "/api/auth/verify-code":
                order.append("sent")
            await send(message)
        await app(scope, receive, send_and_note)

    make_client()  # the database, emptied
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=watched, client=("10.99.0.1", 1)),
                                 base_url="https://testserver") as c:
        await login(c, "s@g.nsu.ru")
    assert "sent" in order and "commit" in order[:order.index("sent")], order
