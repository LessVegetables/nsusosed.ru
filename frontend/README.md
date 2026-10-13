# nsusosed.ru — frontend

Plain HTML, CSS and JavaScript (ES modules in the browser). No framework, no build step, no npm: what is in this folder is exactly what the browser gets. Russian is the default language; English is one click away.

The product spec is the root [README.md](../README.md). The backend lives in [`backend/`](../backend) and is a teammate's area: this folder only talks to it through `/api/`.

## Run it locally

You need Python 3.8+ and nothing else.

### Without the backend (mock API)

```bash
python3 frontend/dev_server.py
```

Open <http://localhost:8080/?mock=1>. A yellow banner says the mock is on. Any `@g.nsu.ru` address logs in with code **123456**. The mock keeps its data in `localStorage`, ships with about 20 sample rooms, and follows the same contract as the real API (error codes, versions, the matching formula). The demo invite link is <http://localhost:8080/join#token=demo-invite-token>. Turn the mock off with `?mock=0`. To start over with fresh data, run `resetMockDb()` in the browser console.

The mock only works on `localhost` / `127.0.0.1`, and the browser never downloads it otherwise.

### Against the real backend

1. Run the backend on `http://localhost:8000` (see [backend/README.md](../backend/README.md)) with these values in its `.env`:

   ```
   PUBLIC_ORIGIN=http://localhost:8080
   EMAIL_MODE=log
   ```

   `PUBLIC_ORIGIN` has to be the dev server's address. The backend rejects POST/PUT/DELETE requests whose `Origin` header doesn't match it, and it builds invite links from it. With `EMAIL_MODE=log` the login code shows up in the backend's log instead of in an email.

2. Start the dev server and open <http://localhost:8080>:

   ```bash
   python3 frontend/dev_server.py
   ```

   Options: `--port 3000`, `--backend http://localhost:8001`, `--host 0.0.0.0` (to open the site from your phone on the same Wi-Fi; set `PUBLIC_ORIGIN` to match).

The dev server serves pages the same way production nginx does (`/matches` → `matches.html`, unknown paths → `404.html`). It also proxies `/api/*` to the backend, so everything is same-origin and the session cookie works.

**Cookie on http://localhost.** The backend sets `__Host-nsusosed` with `Secure`. Chrome, Edge and Firefox accept Secure cookies on `http://localhost`, so the login works there. If you log in and immediately land back on the login page, your browser refused the cookie on plain http: use Chrome or Firefox, or the mock.

### Checks

```bash
python3 frontend/tools/check_i18n.py   # ru.js and en.js have the same keys; no key is missing
```

## Pages

| URL | File | What it does |
|---|---|---|
| `/` | `index.html` | Short intro; link to log in or to matches |
| `/login` | `login.html` | Email + privacy checkbox → 6-digit code (2-minute timer, resend after 60 s) |
| `/questionnaire` | `questionnaire.html` | 9 questions: answer, importance 1–10, optional hard condition; situation and budget |
| `/matches?kind=dorm\|apartment&page=N` | `matches.html` | Tabs, cards sorted by score, explanation, warnings, pagination |
| `/listing?id=<uuid>` | `listing.html` | Listing detail, question-by-question breakdown, "Show contact" |
| `/my-listing` | `my-listing.html` | Create / edit / pause / resume / delete; confirm every 30 days; invite link; residents |
| `/join#token=…` | `join.html` | Accept an invite: log in, fill in the questionnaire if needed, then join |
| `/account` | `account.html` | Display name, leave a room, log out, delete account (type `DELETE`) |
| `/privacy` | `privacy.html` | Personal data policy (**draft**: see "Gaps") |
| anything else | `404.html` | Not found |

Pages that need a login send logged-out users to `/login?next=<page>` and bring them back afterwards. A new user goes from the login straight to the questionnaire.

## Production: what nginx needs

The site is static files on the same origin as the API: `https://nsusosed.ru`, with the API under `/api/`. Copy this folder to the server (for example `/var/www/nsusosed/frontend`). Then:

```nginx
server {
    listen 443 ssl;
    http2 on;               # nginx 1.25.1+; older versions: "listen 443 ssl http2;"
    server_name nsusosed.ru;
    # ssl_certificate / ssl_certificate_key ...

    root /var/www/nsusosed/frontend;
    index index.html;

    # 1. API → FastAPI. Same origin, so the __Host- cookie and the Origin check work.
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 64k;
    }

    # 2. Pages without ".html": /matches → matches.html, /join → join.html,
    #    /listing?id=… → listing.html (the query string is kept), / → index.html.
    location / {
        try_files $uri $uri.html $uri/ =404;
    }
    error_page 404 /404.html;

    # 3. Files in this folder that are for developers only.
    location ~ ^/(tools/|dev_server\.py$|README\.md$) {
        return 404;
    }

    # 4. Headers. Keep them all at the server level: an add_header inside a
    #    location block would silently drop these.
    #    No build step means no hashed file names, so browsers must revalidate
    #    (they still get 304s, so it stays fast).
    add_header Cache-Control "no-cache" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
    add_header Referrer-Policy "same-origin" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000" always;
}

server {
    listen 80;
    server_name nsusosed.ru;
    return 301 https://$host$request_uri;
}
```

Notes:

