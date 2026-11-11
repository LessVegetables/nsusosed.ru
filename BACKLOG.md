# Backlog

Things we decided to do later. Not ordered. Remove an item when it's done.

## Content to verify

- **"How to open your DMs" instructions** (account page, `contact.*.howto` in `frontend/js/i18n/*.js`).
  The Telegram, VK, Instagram, Snapchat and WeChat menu paths were written from memory; the Max one is
  deliberately vague because its settings weren't known. Check each against the real app, in all three
  languages, and fix the wording.
- **Dorms and faculties** (`backend/app/config/dorms.json`, `faculties.json`). Filled in from nsu.ru on
  2026-11-10, but that page is known to be not fully accurate. Get the real faculty → dorm mapping and the
  full dorm list before launch. Coordinates are still empty (stage 3).
- **Privacy policy** (`frontend/privacy.html`). Written as if the whole pilot is built. Still marked as a
  draft: the final legal text needs a review before launch.

## Known gaps

- **Umami session recorder vs. the CSP.** `stat.gehrman.me/recorder.js` tries to apply inline styles, which
  the strict CSP blocks, so the console fills with "Applying inline style violates…" errors. Harmless to the
  site, but recordings may be incomplete. Either drop the recorder or relax `style-src-attr` for it.
- **Dorm coordinates** in `dorms.json` were looked up by address in OpenStreetMap and not checked by a
  person. 8/1 and 8/2 share one address, so they share one point. Check each pin on a room page.

- **`intstruction.md` and `screenshots/`** describe the MVP. Rewrite or delete them before showing the
  repo to anyone as documentation of the pilot.
- **CI does not run the backend tests** (they need Postgres). Add a job with a Postgres service.
- **A request without an `Origin` header skips the Origin check** (`backend/app/utils/deps.py`). Browsers
  send it on every POST/PUT/DELETE and the cookie is SameSite=Lax, so this only lets non-browser clients
  through; tighten it if that ever matters.
- **Feed scoring loads every home of a kind** and scores it in Python. Fine for a pilot; needs paging
  and precomputed scores at scale.

## Pages to rework

- **Landing page.** The current one is a first cut; to be redone.

## Product

- **Bot check before "get contact info"** (Cloudflare or something that works reliably in Russia). The
  endpoint is a POST so a challenge can be added in front of it.
- **Stale listings and stale accounts.** Not a pilot problem; no expiry rules yet.
- **Questionnaire length.** v1 has 20 questions; it may be too deep and too long. Revisit after the pilot.
- **Hidden-answer retention.** The questionnaire research says to delete hidden raw answers after a
  matching season; that conflicts with re-fitting the weights. Decide together with the stale-data rules.
- **Self-hosted Chinese font.** Chinese text uses the device's own font; Noto Sans SC is not shipped.
- **Dorm bank.** Long term: every dorm building with room layouts and photos, so listing a room (or
  managing a dorm) starts from known data.
