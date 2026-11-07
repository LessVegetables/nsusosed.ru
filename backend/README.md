# nsusosed — Backend & Infrastructure

Подбор соседей в общежитиях и съёмных квартирах НГУ.

## Запуск (локально, без Docker)

Нужны Python 3.12 и PostgreSQL 16. Команды — из папки `backend/`.

1. Окружение и зависимости:
   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. Настройки. Приложение читает `.env` из текущей папки, то есть `backend/.env`:
   ```bash
   cp ../.env.example .env
   ```
   Для разработки достаточно поправить `DATABASE_URL`; `EMAIL_MODE=log` пишет коды входа в лог вместо писем.

3. База и миграции:
   ```bash
   createdb nsusosed
   alembic upgrade head
   ```

4. Запуск и проверка:
   ```bash
   uvicorn app.main:app --reload --port 8000
   curl http://localhost:8000/api/health
   ```

Сайт целиком (фронтенд + `/api` на одном адресе) — через `frontend/dev_server.py`, см. [frontend/README.md](../frontend/README.md).

## Тестовые данные

Около 20 жилья с жильцами и анкетами для локальной разработки (работает только при `EMAIL_MODE=log`):
```bash
EMAIL_MODE=log python -m app.seed           # пустая база
EMAIL_MODE=log python -m app.seed --reset   # стереть все таблицы и заполнить заново
```
Войти можно под любым адресом `@g.nsu.ru` (код — в логе бэкенда), в том числе под жильцами `student1@g.nsu.ru`, `student2@g.nsu.ru`… Ссылка-приглашение в комнату Ани: `{PUBLIC_ORIGIN}/join#token=demo-invite-token`.

## Миграции

В продакшене применяются автоматически при старте контейнера (`alembic upgrade head` в `Dockerfile`). Локально:
```bash
alembic upgrade head
alembic revision --autogenerate -m "description"   # потом прочитать и поправить файл
alembic check                                        # модели и миграции совпадают
```

## Тесты

```bash
# Отдельная пустая БД: таблицы очищаются перед каждым тестом
createdb nsusosed_test
TEST_DATABASE_URL=postgresql+asyncpg://localhost/nsusosed_test pytest
```

Без `TEST_DATABASE_URL` запускаются только юнит-тесты формулы совместимости, остальные пропускаются.

## Homes, admins and photos

A home (`listings` table) has no single owner. It exists while someone lives in it:

- `memberships.is_admin` says who manages it. Admins edit it (details, 1–10 `contacts`, photos), confirm, pause, delete, create invite links, make other residents admins (`POST/DELETE /api/listings/{id}/admins/{user_id}`) and remove residents (`DELETE /api/listings/{id}/members/{user_id}`). Only a resident with a questionnaire can be made admin.
- When the last admin leaves (or is removed, or deletes their account), the longest-standing resident becomes admin, preferring one with a questionnaire. When the last resident leaves, the home and its photos are deleted.
- A user is a `seeker` or a `host` (`profiles.situation`). Creating or joining a home makes them a host; a resident can't switch to seeker without leaving.
- `GET /api/me` returns `language`, `situation`, `profile_complete` (a questionnaire of the current version) and `home: {id, is_admin} | null`. `PUT /api/me` takes `display_name` and/or `language`.
- `GET /api/matches?include_unmatched=true` also returns homes that break a hard condition or the budget, after the matches, with `fits: false` and `reasons`. Detail and contact work for them too.
- Questionnaire v2 adds `wake` after `sleep`. v1 profiles keep matching; a question one side hasn't answered is skipped.

Photos: `POST /api/listings/{id}/photos` (multipart, field `file`), `DELETE /api/listings/{id}/photos/{photo_id}`, `PUT /api/listings/{id}/photos/order` (`{"photo_ids": [...]}`, the first is the cover). Each upload is turned by its EXIF orientation, stripped of all metadata (GPS included), shrunk to 1600 px and saved as JPEG in `MEDIA_DIR/listings/<id>/<random>.jpg`. nginx serves `MEDIA_DIR` at `MEDIA_URL` (`/media`). The file names can't be guessed; the files themselves are public to anyone with the URL.

### Deleting an account

`DELETE /api/me` (`{"confirm": "DELETE"}`) doesn't erase anything yet. It sets `users.deleted_at`, closes all sessions and hides the user: roommates and candidates don't see them, their answers leave matching, and if they were the home's only active admin, an active roommate becomes admin. A home whose only residents are deleting their accounts disappears from search.

Logging in within `ACCOUNT_DELETION_GRACE_DAYS` (14) cancels the deletion; `verify-code` then returns `"account_restored": true`. After the grace period the account is erased for good: profile and sessions cascade, and the user leaves their home by the usual rules (last resident → home and photos deleted). The purge runs on every successful login and at startup, so it can happen a little after the 14 days if nobody logs in.

### Photos in production

The API container runs read-only, so photos go to the host folder `/srv/nsusosed/media`, mounted as `MEDIA_DIR=/data/media` (`deploy/compose.yaml`). Host nginx serves it at `/media/` and allows 11 MB bodies on the upload route only (`deploy/nginx/nsusosed.ru.conf`). Setup and backups: [deploy/README.md](../deploy/README.md).

## Коды ошибок API (API error codes)

Every error response looks like this:

```json
{"error": {"code": "ROOM_FULL", "message": "…", "fields": {}, "request_id": "…", "retry_after": null}}
```

