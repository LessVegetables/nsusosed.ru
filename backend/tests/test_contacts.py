"""Contact methods, avatar and the email language (needs Postgres)."""

import io
from pathlib import Path
import pytest
from PIL import Image
from app.config import settings
from app.services.email_service import otp_email
from app.utils.contact import normalize_contact

ORIGIN = {"Origin": "https://testserver"}


@pytest.mark.parametrize("kind, raw, expected", [
    ("phone", "8 (913) 123-45-67", "+79131234567"),
    ("phone", "+7 913 123 45 67", "+79131234567"),
    ("phone", "9131234567", "+79131234567"),
    ("telegram", "https://t.me/Some_User", "Some_User"),
    ("telegram", "@some_user", "some_user"),
    ("vk", "vk.com/id12345", "id12345"),
    ("vk", "https://m.vk.com/durov?from=x", "durov"),
    ("instagram", "@some.one", "some.one"),
    ("snapchat", "snapchat.com/add/some-one", "some-one"),
    ("wechat", "wxid_abc123", "wxid_abc123"),
    ("max", "8 913 123 45 67", "+79131234567"),
])
def test_contacts_are_normalized(kind, raw, expected):
    assert normalize_contact(kind, raw) == (expected, None)


@pytest.mark.parametrize("kind, raw, reason", [
    ("phone", "12345", "INVALID_PHONE"),
    ("phone", "+1 415 555 0100", "INVALID_PHONE"),
    ("telegram", "ab", "INVALID_TELEGRAM"),
    ("vk", "bad name", "INVALID_VK"),
    ("wechat", "1abc", "INVALID_WECHAT"),
    ("whatsapp", "+79131234567", "INVALID_CHOICE"),
    ("telegram", "  ", "REQUIRED"),
])
def test_bad_contacts_are_rejected(kind, raw, reason):
    assert normalize_contact(kind, raw) == (None, reason)


async def put_contacts(c, *pairs):
    return await c.put("/api/me/contacts", headers=ORIGIN,
                       json={"contacts": [{"type": t, "value": v} for t, v in pairs]})


async def test_contacts_need_a_primary_method(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    assert (await c.get("/api/me")).json()["contacts"] == []

    r = await put_contacts(c, ("wechat", "wxid_abc123"))
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"contacts": "NEED_PRIMARY"}

    r = await put_contacts(c, ("wechat", "wxid_abc123"), ("telegram", "@some_user"))
    assert r.status_code == 200, r.text
    assert r.json()["contacts"] == [
        {"type": "wechat", "value": "wxid_abc123", "url": None},
        {"type": "telegram", "value": "some_user", "url": "https://t.me/some_user"},
    ]

    # The list is replaced as a whole; an empty one is allowed.
    r = await put_contacts(c, ("phone", "89131234567"))
    assert [x["value"] for x in r.json()["contacts"]] == ["+79131234567"]
    assert (await put_contacts(c)).json()["contacts"] == []


async def test_contact_errors_point_at_the_item(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    r = await put_contacts(c, ("phone", "89131234567"), ("telegram", "x"), ("phone", "89130000000"), ("fax", "1"))
    assert r.json()["error"]["fields"] == {
        "contacts.1.value": "INVALID_TELEGRAM", "contacts.2.type": "DUPLICATE_TYPE", "contacts.3.type": "INVALID_CHOICE"}
    assert (await c.get("/api/me")).json()["contacts"] == []


def picture(size=(900, 600), fmt="PNG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(out, fmt)
    return out.getvalue()


async def test_avatar_is_reencoded_square_and_replaced(make_client, login):
    c = make_client()
    await login(c, "s@g.nsu.ru")
    folder = Path(settings.media_dir) / "avatars"

    r = await c.post("/api/me/avatar", headers=ORIGIN, files={"file": ("me.png", picture(), "image/png")})
    assert r.status_code == 200, r.text
    first = folder / r.json()["avatar_url"].rsplit("/", 1)[1]
    with Image.open(first) as img:
        assert img.format == "JPEG" and img.size == (512, 512)

    r = await c.post("/api/me/avatar", headers=ORIGIN, files={"file": ("me.png", picture((100, 300)), "image/png")})
    second = folder / r.json()["avatar_url"].rsplit("/", 1)[1]
    with Image.open(second) as img:
        assert img.size == (100, 100)  # never scaled up
    assert not first.exists() and second.exists()

    r = await c.post("/api/me/avatar", headers=ORIGIN, files={"file": ("x.txt", b"not a picture", "text/plain")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "PHOTO_BAD_TYPE"

    r = await c.request("DELETE", "/api/me/avatar", headers=ORIGIN)
    assert r.json()["avatar_url"] is None and not second.exists()


async def test_code_email_follows_the_page_language(make_client, codes):
    c = make_client()
    await c.post("/api/auth/request-code", json={"email": "s@g.nsu.ru", "privacy_accepted": True, "language": "zh"})
    assert codes["lang:s@g.nsu.ru"] == "zh"
    subject, text, html = otp_email("123456", "en")
    assert subject == "123456 is your code" and "10 minutes" in text and 'lang="en"' in html
    assert otp_email("123456", "zh")[0].startswith("123456") and "10 分钟" in otp_email("123456", "zh")[1]
