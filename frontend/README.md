# nsusosed — frontend

Plain HTML, CSS and JavaScript modules. **No framework, no build step, no npm.** What is in this
folder is what the server serves.

## Run it

```bash
# 1. backend (see ../backend/README.md), on port 8000
# 2. the site, on http://localhost:8080
python3 frontend/dev_server.py
```

`dev_server.py` stands in for the production nginx: one origin for pages, `/api` and `/media`,
clean URLs (`/feed` → `feed.html`), real 404s, and the **same Content-Security-Policy** (read from
`deploy/nginx/nsusosed.ru.conf`), so a CSP mistake shows up locally. `--host 0.0.0.0` lets a phone
on the same Wi-Fi open it.

## Layout

| Path | What |
|---|---|
| `*.html` | One file per page. Text in them is the Russian default; scripts translate it |
| `css/nsusosed.css` | **A copy of `design/nsusosed.css`.** Edit the original, then copy |
| `css/pages.css` | Page layout only, inside `@layer pages`. No colors, fonts or sizes |
| `css/fonts.css`, `fonts/` | Self-hosted Rubik and JetBrains Mono (Latin + Cyrillic). Chinese uses the device font |
| `js/api.js` | `fetch` wrapper; every failure is an `ApiError` with the server's `code`, `fields`, `data` |
| `js/errors.js` | `report()` / `reportBug()`: send caught errors to Umami's error tracking |
| `js/analytics.js` | Umami's `data-before-send` hook (classic script): redacts invite codes in error reports |
| `js/i18n.js`, `js/i18n/{ru,en,zh}.js` | Translations: one flat dictionary per language |
| `js/layout.js` | `initPage()`: language, session, header, footer, phone tab bar |
| `js/routes.js` | `homeFor(user)`: where a logged-in person belongs right now |
| `js/map.js` | Leaflet maps and `obfuscate()`, the function that hides an apartment's location |
| `js/autosave.js` | `autosaver()`: pages have no save buttons; a change is sent as soon as it is made |
| `js/compat.js` | How a compatibility result is drawn (percent, badges) |
| `js/pages/*.js` | One script per page |
| `vendor/leaflet/` | Leaflet 1.9.4, vendored (the CSP allows no script CDN) |
| `tools/check_i18n.py` | Checks run before every commit and in CI |

## Rules

Read `design/README.md` first, especially section 15. In short:

- Build from the design system's classes and tokens. A new component goes into `design/nsusosed.css`,
  `design/specimen.html` and the table in `design/README.md`.
- **No inline styles or scripts**: the CSP blocks them. State lives in ARIA attributes.
- **Mark personal data `data-private`.** The analytics session recorder (Umami, `recorder.js`) masks
  what is typed into fields but records rendered text and button states. Its `blockSelector` is
  `[data-private]`: such an element shows up in recordings as an empty box. Put it on anything
  that shows an email, a name, a photo of a person, a contact, an address or map pin, an invite
  code, or questionnaire answers (answers are buttons, so input masking doesn't cover them).
  The privacy policy promises this.
- **Errors go to Umami** (`data-errors` on the tracker, Errors tab at stat.gehrman.me). Uncaught
  exceptions and unhandled rejections are captured on their own, so a catch that can't handle
  something should rethrow it (`if (!(err instanceof ApiError)) throw err;`). A catch that recovers
  on purpose calls `reportBug(err, { where: '…' })` from `js/errors.js`. `api.js` reports 5xx and
  non-JSON answers itself. `js/analytics.js` is the `data-before-send` hook: it redacts invite
  codes and drops errors from browser extensions. Pages carry `data-release="dev"
  data-environment="development"`; the deploy workflow stamps the commit and `production`.
- **No save buttons.** A choice saves when it is made, a text field a moment after typing stops
  (`js/autosave.js`). `/account` and `/home` answer each save with the "Saved" toast (`saved()` in
  `js/ui.js`); the questionnaire saves its draft quietly. Only creating something new (listing a
  place) has a button.
- Every string is in the three dictionaries, in sentence case. `tools/check_i18n.py` fails on a
  missing, extra or unused key.
- Check a 375px-wide screen and a desktop, light and dark, in Russian, English and Chinese.

```bash
python3 frontend/tools/check_i18n.py
for f in frontend/js/*.js frontend/js/pages/*.js; do node --input-type=module --check < "$f"; done
```

## Pages

| URL | Who | What |
|---|---|---|
| `/` | everyone | Landing for new visitors; logged-in people go to their page; an expired session goes to `/login` |
| `/login` | guests | Email → name (first login) → code |
| `/questionnaire` | logged in | Facts, all 20 questions (a draft saved after every answer), "what are you looking for?" |
| `/feed` | logged in | Rooms with free places; dorm and apartment tabs |
| `/room?id=…` | logged in | One room: photos, map, residents, compatibility, contacts |
| `/home` | logged in | List or edit your place; residents, invites, photos |
| `/join` | logged in | Join a place by invite link or code |
| `/account` | logged in | Profile, contacts, language, logout, delete |
| `/compatibility`, `/privacy` | everyone | How the score works; personal data |

The language switch appears on `/`, `/login` and `/account` only. The account's language is
saved on the server and cached in `localStorage`.
