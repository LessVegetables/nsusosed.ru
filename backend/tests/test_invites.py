"""Invites, joining, residents and their rights (needs Postgres)."""

from sqlalchemy import text
from app.services.home_service import parse_invite_code
from tests.test_homes import ORIGIN, apartment, dorm, fields


async def member(make_client, login, email, name="Иван"):
    c = make_client()
    await login(c, email, first_name=name)
    return c


async def invite(c, home_id, **body) -> dict:
    r = await c.post(f"/api/homes/{home_id}/invites", json=body, headers=ORIGIN)
    assert r.status_code == 201, r.text
    return r.json()


async def join(c, code):
    return await c.post("/api/invites/join", json={"code": code}, headers=ORIGIN)


def test_the_invite_field_takes_a_code_or_a_link():
    for pasted in ("K7QM2XWP", " k7qm-2xwp ", "https://nsusosed.ru/join#code=K7QM2XWP", "nsusosed.ru/join#code=k7qm2xwp&x=1",
                   "Заходи: https://nsusosed.ru/join#code=K7QM2XWP !"):
        assert parse_invite_code(pasted) == "K7QM2XWP", pasted


async def test_invite_join_and_what_the_new_resident_can_do(db, make_client, login):
    owner, mate = await member(make_client, login, "a@g.nsu.ru", "Аня"), await member(make_client, login, "b@g.nsu.ru", "Боря")
    home = (await owner.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    inv = await invite(owner, home["id"])
    assert len(inv["code"]) == 8 and inv["url"] == f"https://testserver/join#code={inv['code']}"
    # Only the hash is stored, and the list never shows the code again.
    async with db.connect() as conn:
        assert inv["code"] not in str((await conn.execute(text("SELECT * FROM invites"))).all())
    listed = (await owner.get(f"/api/homes/{home['id']}/invites")).json()
    assert [(i["id"], i["code"], i["created_by_name"]) for i in listed] == [(inv["id"], None, "Аня")]

    r = await mate.post("/api/invites/preview", json={"code": inv["url"]}, headers=ORIGIN)
    assert r.json() == {"kind": "dorm", "building": "6", "district": None, "emoji": "🐶🍕🚀", "room_name": "", "hosts": ["Аня"]}
    assert "100" not in r.text

    r = await join(mate, inv["code"].lower())
    assert r.status_code == 200, r.text
    joined = r.json()
    assert [(x["first_name"], x["is_you"]) for x in joined["residents"]] == [("Аня", False), ("Боря", True)]
    assert joined["permissions"] == dict.fromkeys(("can_edit", "can_photos", "can_invites", "can_residents"), False)
    assert joined["rooms"][0]["residents"] == 2
    assert (await mate.get("/api/me")).json()["home_id"] == home["id"]
    assert (await join(mate, inv["code"])).status_code == 200          # the same link again is harmless

    # Without rights: no editing, no invites, no removing people.
    assert (await mate.put(f"/api/homes/{home['id']}", json=dorm(room_label=None), headers=ORIGIN)).status_code == 403
    assert (await mate.post(f"/api/homes/{home['id']}/invites", json={}, headers=ORIGIN)).status_code == 403
    assert (await mate.get(f"/api/homes/{home['id']}/invites")).status_code == 403
    owner_id = joined["residents"][0]["user_id"]
    assert (await mate.request("DELETE", f"/api/homes/{home['id']}/residents/{owner_id}", headers=ORIGIN)).status_code == 403


async def test_bad_expired_and_revoked_invites_and_one_home_per_person(db, make_client, login):
    owner, mate, other = [await member(make_client, login, f"{x}@g.nsu.ru") for x in "abc"]
    home = (await owner.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    assert (await join(mate, "NOPE2345")).json()["error"]["code"] == "INVITE_INVALID"

    inv = await invite(owner, home["id"])
    assert (await owner.request("DELETE", f"/api/homes/{home['id']}/invites/{inv['id']}", headers=ORIGIN)).status_code == 204
    assert (await join(mate, inv["code"])).status_code == 404

    inv = await invite(owner, home["id"])
    async with db.begin() as conn:
        await conn.execute(text("UPDATE invites SET expires_at = now() - interval '1 minute'"))
    assert (await join(mate, inv["code"])).status_code == 404
    assert (await owner.get(f"/api/homes/{home['id']}/invites")).json() == []

    await other.post("/api/homes", json=apartment(), headers=ORIGIN)
    inv = await invite(owner, home["id"])
    r = await join(other, inv["code"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_IN_HOME"


async def test_apartment_invite_puts_the_person_in_the_chosen_room_and_they_can_move(make_client, login):
    owner, mate = await member(make_client, login, "a@g.nsu.ru"), await member(make_client, login, "b@g.nsu.ru")
    home = (await owner.post("/api/homes", json=apartment(), headers=ORIGIN)).json()
    big, small = [r["id"] for r in home["rooms"]]
    inv = await invite(owner, home["id"], room_id=small)
    joined = (await join(mate, inv["code"])).json()
    me = next(r for r in joined["residents"] if r["is_you"])
    assert me["room_id"] == small and [r["residents"] for r in joined["rooms"]] == [1, 1]

    # Anyone may change their own room; nothing else about themselves.
    r = await mate.put(f"/api/homes/{home['id']}/residents/{me['user_id']}", json={"room_id": big}, headers=ORIGIN)
    assert [x["residents"] for x in r.json()["rooms"]] == [2, 0]
    r = await mate.put(f"/api/homes/{home['id']}/residents/{me['user_id']}", json={"can_edit": True}, headers=ORIGIN)
    assert r.status_code == 403
    assert await fields(await invite_raw(owner, home["id"], "00000000-0000-0000-0000-000000000000")) == {"room_id": "UNKNOWN_ROOM"}


async def invite_raw(c, home_id, room_id):
    return await c.post(f"/api/homes/{home_id}/invites", json={"room_id": room_id}, headers=ORIGIN)


async def test_rights_can_be_granted_and_someone_always_manages(make_client, login):
    owner, mate = await member(make_client, login, "a@g.nsu.ru", "Аня"), await member(make_client, login, "b@g.nsu.ru", "Боря")
    home = (await owner.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    joined = (await join(mate, (await invite(owner, home["id"]))["code"])).json()
    owner_id, mate_id = [r["user_id"] for r in joined["residents"]]
    url = f"/api/homes/{home['id']}/residents"

    r = await owner.put(f"{url}/{mate_id}", json={"can_photos": True, "can_invites": True}, headers=ORIGIN)
    boria = next(x for x in r.json()["residents"] if x["user_id"] == mate_id)
    assert boria["permissions"] == {"can_edit": False, "can_photos": True, "can_invites": True, "can_residents": False}
    assert (await mate.post(f"/api/homes/{home['id']}/invites", json={}, headers=ORIGIN)).status_code == 201

    # The only manager can't drop the right…
    r = await owner.put(f"{url}/{owner_id}", json={"can_residents": False}, headers=ORIGIN)
    assert r.status_code == 409 and r.json()["error"]["code"] == "LAST_MANAGER"
    # …but can share it, and then step down.
    await owner.put(f"{url}/{mate_id}", json={"can_residents": True}, headers=ORIGIN)
    assert (await owner.put(f"{url}/{owner_id}", json={"can_residents": False}, headers=ORIGIN)).status_code == 200

    # The manager removes a resident; removing yourself goes through "leave".
    r = await mate.request("DELETE", f"{url}/{mate_id}", headers=ORIGIN)
    assert await fields(r) == {"user_id": "USE_LEAVE"}
    r = await mate.request("DELETE", f"{url}/{owner_id}", headers=ORIGIN)
    assert [x["first_name"] for x in r.json()["residents"]] == ["Боря"]
    assert (await owner.get("/api/homes/mine")).json() == {"home": None}


async def test_when_the_manager_leaves_or_deletes_their_account_the_oldest_resident_takes_over(make_client, login):
    owner = await member(make_client, login, "a@g.nsu.ru", "Аня")
    home = (await owner.post("/api/homes", json=dorm(), headers=ORIGIN)).json()
    mates = []
    for i, name in enumerate(("Боря", "Вика")):
        c = await member(make_client, login, f"m{i}@g.nsu.ru", name)
        await join(c, (await invite(owner, home["id"]))["code"])
        mates.append(c)
    boria, vika = mates

    assert (await owner.request("DELETE", "/api/homes/mine/membership", headers=ORIGIN)).status_code == 204
    seen = (await boria.get("/api/homes/mine")).json()["home"]
    assert [x["first_name"] for x in seen["residents"]] == ["Боря", "Вика"]
    assert seen["permissions"]["can_residents"] is True and seen["permissions"]["can_edit"] is True
    assert (await vika.get("/api/homes/mine")).json()["home"]["permissions"]["can_residents"] is False

    # Asking to delete the account hides the person and hands management on right away.
    assert (await boria.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=ORIGIN)).status_code == 204
    seen = (await vika.get("/api/homes/mine")).json()["home"]
    assert [x["first_name"] for x in seen["residents"]] == ["Вика"] and seen["permissions"]["can_residents"] is True
