# nsusosed.ru — frontend

Plain HTML, CSS and JavaScript (ES modules in the browser). No framework, no build step, no npm: what is in this folder is exactly what the browser gets. The interface is in Russian and English: each user picks a language once during onboarding and can change it on the Account page.

The product spec is the root [README.md](../README.md). The backend lives in [`backend/`](../backend) and is a teammate's area: this folder only talks to it through `/api/`.

## Run it locally

You need Python 3.8+ and nothing else.

### Without the backend (mock API)

```bash
python3 frontend/dev_server.py
```

Open <http://localhost:8080/?mock=1>. A yellow banner says the mock is on. Any `@g.nsu.ru` address logs in with code **123456**. The mock keeps its data in `localStorage`, ships with about 20 sample homes, and follows the same contract as the real API (error codes, versions, admins, photos, the matching formula). The demo invite link is <http://localhost:8080/join#token=demo-invite-token>. Turn the mock off with `?mock=0`. To start over with fresh data, run `resetMockDb()` in the browser console.

The mock only works on `localhost` / `127.0.0.1`, and the browser never downloads it otherwise.

### Against the real backend

1. Run the backend on `http://localhost:8000` (see [backend/README.md](../backend/README.md)) with these values in its `.env`:

   ```
   PUBLIC_ORIGIN=http://localhost:8080
   EMAIL_MODE=log
   MEDIA_DIR=media
   ```

   `PUBLIC_ORIGIN` has to be the dev server's address. With `MEDIA_DIR=media` photos land in `backend/media`, which the dev server serves as `/media/` (`--media-dir` to change it). The backend rejects POST/PUT/DELETE requests whose `Origin` header doesn't match it, and it builds invite links from it. With `EMAIL_MODE=log` the login code shows up in the backend's log instead of in an email.

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
| `/` | `index.html` | Short intro; link to log in, or to matches / your home |
| `/login` | `login.html` | Email + privacy checkbox → 6-digit code (2-minute timer, resend after 60 s) |
| `/questionnaire` | `questionnaire.html` | Unfinished accounts: step-by-step onboarding (language → role → one screen per unanswered question → budget, or home, contacts, photos and invite). Finished accounts: role, 10 questions and budget on one page |
| `/matches?kind=dorm\|apartment&page=N&all=1` | `matches.html` | Seekers: tabs, cards sorted by score, explanation, warnings, pagination; `all=1` also shows places that don't fit, with the reasons |
| `/listing?id=<uuid>` | `listing.html` | Home detail: photos, question-by-question breakdown, why it doesn't fit, "Show contacts" |
| `/home` | `home.html` | Hosts: the home they live in. Admins edit details, contacts and photos, confirm every 30 days, pause, delete, invite, make or unmake admins, remove residents; everyone can leave. Without a home: create one (`/my-listing` redirects here) |
| `/join#token=…` | `join.html` | Accept an invite: log in, answer the questionnaire if needed, then join |
| `/account` | `account.html` | Display name, interface language, log out, delete account (type `DELETE`) |
| `/privacy` | `privacy.html` | Personal data policy (**draft**: see "Gaps") |
| anything else | `404.html` | Not found |

Pages that need a login send logged-out users to `/login?next=<page>` and bring them back afterwards. An unfinished account (no language, no role, or a questionnaire of an older version) is sent to `/questionnaire?next=<page>` from every page except the questionnaire, `/join`, Account and the static pages.

The menu depends on the role (`layout.js`, `data-show` on each item): seekers see Matches, hosts see My home, both see Questionnaire and Account; during onboarding only Account is shown.

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

    # 3. Listing photos, written by the backend to its MEDIA_DIR (see
    #    backend/README.md, "Photos in production"). Uploads need a bigger
    #    body limit than the rest of the API.
    location /media/ {
        alias /var/lib/nsusosed/media/;
    }
    location ~ ^/api/listings/[^/]+/photos$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 11m;
    }

    # 4. Files in this folder that are for developers only.
    location ~ ^/(tools/|dev_server\.py$|README\.md$) {
        return 404;
    }

    # 5. Headers. Keep them all at the server level: an add_header inside a
    #    location block would silently drop these.
    #    No build step means no hashed file names, so browsers must revalidate
    #    (they still get 304s, so it stays fast).
    add_header Cache-Control "no-cache" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://stat.gehrman.me; style-src 'self'; img-src 'self' data:; connect-src 'self' https://stat.gehrman.me; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
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
├── *.html              one file per page: header, footer and static skeleton + one <script type="module">
├── css/style.css       all styles; mobile first, light and dark theme
├── favicon.svg
├── js/
│   ├── api.js          the only module that calls the backend; lists every endpoint
│   ├── errors.js       error code → message (ru/en): edit here when the backend adds a code
│   ├── i18n.js         t(), language switch, data-i18n attributes
│   ├── i18n/ru.js      Russian texts (default)
│   ├── i18n/en.js      English texts
│   ├── layout.js       login check, menu by role, account language, onboarding redirect: initPage()
│   ├── home-form.js    home details, contacts editor, photo editor, invite link (onboarding and /home)
│   ├── ui.js           DOM helper h(), errors next to fields, busy buttons, dialogs
│   ├── listing-view.js listing title, score, explanation, warnings, reasons (shared)
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

FastAPI's `/docs` and `/openapi.json` are the source of truth; `js/api.js` lists every call, and `backend/README.md` describes homes, admins, photos and the error codes. The whole flow has been run against the real backend: onboarding as a host (home, three contacts, two photos, invite), joining by invite, making an admin, the last admin leaving, a seeker with "Show places I don't match with", and a user with an older questionnaire who only gets the new question.

## Gaps and notes for the backend

1. **Default display name is `Пользователь`** (Russian) for every new user, and it is what roommates see. Consider asking for a name during onboarding, or `null` plus a prompt.
2. **`RESIDENTS_DISAGREE`** is only reported for the first question where residents disagree (`break` in `matching_service.py`). The frontend can show several if the backend sends them.
3. **Privacy policy** (`privacy.html`) is a draft written from what the code stores. The team needs to supply the final legal text (Russian personal-data law, 152-FZ) before launch.
4. **Photos are public by URL.** The file names are random, but anyone with a link can open the photo without logging in. Serving them through the API would need an auth check per image.
5. **Error codes.** `js/errors.js` covers every code in `backend/README.md`, plus three the frontend makes up itself: `NETWORK_ERROR`, `SERVICE_UNAVAILABLE` (nginx 502/503/504) and `UNKNOWN`. A new backend code shows a generic message until it is added there.