- The only fallback rule that matters is `try_files $uri $uri.html $uri/ =404`. There is no single-page-app "everything → index.html" fallback: every page is its own HTML file.
- `/join` must resolve to `join.html`. The backend builds invite links as `{PUBLIC_ORIGIN}/join#token=…`, so in production `PUBLIC_ORIGIN=https://nsusosed.ru`. The token is in the `#hash`, which browsers never send to the server, so it doesn't end up in nginx logs.
- `.js` files must be served as JavaScript (`application/javascript` or `text/javascript`). The stock `mime.types` already does this; if pages come up blank, check this first.
- The CSP above works because the code has no inline scripts, inline styles or `eval`. Keep it that way.
- Behind nginx, uvicorn needs `--proxy-headers` (and `FORWARDED_ALLOW_IPS=127.0.0.1`) to see real client IPs for its rate limits.

## How the code is organised

```
frontend/
├── *.html              one file per page: static skeleton + one <script type="module">
├── css/style.css       all styles; mobile first, light and dark theme
├── favicon.svg
├── js/
│   ├── api.js          the only module that calls the backend; lists every endpoint
│   ├── errors.js       error code → message (ru/en): edit here when the backend adds a code
│   ├── i18n.js         t(), language switch, data-i18n attributes
│   ├── i18n/ru.js      Russian texts (default)
│   ├── i18n/en.js      English texts
│   ├── layout.js       header, footer, login check: initPage()
│   ├── ui.js           DOM helper h(), errors next to fields, busy buttons, dialogs
│   ├── listing-view.js listing title, score, explanation, warnings (shared)
│   ├── config.js       constants and the mock switch (no secrets, ever)
│   ├── storage.js      localStorage/sessionStorage wrapped in try/catch
│   ├── pages/*.js      one script per page
│   └── mock/           fake backend for local development
├── dev_server.py       static files + /api proxy, standard library only
└── tools/check_i18n.py translation key check
```

A few rules the code follows:

- **Texts.** Every visible string has a key in `ru.js` and `en.js`. HTML uses `data-i18n="key"`; JS uses `h('p', { i18n: 'key', i18nArgs: {...} })`. Switching language re-translates the page in place, so half-filled forms keep their values. Question labels from the API are `{ru, en}` pairs and switch the same way (`localized:`). Plurals use `{one, few, many, other}`.
- **Errors.** `api.js` throws `ApiError` with `code`, `fields`, `retryAfter`, `requestId`. Pages show `errorText(err)` from `errors.js` and put `fields` reasons next to the inputs (each field wrapper has `data-field="path"`, e.g. `answers.sleep.allowed`). The API's `message` is never shown. For 500s the `request_id` is shown so users can report it.
- **Versions.** `expected_version` is sent with every change. On `VERSION_CONFLICT`:
  - the questionnaire reloads and asks the user to check and save again;
  - confirm, invite and pause/resume reload the listing and retry once (they don't depend on what the user typed);
  - the listing edit form keeps the user's edits, takes the new version and asks them to save again.
- **Nothing sensitive in URLs.** Forms are submitted by JS only (static forms have no `name` attributes and start with disabled buttons until the script is ready). The invite token is read from `#token=…`, moved to `sessionStorage` while the user logs in, and removed from the address bar immediately.
- **Accessibility.** Real `<label>`s, `fieldset`/`legend` for groups, `aria-invalid` + `aria-describedby` for field errors, `role="alert"` for errors, a live region for "Saved", the ARIA tabs pattern with arrow keys on `/matches`, a skip link, visible focus outlines, 44 px touch targets.

## API contract the frontend uses

Coded against the backend on branch `feature/backend_fixes` (commit `c7546d1`), which implements the contract from the task. FastAPI's `/docs` and `/openapi.json` are the source of truth; `js/api.js` lists every call. I ran the whole flow against that backend locally: login with a code, questionnaire, create/edit/pause/confirm a listing, invite → join, matches with a hard condition, detail, contact, `VERSION_CONFLICT` and `RATE_LIMITED`.

`main` still has the older backend (Russian-only question labels, fewer and less specific error codes), so the frontend won't work against `main` until that branch is merged. Use the mock until then.

## Gaps and notes for the backend

Things the frontend works around today. Each needs a decision or a small backend change.

1. **"Which room am I a resident of?"** No endpoint answers this. The Account page can't name the room, so "Leave the room" is always shown, and `DELETE /api/membership` returns 204 even when the user wasn't a resident. That means the page says "you are no longer a resident" either way. Suggestion: `GET /api/membership` → `{listing_id, building, room_number, district} | null`, or the same thing inside `GET /api/me`.
2. **Apartment price on match cards.** The `/api/matches` items have no `monthly_cost_per_person_rub`, so apartment cards show only the district. The card already shows the price if the field appears.
3. **`GET /api/me` has no `profile_complete`.** Pages that need it call `GET /api/profile` as well. Fine for now, but it costs an extra request.
4. **Author or resident?** `GET /api/listings/{id}` returns `compatibility: null` for both, with nothing saying which. The page shows one combined message.
5. **Confirming a paused listing resumes it** (`confirm` sets `status=active` when there are free places). So the "Confirm" button is shown only for active listings; paused ones show "Resume" instead.
6. **Default display name is `Пользователь`** (Russian) for every new user, and it is what roommates see. Consider asking for a name at sign-up, or `null` plus a prompt.
7. **`RESIDENTS_DISAGREE`** is only reported for the first question where residents disagree (`break` in `matching_service.py`). The frontend can show several if the backend sends them.
8. **Privacy policy** (`privacy.html`) is a draft written from what the code stores. The team needs to supply the final legal text (Russian personal-data law, 152-FZ) before launch.
9. **Error codes.** `js/errors.js` covers every code in the backend README on `feature/backend_fixes`, plus three the frontend makes up itself: `NETWORK_ERROR`, `SERVICE_UNAVAILABLE` (nginx 502/503/504) and `UNKNOWN`. A new backend code shows a generic message until it is added there.
