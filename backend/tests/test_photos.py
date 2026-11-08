"""Фото жилья (нужен Postgres)."""

import io
from pathlib import Path
from PIL import Image
from app.config import settings
from tests.test_api import DORM, invite


def jpeg_with_gps(width=3000, height=2000) -> bytes:
    img = Image.new("RGB", (width, height), (200, 100, 50))
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: повернуть на 90°
    exif[0x8825] = {1: "N", 2: (55.0, 6.0, 0.0), 3: "E", 4: (83.0, 6.0, 0.0)}  # GPS
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif)
    return out.getvalue()


def png_with_alpha() -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(out, "PNG")
    return out.getvalue()


def media_path(url: str) -> Path:
    return Path(settings.media_dir) / url.removeprefix(settings.media_url + "/")


async def upload(client, listing_id, data: bytes, name="photo.jpg"):
    return await client.post(f"/api/listings/{listing_id}/photos", files={"file": (name, data, "image/jpeg")})


async def test_upload_strips_metadata_and_resizes(make_client, login):
    owner, cand = make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(cand, "cand@g.nsu.ru")
    listing = (await owner.post("/api/listings", json=DORM)).json()

    r = await upload(owner, listing["id"], jpeg_with_gps())
    assert r.status_code == 201, r.text
    photo = r.json()["photos"][0]
    # Повёрнуто по EXIF (3000x2000 → 2000x3000) и уменьшено до 1600 по длинной стороне.
    assert (photo["width"], photo["height"]) == (1067, 1600)
    with Image.open(media_path(photo["url"])) as saved:
        assert saved.format == "JPEG" and saved.size == (1067, 1600)
        assert not saved.getexif() and "exif" not in saved.info

    r = await upload(owner, listing["id"], png_with_alpha(), "a.png")
    assert r.status_code == 201
    first, second = [p["id"] for p in r.json()["photos"]]

    item = (await cand.get("/api/matches", params={"kind": "dorm"})).json()["items"][0]
    assert item["cover_url"] == photo["url"]
    detail = (await cand.get(f"/api/listings/{listing['id']}")).json()
    assert [p["id"] for p in detail["photos"]] == [first, second]

    r = await owner.put(f"/api/listings/{listing['id']}/photos/order", json={"photo_ids": [second, first]})
    assert [p["id"] for p in r.json()["photos"]] == [second, first]
    r = await owner.put(f"/api/listings/{listing['id']}/photos/order", json={"photo_ids": [second]})
    assert r.status_code == 422

    r = await owner.delete(f"/api/listings/{listing['id']}/photos/{second}")
    assert [p["id"] for p in r.json()["photos"]] == [first]
    assert media_path(photo["url"]).exists()

    # Ушёл последний жилец — жильё и все его файлы удалены.
    assert (await owner.delete("/api/membership")).status_code == 204
    assert not media_path(photo["url"]).parent.exists()


async def test_upload_rules(make_client, login):
    owner, resident = make_client(), make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    await login(resident, "res@g.nsu.ru", situation="host")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    await resident.post("/api/memberships/join", json={"invite_token": await invite(owner, listing["id"])})

    r = await upload(resident, listing["id"], png_with_alpha())
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_ADMIN"
    r = await upload(owner, listing["id"], b"GIF89a not really")
    assert r.status_code == 415 and r.json()["error"]["code"] == "PHOTO_BAD_TYPE"
    r = await upload(owner, listing["id"], b"x" * (10 * 1024 * 1024 + 1))
    assert r.status_code == 413 and r.json()["error"]["code"] == "PHOTO_TOO_LARGE"
    r = await owner.post(f"/api/listings/{listing['id']}/photos", json={})
    assert r.status_code == 415

    for _ in range(10):
        assert (await upload(owner, listing["id"], png_with_alpha())).status_code == 201
    r = await upload(owner, listing["id"], png_with_alpha())
    assert r.status_code == 409 and r.json()["error"]["code"] == "TOO_MANY_PHOTOS"


def listing_files(listing_id: str) -> set[str]:
    folder = Path(settings.media_dir) / "listings" / listing_id
    return {p.name for p in folder.iterdir()} if folder.is_dir() else set()


async def test_failed_upload_leaves_no_file(make_client, login, monkeypatch):
    owner = make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    listing = (await owner.post("/api/listings", json=DORM)).json()

    # Файл уже записан, но запрос падает до коммита: строки в базе нет — и файла быть не должно.
    async def boom(*args, **kwargs):
        raise RuntimeError("after the file was written")
    monkeypatch.setattr("app.routers.listings.to_home_dto", boom)
    r = await upload(owner, listing["id"], png_with_alpha())
    assert r.status_code == 500
    assert listing_files(listing["id"]) == set()


async def test_failed_delete_keeps_the_file(make_client, login, monkeypatch):
    owner = make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    photo = (await upload(owner, listing["id"], png_with_alpha())).json()["photos"][0]

    async def boom(*args, **kwargs):
        raise RuntimeError("before commit")
    monkeypatch.setattr("app.routers.listings.to_home_dto", boom)
    r = await owner.delete(f"/api/listings/{listing['id']}/photos/{photo['id']}")
    assert r.status_code == 500
    # Удаление откатилось — фото осталось и в базе, и на диске.
    assert media_path(photo["url"]).exists()


async def test_sweep_removes_old_orphans_only(db, make_client, login):
    import os
    import time
    from app.database import async_session_factory
    from app.services.photo_service import sweep_orphan_folders

    owner = make_client()
    await login(owner, "owner@g.nsu.ru", situation="host")
    listing = (await owner.post("/api/listings", json=DORM)).json()
    photo = (await upload(owner, listing["id"], png_with_alpha())).json()["photos"][0]
    folder = media_path(photo["url"]).parent
    old_orphan, fresh_orphan = folder / "old.jpg", folder / "fresh.jpg"
    old_orphan.write_bytes(b"x")
    fresh_orphan.write_bytes(b"x")
    two_hours_ago = time.time() - 7200
    os.utime(old_orphan, (two_hours_ago, two_hours_ago))
    os.utime(media_path(photo["url"]), (two_hours_ago, two_hours_ago))

    async with async_session_factory() as session:
        await sweep_orphan_folders(session)
    assert listing_files(listing["id"]) == {media_path(photo["url"]).name, "fresh.jpg"}
