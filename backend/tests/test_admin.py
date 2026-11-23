"""Admin panel at /api/admin: only for site accounts on ADMIN_EMAILS (the database tests need Postgres)."""

from fastapi import FastAPI
from app.admin import mount_admin
from app.config import settings

ADMIN = "admin@g.nsu.ru"  # set in conftest before the app is imported


def test_not_mounted_without_admin_emails(monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "")
    app = FastAPI()
    mount_admin(app)
    assert not any(getattr(r, "path", "").startswith("/api/admin") for r in app.routes)


async def test_anonymous_is_sent_to_site_login(make_client):
    c = make_client()
    r = await c.get("/api/admin/")
    assert r.status_code == 303
    assert r.headers["location"].startswith("https://testserver/api/admin/login")
    r = await c.get("/api/admin/login")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert (await c.get("/api/admin/user/list")).status_code == 303


async def test_user_not_on_the_list_gets_403(make_client, login):
    c = make_client()
    await login(c, "student@g.nsu.ru")
    assert (await c.get("/api/admin/")).status_code == 303
    assert (await c.get("/api/admin/login")).status_code == 403
    assert (await c.get("/api/admin/user/list")).status_code == 303


async def test_admin_sees_tables_without_secrets(make_client, login):
    c = make_client()
    await login(c, ADMIN)
    assert (await c.get("/api/admin/")).status_code == 200
    r = await c.get("/api/admin/user/list")
    assert r.status_code == 200 and ADMIN in r.text
    for page in ("session/list", "otp-code/list", "invite/list", "home/list", "home/create"):
        r = await c.get(f"/api/admin/{page}")
        assert r.status_code == 200, page
        assert not [s for s in ("token_hash", "code_hash", "room_label") if s in r.text], page
    assert (await c.get("/api/admin/session/create")).status_code in (403, 404)


async def test_admin_off_beta_is_locked_out(make_client, login, monkeypatch):
    c = make_client()
    await login(c, ADMIN)
    monkeypatch.setattr(settings, "beta_emails", "someone.else@g.nsu.ru")
    assert (await c.get("/api/admin/")).status_code == 303