The frontend picks the text to show from `code`, and from `fields` for validation errors. `message` is a Russian fallback for debugging; don't show it to users.

### `error.code`

| HTTP | code | When |
|---|---|---|
| 401 | `AUTH_REQUIRED` | No valid session: log in again |
| 401 | `INVALID_CODE` | Wrong or expired login code |
| 403 | `FORBIDDEN` | Not allowed, or a bad `Origin` |
| 403 | `NOT_ADMIN` | Only the home's admins can do this |
| 404 | `NOT_FOUND` | The home (or photo) doesn't exist, or isn't shown to this user (paused, expired, full) |
| 404 | `NOT_MEMBER` | The user named in the URL doesn't live in this home |
| 404 | `INVITE_INVALID` | Unknown invite token |
| 404 | `INVITE_EXPIRED` | Invite link has expired |
| 409 | `VERSION_CONFLICT` | `expected_version` is stale: reload, then retry |
| 409 | `ROOM_TAKEN` | This dorm building and room is already on the site |
| 409 | `ALREADY_IN_ROOM` | The user already lives in a home (creating or joining another one) |
| 409 | `ROOM_FULL` | The home already has as many residents on the site as occupied places |
| 409 | `OCCUPANCY_CONFLICT` | `occupied_count` is lower than the number of residents on the site |
| 409 | `LAST_ADMIN` | Unmaking the only admin; make someone else admin first |
| 409 | `LEAVE_HOME_FIRST` | A resident tried to switch their questionnaire to `seeker` |
| 409 | `TOO_MANY_PHOTOS` | The home already has 10 photos |
| 413 | `PHOTO_TOO_LARGE` | The photo is over 10 MB, or decodes to too many pixels |
| 415 | `PHOTO_BAD_TYPE` | Not a JPEG, PNG or WebP image |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | The request body isn't JSON (or `multipart/form-data` for photo uploads) |
| 422 | `VALIDATION_ERROR` | Invalid input; see `fields` |
| 422 | `PROFILE_REQUIRED` | Fill in the questionnaire first |
| 422 | `TARGET_PROFILE_REQUIRED` | Only a resident with a questionnaire can be made admin |
| 422 | `BUDGET_REQUIRED` | Set a monthly budget first (needed for apartments) |
| 429 | `RATE_LIMITED` | Too many login attempts; `retry_after` is in seconds (also sent as the `Retry-After` header) |
| 503 | `EMAIL_SEND_FAILED` | The login code couldn't be emailed |
| 500 | `INTERNAL_ERROR` | Unexpected error; quote `request_id` when reporting it |
| other | `METHOD_NOT_ALLOWED`, `PAYLOAD_TOO_LARGE`, `HTTP_ERROR` | Generic HTTP errors |

### `error.fields` (with `VALIDATION_ERROR`)

`fields` maps a field path to a reason code, for example `{"answers.sleep.allowed": "REQUIRED_WHEN_HARD"}` or `{"email": "DOMAIN_NOT_ALLOWED"}`. Query parameters are prefixed with `query.`, and `_` means the request as a whole.

Reasons set by our own checks:

| Reason | Meaning |
|---|---|
| `REQUIRED` | Required for this listing type (`building`, `room_number`, `floor` for dorms; `district`, `monthly_cost_per_person_rub` for apartments), or a contact (`contacts.N.value`) is empty |
| `MUST_BE_EMPTY` | The field doesn't apply here (a dorm field on an apartment or vice versa; `allowed` when `hard` is false) |
| `INVALID_CHOICE` | Not one of the allowed values (`kind`, `status`, `view`, `contacts.N.type`, `situation`) |
| `EXCEEDS_CAPACITY` | `occupied_count` is greater than `capacity` |
| `INVALID_TELEGRAM` | Not a Telegram username (5–32 characters: Latin letters, digits, `_`) |
| `INVALID_PHONE` | Not a phone number (phone, WhatsApp) |
| `TOO_LONG` | A contact is longer than 100 characters, or `contacts` has more than 10 items |
| `TOO_SHORT` | `contacts` is empty (a home needs at least one) |
| `INVALID_SET` | `photo_ids` must list every photo of the home exactly once |
| `DOMAIN_NOT_ALLOWED` | The email isn't on an allowed domain (`@g.nsu.ru`) |
| `INVALID_EMAIL` | Not an email address |
| `MUST_ACCEPT` | `privacy_accepted` must be true |
| `MUST_BE_DELETE` | Deleting the account needs `{"confirm": "DELETE"}` |
| `REQUIRED_WHEN_HARD` | `allowed` must not be empty when `hard` is true |
| `DUPLICATES` | `allowed` contains repeated values |
| `OUT_OF_SCALE` | An answer value (or a value in `allowed`) is outside the question's scale |
| `INVALID_QUESTION_SET` | `answers` must contain exactly the 10 question keys |
| `UNSUPPORTED_VERSION` | Only `questionnaire_version: 2` is supported |

Anything else is a pydantic error type, uppercased: `MISSING`, `STRING_TOO_SHORT`, `STRING_TOO_LONG`, `GREATER_THAN_EQUAL`, `LESS_THAN_EQUAL`, `INT_PARSING`, `BOOL_PARSING`, `STRING_PATTERN_MISMATCH`, and so on. The frontend can show a generic "invalid value" message for these.
