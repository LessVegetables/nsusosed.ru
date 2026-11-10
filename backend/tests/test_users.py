"""Account fields and the reference lists (needs Postgres)."""

ORIGIN = {"Origin": "https://testserver"}


async def test_update_is_partial_and_validated(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    r = await c.put("/api/me", json={"gender": "f", "faculty": "mmf", "is_adult": True,
                                     "intent": "seek_dorm", "language": "zh"}, headers=ORIGIN)
    assert r.status_code == 200, r.text
    r = await c.put("/api/me", json={"bio": "  привет  "}, headers=ORIGIN)
    me = r.json()
    assert (me["gender"], me["faculty"], me["is_adult"], me["intent"], me["language"], me["bio"]) == \
        ("f", "mmf", True, "seek_dorm", "zh", "привет")
    assert me["first_name"] == "Иван"

    for bad, field in [({"faculty": "hogwarts"}, "faculty"), ({"language": "de"}, "language"),
                       ({"gender": "x"}, "gender"), ({"intent": "lurk"}, "intent"),
                       ({"first_name": "   "}, "first_name"), ({"bio": "x" * 501}, "bio")]:
        r = await c.put("/api/me", json=bad, headers=ORIGIN)
        assert r.status_code == 422 and field in r.json()["error"]["fields"], bad


async def test_me_requires_a_session(make_client):
    assert (await make_client().get("/api/me")).status_code == 401


async def test_meta_lists_are_public_and_consistent(make_client):
    meta = (await make_client().get("/api/meta")).json()
    faculty_ids = {f["id"] for f in meta["faculties"]}
    assert {"mmf", "fen", "med"} <= faculty_ids
    assert all({"ru", "en", "zh"} <= f.keys() for f in meta["faculties"])
    assert len({d["id"] for d in meta["dorms"]}) == len(meta["dorms"])
    assert all(set(d["faculties"]) <= faculty_ids for d in meta["dorms"])
