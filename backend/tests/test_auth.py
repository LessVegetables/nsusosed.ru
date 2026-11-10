"""Вход по коду: создание пользователя и ограничения частоты (нужен Postgres)."""

from sqlalchemy import text

EMAIL = "student@g.nsu.ru"


NAME = {"first_name": "Аня", "last_name": "Ким"}


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


async def count_users(db, email: str) -> int:
    async with db.connect() as conn:
        return (await conn.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": email})).scalar()


async def age_auth_events(db, email: str, seconds: int) -> None:
    async with db.begin() as conn:
        await conn.execute(text("UPDATE auth_events SET created_at = created_at - make_interval(secs => :s) "
                                "WHERE email = :e"), {"s": seconds, "e": email})


async def test_user_is_created_only_after_verification(db, make_client, codes):
    c = make_client()
    r = await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
    assert r.status_code == 200 and r.json()["is_new"] is True
    assert await count_users(db, EMAIL) == 0

    r = await c.post("/api/auth/verify-code", json={
        "email": EMAIL, "code": codes[EMAIL], "first_name": "  Аня ", "last_name": "Ким", "language": "zh"})
    assert r.status_code == 200
    assert r.json()["is_new"] is True and r.json()["first_name"] == "Аня"
    assert await count_users(db, EMAIL) == 1
    me = (await c.get("/api/me")).json()
    assert (me["first_name"], me["last_name"], me["language"]) == ("Аня", "Ким", "zh")
    assert me["questionnaire_complete"] is False and me["intent"] is None


async def test_first_login_needs_a_name_and_does_not_burn_the_code(db, make_client, codes):
    c = make_client()
    await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
    r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": codes[EMAIL]})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"first_name": "MISSING", "last_name": "MISSING"}
    r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": codes[EMAIL], "first_name": "Аня"})
    assert r.json()["error"]["fields"] == {"last_name": "MISSING"}
    assert await count_users(db, EMAIL) == 0
    r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": codes[EMAIL]} | NAME)
    assert r.status_code == 200


async def test_returning_user_skips_the_name_and_keeps_their_language(db, make_client, login):
    c = make_client()
    await login(c, EMAIL, language="en")
    await age_auth_events(db, EMAIL, 61)
    again = await login(make_client(), EMAIL, first_name="Other")
    assert again["is_new"] is False and again["first_name"] == "Иван"
    assert (await c.get("/api/me")).json()["language"] == "en"

    # Picking a language on the login page is saved to the account.
    await age_auth_events(db, EMAIL, 61)
    await login(make_client(), EMAIL, language="ru")
    assert (await c.get("/api/me")).json()["language"] == "ru"


async def test_wrong_domain_and_missing_privacy(make_client):
    c = make_client()
    r = await c.post("/api/auth/request-code", json={"email": "x@gmail.com", "privacy_accepted": True})
    assert r.json()["error"]["fields"] == {"email": "DOMAIN_NOT_ALLOWED"}
    r = await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": False})
    assert r.json()["error"]["fields"] == {"privacy_accepted": "MUST_ACCEPT"}


async def test_resend_cooldown(make_client, codes):
    c = make_client()
    assert (await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})).status_code == 200
    r = await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert 0 < r.json()["error"]["retry_after"] <= 60
    assert r.headers["Retry-After"] == str(r.json()["error"]["retry_after"])


async def test_code_dies_after_five_wrong_attempts(make_client, codes):
    c = make_client()
    await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
    for _ in range(5):
        r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": wrong(codes[EMAIL])} | NAME)
        assert r.json()["error"]["code"] == "INVALID_CODE"
    r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": codes[EMAIL]} | NAME)
    assert r.status_code == 401


async def test_failed_verifies_are_capped_across_fresh_codes(db, make_client, codes):
    c = make_client()
    statuses = []
    for i in range(11):
        if i % 4 == 0:  # новый код до того, как старый сгорит
            await age_auth_events(db, EMAIL, 61)  # мимо кулдауна на повторную отправку
            await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
        r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": wrong(codes[EMAIL])} | NAME)
        statuses.append(r.status_code)
    assert statuses == [401] * 10 + [429]
    # Даже верный код не проходит, пока действует блокировка
    r = await c.post("/api/auth/verify-code", json={"email": EMAIL, "code": codes[EMAIL]} | NAME)
    assert r.status_code == 429


async def test_hourly_code_request_limit(db, make_client):
    c = make_client()
    statuses = []
    for _ in range(6):
        await age_auth_events(db, EMAIL, 61)
        r = await c.post("/api/auth/request-code", json={"email": EMAIL, "privacy_accepted": True})
        statuses.append(r.status_code)
    assert statuses == [200] * 5 + [429]


async def test_per_ip_limit(make_client):
    c = make_client(ip="10.200.0.1")
    statuses = [
        (await c.post("/api/auth/request-code", json={"email": f"s{i}@g.nsu.ru", "privacy_accepted": True})).status_code
        for i in range(21)
    ]
    assert statuses == [200] * 20 + [429]
    # Другой IP не затронут
    other = make_client(ip="10.200.0.2")
    r = await other.post("/api/auth/request-code", json={"email": "other@g.nsu.ru", "privacy_accepted": True})
    assert r.status_code == 200
