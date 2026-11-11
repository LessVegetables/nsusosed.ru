# nsusosed — backend

The API behind nsusosed.ru: FastAPI, PostgreSQL 16, SQLAlchemy (async), Alembic. Python 3.12.

## Run it locally (no Docker)

Commands are run from `backend/`.

1. Environment and dependencies:
   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. Settings. The app reads `.env` from the current folder, so `backend/.env`:
   ```bash
   cp ../.env.example .env
   ```
   For development it is enough to fix `DATABASE_URL`. `EMAIL_MODE=log` writes login codes to the log instead of emailing them. With `PUBLIC_ORIGIN=http://…` the session cookie is sent without `Secure` (Safari refuses Secure cookies on plain http, even on localhost).

3. Database and migrations:
   ```bash
   createdb nsusosed
   alembic upgrade head
   ```

4. Start and check:
   ```bash
   uvicorn app.main:app --reload --port 8000
   curl http://localhost:8000/api/health
   ```

The whole site (pages and `/api` on one address) runs through `frontend/dev_server.py`; see [frontend/README.md](../frontend/README.md). Log in with any `@nsu.ru` or `@*.nsu.ru` address; the code is in the backend log.

## Tests

```bash
createdb nsusosed_test     # a separate database: its tables are emptied before every test
TEST_DATABASE_URL=postgresql+asyncpg://localhost/nsusosed_test pytest
```

Without `TEST_DATABASE_URL` only the tests that need no database run (scoring, emojis, contacts, settings). The tests pin the login rate limits to their production values, whatever `.env` says.

## Migrations

