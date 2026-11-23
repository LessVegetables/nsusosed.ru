"""Admin panel at /api/admin: only for site accounts on ADMIN_EMAILS (the database tests need Postgres)."""

from html.parser import HTMLParser
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


class _Form(HTMLParser):
    """The fields a browser would submit from the page's edit form."""
    def __init__(self):
        super().__init__()
        self.data, self._select, self._textarea = {}, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name") and a.get("type") not in ("submit", "button", "file"):
            if a.get("type") != "checkbox" or "checked" in a:
                self.data[a["name"]] = a.get("value") or ("on" if a.get("type") == "checkbox" else "")
        elif tag == "select" and a.get("name"):
            self._select = a["name"]  # nothing selected: a browser sends nothing
        elif tag == "option" and self._select and "selected" in a:
            self.data[self._select] = a.get("value", "")
        elif tag == "textarea" and a.get("name"):
            self._textarea = a["name"]
            self.data[a["name"]] = ""

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None
        elif tag == "textarea":
            self._textarea = None

    def handle_data(self, data):
        if self._textarea:
            self.data[self._textarea] += data


async def _edit_form(c, page: str) -> dict:
    parser = _Form()
    parser.feed((await c.get(page)).text)
    return parser.data


async def _admin_edit_page(c, login, db) -> str:
    from sqlalchemy import text
    await login(c, ADMIN)
    async with db.connect() as conn:
        uid = (await conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": ADMIN})).scalar()
    return f"/api/admin/user/edit?pk={uid}"


async def test_saving_a_form_keeps_unset_columns_null(make_client, login, db):
    from sqlalchemy import text
    c = make_client()
    page = await _admin_edit_page(c, login, db)
    form = await _edit_form(c, page)
    assert "csrftoken" in form
    assert "is_adult" not in form  # set by logging in (18+ only), never by hand
    form["bio"] = "edited"
    r = await c.post(page, data=form, headers={"origin": "https://testserver"})
    assert r.status_code in (302, 303), r.text[-2000:]
    async with db.connect() as conn:
        row = (await conn.execute(text("SELECT gender, faculty, intent, avatar_file, is_adult, bio, "
                                       "privacy_accepted_at = created_at OR true FROM users WHERE email = :e"),
                                  {"e": ADMIN})).one()
    assert tuple(row) == (None, None, None, None, True, "edited", True)


async def test_constraint_violation_is_a_form_error_not_a_500(make_client, login, db):
    c = make_client()
    page = await _admin_edit_page(c, login, db)
    form = await _edit_form(c, page)
    form["language"] = "xx"
    r = await c.post(page, data=form, headers={"origin": "https://testserver"})
    assert r.status_code == 422 and "ck_users_language" in r.text
