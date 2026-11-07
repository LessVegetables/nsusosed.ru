"""Удаление аккаунта со сроком ожидания (нужен Postgres)."""

from sqlalchemy import text
from tests.test_api import DORM, invite

ORIGIN = {"Origin": "https://testserver"}


async def delete_account(client):
    r = await client.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=ORIGIN)
    assert r.status_code == 204, r.text


async def relogin(db, client, codes, email):
    # Повторный вход сразу после первого упёрся бы в минутную паузу между кодами.
    async with db.begin() as conn:
        await conn.execute(text("DELETE FROM auth_events WHERE email = :e"), {"e": email})
    r = await client.post("/api/auth/request-code", json={"email": email, "privacy_accepted": True})
    assert r.status_code == 200, r.text
    r = await client.post("/api/auth/verify-code", json={"email": email, "code": codes[email]})
    assert r.status_code == 200, r.text
    return r.json()


async def age_deletion(db, email, days):
    async with db.begin() as conn:
        await conn.execute(text("UPDATE users SET deleted_at = now() - make_interval(days => :d) WHERE email = :e"),
                           {"d": days, "e": email})


async def scalar(db, sql, **params):
    async with db.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


async def test_deleted_account_is_hidden_and_admin_passes_on(db, make_client, login):
    owner, resident, cand = make_client(), make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(resident, "res@g.nsu.ru", situation="host")
    await login(cand, "cand@g.nsu.ru")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    await resident.post("/api/memberships/join", json={"invite_token": await invite(owner, listing["id"])})

    await delete_account(owner)
    assert (await owner.get("/api/me")).status_code == 401

    # Соседи его не видят, а админом стал оставшийся жилец.
    home = (await resident.get("/api/listings/mine")).json()["item"]
    assert [r["display_name"] for r in home["residents"]] == ["Пользователь"]
    assert home["you_are_admin"] is True
    # Кандидат видит жильё по анкете оставшегося жильца.
    detail = (await cand.get(f"/api/listings/{listing['id']}")).json()
    assert detail["answered_count"] == 1 and len(detail["residents"]) == 1


async def test_only_resident_deleting_hides_the_home(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(cand, "cand@g.nsu.ru")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    assert len((await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"]) == 1

    await delete_account(owner)
    assert (await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"] == []
    assert (await cand.get(f"/api/listings/{listing['id']}")).status_code == 404


async def test_logging_in_during_the_grace_period_restores_everything(db, make_client, login, codes):
    owner, cand = make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(cand, "cand@g.nsu.ru")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    await delete_account(owner)
    await age_deletion(db, "owner@g.nsu.ru", 13)

    auth = await relogin(db, owner, codes, "owner@g.nsu.ru")
    assert auth["account_restored"] is True and auth["profile_complete"] is True
    me = (await owner.get("/api/me")).json()
    assert me["home"] == {"id": listing["id"], "is_admin": True}
    assert len((await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"]) == 1
    # Обычный вход флаг не ставит.
    assert (await relogin(db, owner, codes, "owner@g.nsu.ru"))["account_restored"] is False


async def test_account_is_erased_after_the_grace_period(db, make_client, login, codes):
    owner, resident, other = make_client(), make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(resident, "res@g.nsu.ru", situation="host")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    await resident.post("/api/memberships/join", json={"invite_token": await invite(owner, listing["id"])})
    await delete_account(owner)
    await delete_account(resident)
    await age_deletion(db, "owner@g.nsu.ru", 15)

    # Стирание идёт при любом входе. Владелец стёрт; жильё живо, пока ждёт второй жилец.
    await login(other, "other@g.nsu.ru")
    assert await scalar(db, "SELECT count(*) FROM users WHERE email = 'owner@g.nsu.ru'") == 0
    assert await scalar(db, "SELECT count(*) FROM profiles p JOIN users u ON u.id = p.user_id "
                            "WHERE u.email = 'owner@g.nsu.ru'") == 0
    assert await scalar(db, "SELECT count(*) FROM listings") == 1

    # Стёрт последний жилец — жильё удалено.
    await age_deletion(db, "res@g.nsu.ru", 15)
    await relogin(db, other, codes, "other@g.nsu.ru")
    assert await scalar(db, "SELECT count(*) FROM listings") == 0

    # Тот же адрес после стирания — это новый аккаунт.
    auth = await relogin(db, owner, codes, "owner@g.nsu.ru")
    assert auth["account_restored"] is False and auth["profile_complete"] is False
