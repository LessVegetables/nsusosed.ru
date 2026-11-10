"""Общие фикстуры.

Тесты с базой нужны настоящий Postgres: TEST_DATABASE_URL=postgresql+asyncpg://...
(отдельная БД — её таблицы очищаются перед каждым тестом). Без переменной такие
тесты пропускаются, чистые юнит-тесты работают всегда.
"""

from __future__ import annotations
import itertools
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# До импорта app: настройки читаются при импорте.
os.environ.setdefault("EMAIL_MODE", "log")
# The tests assert the production limits, whatever a developer's .env relaxes them to.
os.environ.update(OTP_MAX_REQUESTS_PER_HOUR="5", OTP_RESEND_COOLDOWN_SECONDS="60",
                  OTP_MAX_FAILED_VERIFIES_PER_HOUR="10", AUTH_IP_MAX_REQUESTS="20", AUTH_IP_WINDOW_SECONDS="600")
os.environ.setdefault("PUBLIC_ORIGIN", "https://testserver")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="nsusosed-media-"))
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
TABLES = ["auth_events", "otp_codes", "sessions", "user_contacts", "questionnaire_responses", "users"]


@pytest.fixture(scope="session")
def migrated():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL не задан")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True,
                   env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL})


@pytest.fixture
async def db(migrated):
    from app.database import engine
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    yield engine
    # Пул привязан к event loop теста — закрываем его, следующий тест создаст свой.
    await engine.dispose()


@pytest.fixture
def codes(monkeypatch) -> dict:
    """Перехватывает письма с кодами: {email: code}."""
    sent: dict = {}

    async def fake_send(email: str, code: str, lang: str = "ru") -> bool:
        sent[email] = code
        sent["lang:" + email] = lang
        return True

    monkeypatch.setattr("app.services.auth_service.send_otp_email", fake_send)
    return sent


_ips = itertools.count(1)


@pytest.fixture
async def make_client(db):
    """Фабрика клиентов. У каждого свой IP, чтобы не упираться в лимит по IP."""
    from app.main import app
    clients = []

    def factory(ip: str | None = None) -> httpx.AsyncClient:
        n = next(_ips)
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False,
                                        client=(ip or f"10.{n // 250 % 250}.{n % 250}.1", 1))
        c = httpx.AsyncClient(transport=transport, base_url="https://testserver")
        clients.append(c)
        return c

    yield factory
    for c in clients:
        await c.aclose()


@pytest.fixture
def login(codes):
    """Log in with an emailed code; a first login also gives the name."""
    async def _login(client: httpx.AsyncClient, email: str, *, first_name: str = "Иван",
                     last_name: str = "Петров", language: str | None = None) -> dict:
        r = await client.post("/api/auth/request-code", json={"email": email, "privacy_accepted": True})
        assert r.status_code == 200, r.text
        body = {"email": email, "code": codes[email]}
        if r.json()["is_new"]:
            body |= {"first_name": first_name, "last_name": last_name}
        if language:
            body["language"] = language
        r = await client.post("/api/auth/verify-code", json=body)
        assert r.status_code == 200, r.text
        return r.json()
    return _login
