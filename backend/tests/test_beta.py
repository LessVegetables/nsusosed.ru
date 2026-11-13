"""Closed beta: BETA_EMAILS lets only listed addresses in (the database tests need Postgres)."""

import pytest
from sqlalchemy import text
from app.config import settings

IN = "tester@g.nsu.ru"
OUT = "stranger@g.nsu.ru"


@pytest.fixture
def beta(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(settings, "beta_emails", value)
    return _set


def test_list_parsing(beta):
    beta("")
    assert settings.beta_allows("anyone@nsu.ru")
    beta(" A@nsu.ru,b@g.nsu.ru\n c@nsu.ru ,, ")
    assert settings.beta_allowlist == {"a@nsu.ru", "b@g.nsu.ru", "c@nsu.ru"}
    assert settings.beta_allows("a@nsu.ru") and not settings.beta_allows("d@nsu.ru")


async def test_unlisted_address_gets_no_code(db, make_client, codes, beta):
    beta(IN)
    r = await make_client().post("/api/auth/request-code", json={"email": OUT, "privacy_accepted": True})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "BETA_CLOSED"
    assert r.json()["error"]["fields"] == {"email": "BETA_CLOSED"}
    assert OUT not in codes
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM otp_codes"))).scalar() == 0


async def test_listed_address_logs_in_case_insensitively(make_client, login, beta):
    beta(IN.upper())
    c = make_client()
    await login(c, IN)
    assert (await c.get("/api/me")).status_code == 200


async def test_code_sent_before_removal_no_longer_works(make_client, codes, beta):
    beta(IN)
    c = make_client()
    await c.post("/api/auth/request-code", json={"email": IN, "privacy_accepted": True})
    beta("someone.else@g.nsu.ru")
    r = await c.post("/api/auth/verify-code", json={"email": IN, "code": codes[IN], "first_name": "Аня", "last_name": "Ким"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "BETA_CLOSED"


async def test_removal_logs_out_at_once(make_client, login, beta):
    beta(IN)
    c = make_client()
    await login(c, IN)
    beta("someone.else@g.nsu.ru")
    assert (await c.get("/api/me")).status_code == 401
    beta("")  # the beta ends: the same session works again
    assert (await c.get("/api/me")).status_code == 200
