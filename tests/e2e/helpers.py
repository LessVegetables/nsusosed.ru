"""What the browser tests share: the running site, logging in, calling the API as someone."""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from playwright.sync_api import Page, expect


class Site:
    """The running site: its address and the API log the login codes are written to."""

    def __init__(self, url: str, api_log: Path):
        self.url = url
        self.api_log = api_log

    def _codes(self, email: str) -> list[str]:
        return re.findall(rf"To: {re.escape(email)} \| Code: (\d+)", self.api_log.read_text(errors="replace"))

    def next_code(self, email: str, seen: int, timeout: float = 10) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            codes = self._codes(email)
            if len(codes) > seen:
                return codes[-1]
            time.sleep(0.1)
        raise AssertionError(f"no login code for {email} in the API log")



def new_email(name: str = "e2e") -> str:
    return f"{name}.{uuid.uuid4().hex[:10]}@g.nsu.ru"


def expect_path(page: Page, path: str) -> None:
    """The page ends up at `path` (query included). Waits: pages send people on by themselves."""
    expect(page).to_have_url(re.compile(r"^https?://[^/]+" + re.escape(path) + "$"))


def log_in(page: Page, site: Site, email: str, first: str = "Ann", last: str = "Test") -> None:
    """Go through the login page that is open now: email, name (first login only), code."""
    expect(page).to_have_url(re.compile(r"/login(\?.*)?$"))  # campaign tags may come along
    seen = len(site._codes(email))
    page.locator("#email").fill(email)
    page.locator("#privacy").check()
    page.locator("#step-email button[type=submit]").click()
    code = site.next_code(email, seen)
    # The name step for a new account, straight to the code for a known one.
    page.locator("#step-name:not([hidden]), #step-code:not([hidden])").first.wait_for()
    if page.locator("#step-name").is_visible():
        page.locator("#first-name").fill(first)
        page.locator("#last-name").fill(last)
        page.locator("#step-name button[type=submit]").click()
    page.locator("#code input").first.wait_for(state="visible")
    page.locator("#code input").first.press_sequentially(code)
    # The last digit sends the code; the page then leaves /login.
    page.wait_for_url(lambda url: "/login" not in url)


def api(page: Page, method: str, path: str, body: dict | None = None):
    """Call the API as the person logged in on this page (same origin, their cookie)."""
    result = page.evaluate(
        """async ([method, path, body]) => {
          const r = await fetch('/api' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {},
            body: body ? JSON.stringify(body) : undefined });
          return { status: r.status, body: r.status === 204 ? null : await r.json() };
        }""",
        [method, path, body],
    )
    assert result["status"] < 400, f"{method} {path}: {result}"
    return result["body"]


def answer_everything(page: Page, gender: str = "f") -> None:
    """Fill the questionnaire through the API (the first option everywhere); "Done" is still to click."""
    meta = api(page, "GET", "/meta")
    api(page, "PUT", "/me", {"gender": gender, "is_adult": True, "faculty": meta["faculties"][0]["id"]})
    quiz = api(page, "GET", "/questionnaire")
    answers = {q["id"]: 0 if q["type"] == "single" else [0] for q in quiz["questions"]}
    saved = api(page, "PUT", "/questionnaire", {"version": quiz["version"], "answers": answers, "replace": True})
    assert saved["complete"], saved.get("missing")


def finish_questionnaire(page: Page, gender: str = "f") -> None:
    """On the questionnaire page: answer everything, reload so the page sees it, press Done."""
    expect(page).to_have_url(re.compile(r"/questionnaire$"))
    answer_everything(page, gender)
    page.reload()
    # The questions are drawn in the same step that wires up "Done": clicking any earlier sends
    # the form the plain HTML way (to /questionnaire?) and the page goes nowhere.
    page.locator("#blocks [data-question]").first.wait_for()
    page.locator("#quiz button[type=submit]").click()
    page.wait_for_url(lambda url: "/questionnaire" not in url)


def log_out(page: Page) -> None:
    api(page, "POST", "/auth/logout")
