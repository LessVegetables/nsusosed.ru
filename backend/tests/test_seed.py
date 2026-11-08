"""Тестовые данные для разработки (нужен Postgres)."""

from app.database import async_session_factory
from app.seed import DEMO_INVITE_TOKEN, Seeder


async def test_seed_gives_a_browsable_world(db, make_client, login):
    async with async_session_factory() as session:
        Seeder(session).fill()
        await session.commit()

    seeker = make_client()
    await login(seeker, "me@g.nsu.ru")
    dorms = (await seeker.get("/api/matches", params={"kind": "dorm", "limit": 50})).json()
    # 15 комнат со свободными местами; скрыты полная, неподтверждённая
    # и комната курильщика (его жёсткое условие против некурящего).
    assert dorms["total"] == 14
    assert dorms["items"][0]["compatibility"]["score"] >= dorms["items"][-1]["compatibility"]["score"]
    everything = (await seeker.get("/api/matches", params={"kind": "dorm", "limit": 50,
                                                            "include_unmatched": "true"})).json()
    assert everything["total"] == 15
    apartments = (await seeker.get("/api/matches", params={"kind": "apartment"})).json()
    assert apartments["total"] == 3

    host = make_client()
    await login(host, "host@g.nsu.ru", situation="host")
    r = await host.post("/api/memberships/join", json={"invite_token": DEMO_INVITE_TOKEN})
    assert r.status_code == 200, r.text
