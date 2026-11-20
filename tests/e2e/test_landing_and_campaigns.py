"""The landing page's header for guests, and poster campaign tags (utm_*) surviving redirects
(js/layout.js, js/pages/index.js, js/routes.js: withCampaign)."""

import re

from playwright.sync_api import Page, expect

from helpers import Site, answer_everything, api, expect_path, log_in, log_out, new_email

UTM = "utm_source=poster&utm_medium=qr&utm_campaign=posters-2026-11&utm_content=test-na-sovmestimost"


# ── Guest header on the landing ─────────────────────────

def test_guest_sees_the_sections_with_log_in_instead_of_account(page: Page):
    page.goto("/")
    nav = page.locator(".site-header .site-nav")
    expect(nav.locator("a")).to_have_text(["Matches", "My home", "Lifestyle"])
    header = page.locator(".site-header")
    expect(header.locator(".row .langsw")).to_be_visible()
    expect(header.locator(".row a.btn[href='/login']")).to_be_visible()
    expect(header.get_by_role("link", name="Account")).to_have_count(0)
    # On a computer the language switch is in the header only.
    expect(page.locator(".site-footer .footer-lang")).to_be_hidden()


def test_guest_on_a_phone_gets_the_tab_bar_and_the_language_switch_in_the_footer(page: Page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto("/")
    tabs = page.locator(".site-header .tabbar")
    expect(tabs.locator("a")).to_have_text(["Matches", "Home", "Lifestyle", "Log in"])
    expect(page.locator(".site-header .row")).to_be_hidden()
    expect(page.locator(".site-footer .footer-lang .langsw")).to_be_visible()


def test_language_switch_in_the_footer_translates_the_header(page: Page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto("/")
    page.locator(".site-footer .langsw button", has_text="RU").click()
    expect(page.locator(".site-header .tabbar a").first).to_have_text("Подборка")


def test_other_public_pages_keep_the_plain_guest_header(page: Page):
    page.goto("/support")
    expect(page.locator(".site-header .site-nav")).to_have_count(0)
    expect(page.locator(".site-header a.btn[href='/login']")).to_be_visible()


def test_a_section_link_goes_through_login_and_back(page: Page, site: Site):
    page.goto("/login")
    email = new_email("nav")
    log_in(page, site, email)
    answer_everything(page)
    api(page, "PUT", "/me", {"intent": "seek_dorm"})
    log_out(page)
    page.context.clear_cookies()
    page.evaluate("localStorage.clear()")  # a guest who has never logged in here sees the landing

    page.goto("/")
    page.locator(".site-header .site-nav a", has_text="Lifestyle").click()
    log_in(page, site, email)
    expect_path(page, "/questionnaire")


# ── Campaign tags through redirects ─────────────────────

def test_utm_tags_follow_a_guest_to_login_and_back(page: Page, site: Site):
    page.goto(f"/compare?{UTM}&other=1")
    expect_path(page, f"/login?{UTM}")  # only the campaign tags come along
    log_in(page, site, new_email("poster"))
    expect_path(page, f"/compare?{UTM}&other=1")


def test_utm_tags_follow_a_logged_in_person_from_the_landing(page: Page, site: Site):
    page.goto("/login")
    log_in(page, site, new_email("poster"))
    answer_everything(page)
    api(page, "PUT", "/me", {"intent": "seek_dorm"})
    page.goto(f"/?{UTM}")
    expect_path(page, f"/feed?kind=dorm&{UTM}")


def test_no_tags_no_query(page: Page):
    page.goto("/compare")
    expect(page).to_have_url(re.compile(r"/login$"))