Applied automatically in production when the container starts. Locally:

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"   # then read and fix the file
```

The pilot's migrations start again at `001`; nothing is carried over from the MVP (see `deploy/README.md` for the one-time reset of a server that ran the MVP).

## What is where

| Path | What |
|---|---|
| `app/main.py` | The app, routers, the single error envelope |
| `app/routers/` | `auth`, `users` (`/api/me…`), `questionnaire`, `homes` (homes, photos, residents, invites, emojis, address search), `feed` (feed, room page, contacts), `meta` |
| `app/services/` | The logic behind each router |
| `app/models/`, `alembic/versions/` | Tables and their migrations |
| `app/questionnaires/vN/` | One questionnaire version: `questions.json`, `scoring.json` and the scorer |
| `app/config/faculties.json`, `dorms.json` | Reference lists served by `GET /api/meta` |
| `app/utils/` | Sessions, origin check, contacts, emojis, errors |

## Data and privacy rules the code enforces

- **Dorm room label** (`homes.room_label`, e.g. `100б`): stored normalized, used only for the "this room is already listed" check, **never returned by any endpoint**.
- **Apartments**: only `district`, `lat`, `lon`, `radius_m`. The circle is produced in the host's browser; the server rejects a radius outside 300–500 m (so an exact point can't be stored) and coordinates outside the Novosibirsk area. There is no address column.
- **Address search** (`POST /api/geo/search`) proxies OpenStreetMap's Nominatim. The query is not stored, and the HTTP client's request logging is turned off so it does not reach the log either.
- **Questionnaire answers**: stored with their version. Hidden answers are returned only to their owner. Compatibility leaves the server only as `{percent, badges}`: a percent rounded to 5 and one of three levels per topic.
- **Hard blocks** make a room look exactly like one that does not exist (404, absent from the feed).
- **Contacts** belong to the user. They are returned by `GET /api/me` to their owner and by `POST /api/rooms/{id}/contacts` to a logged-in student with a completed questionnaire; nowhere else.
- **Photos and avatars** are re-encoded: EXIF orientation applied, all metadata (GPS included) dropped, saved as JPEG under a random name in `MEDIA_DIR`. nginx serves `MEDIA_DIR` at `/media`; the names can't be guessed, but the files are public to anyone with the URL.
- **Emojis** identify a listing for people; the unique index is on an order-independent key. They are never used as an identifier in code.

## Homes, residents, rights

A home is a dorm room or an apartment with up to six rooms; seekers see rooms. Whoever lists a home lives in it and holds every right. People who join by invite start with none. Rights are per person: `can_edit` (the listing), `can_photos`, `can_invites`, `can_residents` (remove people, change rights). Someone can always manage residents: if the last person who could leaves or asks to delete their account, the longest-standing resident gets every right. When the last resident leaves, the home and its photos are deleted. A person lives in at most one home.

A home is visible to seekers once one of its residents has a phone, Telegram or VK, and it has a free place.

Invite codes are eight characters, valid for `INVITE_TTL_DAYS` (7); only their hash is stored, so a code is shown once, when it is created. `/api/invites/preview` and `/join` accept the bare code or the whole link.

## Deleting an account

`DELETE /api/me` (`{"confirm": "DELETE"}`) erases nothing yet. It sets `users.deleted_at`, closes all sessions and hides the person everywhere. Logging in within `ACCOUNT_DELETION_GRACE_DAYS` (14) cancels it (`verify-code` returns `"account_restored": true`). After that the account is erased: answers, contacts and sessions cascade, the avatar file is removed, and the person leaves their home by the usual rules. The purge runs on every successful login and at startup.

## Errors

Every error looks like this:

```json
{"error": {"code": "ROOM_TAKEN", "message": "…", "fields": {}, "request_id": "…", "retry_after": null, "data": {"room_id": "…"}}}
```

The frontend chooses what to show from `code`, and from `fields` for validation errors (`{"rooms.0.emoji": "EMOJI_TAKEN"}`). `message` is a Russian fallback for debugging and is not shown to users. `data` carries facts some errors need.

| HTTP | code | When |
|---|---|---|
| 401 | `AUTH_REQUIRED` | No valid session |
| 401 | `INVALID_CODE` | Wrong or expired login code |
| 403 | `FORBIDDEN` | A bad `Origin` |
| 403 | `NO_PERMISSION` | The resident lacks the right for this action |
| 404 | `NOT_FOUND` | Doesn't exist, or isn't shown to this person |
| 404 | `INVITE_INVALID` | Unknown, revoked or expired invite |
| 409 | `ROOM_TAKEN` | That dorm room is already listed; `data.room_id` is the listing |
| 409 | `EMOJI_TAKEN` | Another listing has these three emojis |
| 409 | `ALREADY_IN_HOME` | The person already lives in a home |
| 409 | `ROOM_OCCUPIED` | Removing a room someone lives in |
| 409 | `LAST_MANAGER` | Nobody would be left able to manage residents |
| 409 | `ABOUT_REQUIRED` | Answer "are you 18?" before the questionnaire |
| 409 | `QUESTIONNAIRE_OUTDATED` | The page has an old questionnaire version: reload |
| 409 | `QUESTIONNAIRE_REQUIRED` | The feed and contacts need a completed questionnaire |
| 409 | `TOO_MANY_PHOTOS` | A home has 10 photos already |
| 413 | `PHOTO_TOO_LARGE` | Over 10 MB, or too many pixels |
| 415 | `PHOTO_BAD_TYPE` | Not JPEG, PNG or WebP |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | The body isn't JSON (or multipart for uploads) |
| 422 | `VALIDATION_ERROR` | Invalid input; see `fields` |
| 429 | `RATE_LIMITED` | Too many attempts; `retry_after` is in seconds |
| 503 | `EMAIL_SEND_FAILED` | The login code couldn't be emailed |
| 503 | `GEO_UNAVAILABLE` | Address search is down; the pin can be placed by hand |
| 500 | `INTERNAL_ERROR` | Unexpected; quote `request_id` |

Reason codes in `fields` are either set by our checks (`REQUIRED`, `DOMAIN_NOT_ALLOWED`, `NEED_PRIMARY`, `INVALID_PHONE`, `INVALID_EMOJI`, `BAD_RADIUS`, `OUTSIDE_AREA`, `MORE_THAN_CAPACITY`, `INVALID_CHOICE`, `EXCLUSIVE_OPTION`, …) or pydantic's error type in capitals (`MISSING`, `STRING_TOO_LONG`, `LITERAL_ERROR`, …). The frontend translates the ones it knows (`error.field.*` in `frontend/js/i18n/`) and shows a generic message for the rest.
