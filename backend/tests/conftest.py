"""Общие фикстуры.

Тесты с базой нужны настоящий Postgres: TEST_DATABASE_URL=postgresql+asyncpg://...
(отдельная БД — её таблицы очищаются перед каждым тестом). Без переменной такие
тесты пропускаются, чистые юнит-тесты (test_matching.py) работают всегда.
"""

from __future__ import annotations
import itertools
import os
import subprocess
import sys
from pathlib import Path

# До импорта app: настройки читаются при импорте.
os.environ.setdefault("EMAIL_MODE", "log")
os.environ.setdefault("PUBLIC_ORIGIN", "https://testserver")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
QUESTION_KEYS = ["sleep", "noise", "cleanliness", "guests", "smoking", "alcohol", "study", "airing", "temperature"]
TABLES = ["auth_events", "otp_codes", "sessions", "memberships", "listings", "profiles", "users"]


def answers(**overrides) -> dict:
    """Анкета: все ответы 2 (курение 0), важность 5, без жёстких условий."""
    base = {k: {"value": 0 if k == "smoking" else 2, "importance": 5, "hard": False, "allowed": []}
            for k in QUESTION_KEYS}
    for key, item in overrides.items():
        base[key] = {**base[key], **item}
    return base


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

    async def fake_send(email: str, code: str) -> bool:
        sent[email] = code
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
    """Войти по коду и (по умолчанию) заполнить анкету."""
    async def _login(client: httpx.AsyncClient, email: str, *, profile: dict | None = None,
                     budget: int | None = 30000, situation: str = "looking", fill_profile: bool = True):
        r = await client.post("/api/auth/request-code", json={"email": email, "privacy_accepted": True})
        assert r.status_code == 200, r.text
        r = await client.post("/api/auth/verify-code", json={"email": email, "code": codes[email]})
        assert r.status_code == 200, r.text
        if fill_profile:
            r = await client.put("/api/profile", json={
                "expected_version": 0, "situation": situation, "budget_max_rub": budget,
                "answers": profile or answers()})
            assert r.status_code == 200, r.text
    return _login
