"""Where people land after logging in, from each way into the site (js/routes.js, js/layout.js)."""

import re

from playwright.sync_api import Page, expect

from helpers import Site, answer_everything, api, expect_path, finish_questionnaire, log_in, log_out, new_email


def returning_person(page: Page, site: Site, intent: str) -> str:
    """Someone who has answered everything and said what they're here for, logged out again."""
    email = new_email("back")
    page.goto("/login")
    log_in(page, site, email)
    answer_everything(page)
    api(page, "PUT", "/me", {"intent": intent})
    log_out(page)
    return email


# ── The usual ways in ───────────────────────────────────

def test_new_person_from_the_login_page_starts_with_the_questionnaire(page: Page, site: Site):
    page.goto("/login")
    log_in(page, site, new_email())
    expect_path(page, "/questionnaire")


def test_returning_person_from_the_login_page_goes_to_their_page(page: Page, site: Site):
    email = returning_person(page, site, "seek_apt")
    page.goto("/login")
    log_in(page, site, email)
    expect_path(page, "/feed?kind=apartment")


# ── Back to the page that was opened ────────────────────

def test_guest_on_a_private_page_comes_back_to_it(page: Page, site: Site):
    page.goto("/account")
    log_in(page, site, new_email())
    expect_path(page, "/account")


def test_the_query_survives_the_login_detour(page: Page, site: Site):
    email = returning_person(page, site, "seek_dorm")
    page.goto("/feed?kind=apartment")
    log_in(page, site, email)
    expect_path(page, "/feed?kind=apartment")


def test_a_remembered_page_is_used_once(page: Page, site: Site):
    page.goto("/account")
    email = new_email()
    log_in(page, site, email)
    log_out(page)
    page.goto("/login")
    log_in(page, site, email)
    expect_path(page, "/questionnaire")


# ── Compare ─────────────────────────────────────────────

def test_guest_on_compare_comes_back_takes_the_questionnaire_and_returns(page: Page, site: Site):
    page.goto("/compare")
    log_in(page, site, new_email())
    expect_path(page, "/compare")

    cta = page.locator("#quiz-cta")
    expect(cta).to_be_visible()
    expect(page.locator("#share-url")).to_have_value(re.compile(r"/compare#code=\w+$"))
    cta.locator("a").click()

    finish_questionnaire(page)
    expect_path(page, "/compare")
    expect(page.locator("#share-url")).to_have_value(re.compile(r"/compare#code="))
    expect(cta).to_be_hidden()
    assert api(page, "GET", "/me")["intent"] == "compare"


def test_compare_page_has_no_questionnaire_button_once_it_is_done(page: Page, site: Site):
    email = returning_person(page, site, "seek_dorm")
    page.goto("/compare")
    log_in(page, site, email)
    expect_path(page, "/compare")
    expect(page.locator("#share-url")).to_have_value(re.compile(r"/compare#code="))
    expect(page.locator("#quiz-cta")).to_be_hidden()


def test_friends_compare_link_joins_then_questionnaire_then_back(page: Page, new_page, site: Site):
    # Masha makes a link.
    page.goto("/compare")
    log_in(page, site, new_email("masha"), first="Masha")
    link = page.locator("#share-url")
    expect(link).to_have_value(re.compile(r"/compare#code=\w+$"))
    url = link.input_value()

    # Petya opens it without an account.
    petya = new_page()
    petya.goto(url)
    log_in(petya, site, new_email("petya"), first="Petya")
    # Joined straight away, then off to the questionnaire, which says who asked.
    expect_path(petya, "/questionnaire")
    expect(petya.locator("#together-joined")).to_contain_text("Masha")
    assert "code" not in petya.url, "the code is kept out of the address bar"

    # Masha already sees Petya's progress.
    page.reload()
    expect(page.locator("#groups")).to_contain_text("Petya")

    finish_questionnaire(petya)
    expect_path(petya, "/compare")
    expect(petya.locator("#groups")).to_contain_text("Masha")
    assert api(petya, "GET", "/me")["intent"] == "compare"


# ── Invite ──────────────────────────────────────────────

def test_invite_link_waits_for_the_questionnaire_then_joins(page: Page, new_page, site: Site):
    # A host lists a dorm room and makes an invite (through the API: the form has its own tests).
    page.goto("/login")
    log_in(page, site, new_email("host"), first="Olya")
    api(page, "PUT", "/me/contacts", {"contacts": [{"type": "telegram", "value": "@olya_e2e_nsu"}]})
    home = api(page, "POST", "/homes", {
        "kind": "dorm", "building": "6", "room_label": "100б", "description": "Тихая комната",
        "rooms": [{"gender": "f", "capacity": 2, "free_places": 1, "emoji": "🐶🍕🚀", "sunlight": "sunny", "area_m2": 12}]})
    invite = api(page, "POST", f"/homes/{home['id']}/invites", {})

    guest = new_page()
    guest.goto(invite["url"])
    log_in(guest, site, new_email("mate"))
    expect_path(guest, "/questionnaire")  # the questionnaire comes first; the invite waits
    finish_questionnaire(guest)
    expect_path(guest, "/join")
    assert api(guest, "GET", "/me")["intent"] == "join"
