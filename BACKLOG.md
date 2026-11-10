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

- **Phone menu.** On phones the header shows only the Account button; "My home" and "Questionnaire" are
  reachable from the desktop header and by direct link. A bottom bar comes with the feed (stage 5).
- **Umami session recorder vs. the CSP.** `stat.gehrman.me/recorder.js` tries to apply inline styles, which
  the strict CSP blocks, so the console fills with "Applying inline style violates…" errors. Harmless to the
  site, but recordings may be incomplete. Either drop the recorder or relax `style-src-attr` for it.
- **Dorm coordinates** are empty in `dorms.json`, so dorm listings have no map point yet.
- **`/room?id=…`** (linked from the "this room is already listed" message) arrives in stage 5.

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
