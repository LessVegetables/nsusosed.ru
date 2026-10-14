"""Отправка писем через Postbox: подпись SigV4 и формат запроса SES v2."""

from __future__ import annotations
import json
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.services import email_service
from app.utils.sigv4 import sign_headers

# Ключ-пример из документации AWS. Ожидаемая подпись посчитана botocore
# (botocore.auth.SigV4Auth) для тех же запроса, ключа и времени.
KEY_ID = "AKIDEXAMPLE"
SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"


def test_sigv4_matches_botocore():
    headers = sign_headers(
        "POST", "https://postbox.cloud.yandex.net/v2/email/outbound-emails",
        {"Content-Type": "application/json"}, b'{"FromEmailAddress":"noreply@example.com"}',
        access_key_id=KEY_ID, secret_access_key=SECRET, region="ru-central1", service="ses",
        now=datetime(2026, 10, 14, 12, 34, 56, tzinfo=timezone.utc),
    )
    assert headers["X-Amz-Date"] == "20261014T123456Z"
    assert headers["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261014/ru-central1/ses/aws4_request, "
        "SignedHeaders=content-type;host;x-amz-date, "
        "Signature=1f2e69efea0c8305d0a9c0a3bf777dc8f2312a934e69979d183eeb27904bc97b"
    )


def _postbox_mode(monkeypatch, handler):
    monkeypatch.setattr(settings, "email_mode", "postbox")
    monkeypatch.setattr(settings, "postbox_access_key_id", KEY_ID)
    monkeypatch.setattr(settings, "postbox_secret_access_key", SECRET)
    monkeypatch.setattr(settings, "postbox_sender_email", "noreply@codes.example.com")
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        email_service.httpx, "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


async def test_send_otp_email_request(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json={"MessageId": "m-1"})

    _postbox_mode(monkeypatch, handler)
    assert await email_service.send_otp_email("ivan@g.nsu.ru", "123456") is True

    req = seen["request"]
    assert req.method == "POST"
    assert str(req.url) == "https://postbox.cloud.yandex.net/v2/email/outbound-emails"
    assert req.headers["Authorization"].startswith(
        f"AWS4-HMAC-SHA256 Credential={KEY_ID}/"
    )
    assert "/ru-central1/ses/aws4_request" in req.headers["Authorization"]

    body = json.loads(req.content)
    assert body["FromEmailAddress"] == "noreply@codes.example.com"
    assert body["Destination"] == {"ToAddresses": ["ivan@g.nsu.ru"]}
    simple = body["Content"]["Simple"]
    assert simple["Subject"]["Data"] == "Код подтверждения nsusosed"
    assert "123456" in simple["Body"]["Text"]["Data"]
    assert "123456" in simple["Body"]["Html"]["Data"]

    # Подпись должна сходиться с телом, которое реально ушло.
    resigned = sign_headers(
        "POST", str(req.url), {"Content-Type": "application/json"}, req.content,
        access_key_id=KEY_ID, secret_access_key=SECRET, region="ru-central1", service="ses",
        now=datetime.strptime(req.headers["X-Amz-Date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc),
    )
    assert req.headers["Authorization"] == resigned["Authorization"]


async def test_send_otp_email_postbox_error(monkeypatch):
    _postbox_mode(monkeypatch, lambda request: httpx.Response(403, text="SignatureDoesNotMatch"))
    assert await email_service.send_otp_email("ivan@g.nsu.ru", "123456") is False
