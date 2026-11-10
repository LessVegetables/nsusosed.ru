"""Account deletion with a grace period (needs Postgres)."""

from sqlalchemy import text

ORIGIN = {"Origin": "https://testserver"}
EMAIL = "owner@g.nsu.ru"


async def delete_account(client):
    r = await client.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=ORIGIN)
    assert r.status_code == 204, r.text


async def forget_rate_limits(db, email):
    # A second login right after the first would hit the one-minute pause between codes.
    async with db.begin() as conn:
        await conn.execute(text("DELETE FROM auth_events WHERE email = :e"), {"e": email})


async def age_deletion(db, email, days):
    async with db.begin() as conn:
        await conn.execute(text("UPDATE users SET deleted_at = now() - make_interval(days => :d) WHERE email = :e"),
                           {"d": days, "e": email})


async def count_users(db, email):
    async with db.connect() as conn:
        return (await conn.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": email})).scalar()


async def test_delete_needs_confirmation_and_closes_every_session(db, make_client, login):
    phone, laptop = make_client(), make_client()
    await login(phone, EMAIL)
    await forget_rate_limits(db, EMAIL)
    await login(laptop, EMAIL)

    r = await phone.request("DELETE", "/api/me", json={"confirm": "yes"}, headers=ORIGIN)
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"confirm": "MUST_BE_DELETE"}

    await delete_account(phone)
    assert (await phone.get("/api/me")).status_code == 401
    assert (await laptop.get("/api/me")).status_code == 401
    assert await count_users(db, EMAIL) == 1  # hidden, not erased yet


async def test_logging_in_during_the_grace_period_restores_the_account(db, make_client, login):
    c = make_client()
    await login(c, EMAIL, first_name="Аня")
    await c.put("/api/me", json={"bio": "люблю тишину"}, headers=ORIGIN)
    await delete_account(c)
    await age_deletion(db, EMAIL, 13)

    await forget_rate_limits(db, EMAIL)
    auth = await login(c, EMAIL)
    assert auth["account_restored"] is True and auth["is_new"] is False
    assert (await c.get("/api/me")).json()["bio"] == "люблю тишину"
    # An ordinary login doesn't set the flag.
    await forget_rate_limits(db, EMAIL)
    assert (await login(c, EMAIL))["account_restored"] is False


async def test_account_is_erased_after_the_grace_period(db, make_client, login):
    c, other = make_client(), make_client()
    await login(c, EMAIL)
    await delete_account(c)
    await age_deletion(db, EMAIL, 15)

    # Erasing runs on any login.
    await login(other, "other@g.nsu.ru")
    assert await count_users(db, EMAIL) == 0

    # The same address afterwards is a brand-new account.
    await forget_rate_limits(db, EMAIL)
    auth = await login(c, EMAIL)
    assert auth["is_new"] is True and auth["account_restored"] is False
