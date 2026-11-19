"""Browser tests: a real Chromium against the real API and frontend/dev_server.py, both started here.

    E2E_DATABASE_URL=postgresql+asyncpg://… pytest tests/e2e

The database is wiped (every table emptied) when the run starts, so give it one of its own.
Login codes are read from the API's log (EMAIL_MODE=log). See tests/README.md.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from helpers import Site

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
DATABASE_URL = os.environ.get("E2E_DATABASE_URL")

expect.set_options(timeout=10_000)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(url: str, proc: subprocess.Popen, log: Path, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{url} exited early:\n{log.read_text()[-3000:]}")
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"{url} did not come up in {timeout}s:\n{log.read_text()[-3000:]}")


async def _wipe(url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        tables = [r["tablename"] for r in await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")]
        if tables:
            await conn.execute(f"TRUNCATE {', '.join(tables)} CASCADE")
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def site(tmp_path_factory) -> Site:
    if not DATABASE_URL:
        pytest.skip("E2E_DATABASE_URL is not set")
    tmp = tmp_path_factory.mktemp("e2e")
    api_port, site_port = _free_port(), _free_port()
    url = f"http://localhost:{site_port}"
    # Real env vars win over backend/.env, so a developer's own settings don't leak in.
    env = {
        **os.environ,
        "DATABASE_URL": DATABASE_URL,
        "PUBLIC_ORIGIN": url,
        "EMAIL_MODE": "log",
        "BETA_EMAILS": "",
        "MEDIA_DIR": str(tmp / "media"),
        # Every test logs in from the same address, several times.
        "OTP_MAX_REQUESTS_PER_HOUR": "1000",
        "OTP_RESEND_COOLDOWN_SECONDS": "0",
        "OTP_MAX_FAILED_VERIFIES_PER_HOUR": "1000",
        "AUTH_IP_MAX_REQUESTS": "100000",
    }
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
    # Playwright's sync API keeps an event loop running in this thread, so the wipe gets its own.
    with ThreadPoolExecutor(1) as pool:
        pool.submit(asyncio.run, _wipe(DATABASE_URL)).result()

    api_log, site_log = tmp / "api.log", tmp / "site.log"
    with open(api_log, "w") as a, open(site_log, "w") as s:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(api_port)],
                               cwd=BACKEND, env=env, stdout=a, stderr=subprocess.STDOUT)
        web = subprocess.Popen([sys.executable, str(REPO / "frontend" / "dev_server.py"), "--port", str(site_port),
                                "--api", f"http://127.0.0.1:{api_port}"], env=env, stdout=s, stderr=subprocess.STDOUT)
    try:
        _wait_up(f"http://127.0.0.1:{api_port}/api/health", api, api_log)
        _wait_up(f"{url}/login", web, site_log)
        yield Site(url, api_log)
    finally:
        for proc in (web, api):
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()


# pytest-playwright: every page opens relative to the running site, in English.
@pytest.fixture(scope="session")
def base_url(site: Site) -> str:
    return site.url


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, base_url):
    return {**browser_context_args, "base_url": base_url, "locale": "en-US"}


@pytest.fixture
def new_page(browser: Browser, browser_context_args):
    """A second (third, …) person: a page in a browser context of its own."""
    contexts = []

    def make() -> Page:
        ctx = browser.new_context(**browser_context_args)
        contexts.append(ctx)
        return ctx.new_page()

    yield make
    for ctx in contexts:
        ctx.close()
