# nsusosed — Backend & Infrastructure

Подбор соседей в общежитиях и съёмных квартирах НГУ.

## Запуск

1. Скопируйте и отредактируйте переменные (для локальной разработки без Postbox поставьте `EMAIL_MODE=log`):
   ```bash
   cp .env.example .env
   nano .env
   ```

2. Сгенерируйте самоподписанный сертификат (для разработки):
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
       -keyout nginx/certs/privkey.pem \
       -out nginx/certs/fullchain.pem \
       -subj "/CN=localhost"
   ```

3. Запустите:
   ```bash
   docker compose up -d --build
   ```

4. Проверка:
   ```bash
   curl http://localhost/health
   curl http://localhost/api/questions
   ```

## Миграции

Применяются автоматически при старте контейнера app.

Вручную:
```bash
docker compose exec app alembic upgrade head
docker compose exec app alembic revision --autogenerate -m "description"
```

## Тесты

```bash
cd backend
pip install -r requirements-dev.txt
# Отдельная пустая БД: таблицы очищаются перед каждым тестом
TEST_DATABASE_URL=postgresql+asyncpg://nsusosed:PASSWORD@localhost:5432/nsusosed_test pytest
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

### Photos in production

The production stack (`deploy/` on the `deploy` branch) needs three changes before this version ships:

1. **A writable folder for the API container.** It runs read-only as user `10001`, so mount a host folder:
   ```bash
   sudo install -d -o 10001 -g 10001 -m 755 /var/lib/nsusosed/media
   ```
   In `deploy/compose.yaml`, service `api`:
   ```yaml
       volumes:
         - /var/lib/nsusosed/media:/data/media
       environment:
         MEDIA_DIR: /data/media
   ```
2. **Host nginx** (`deploy/nginx/nsusosed.ru.conf`): serve the photos, and allow bigger bodies on the upload route only.
   ```nginx
   location /media/ {
       alias /var/lib/nsusosed/media/;
       expires 30d;
       add_header Cache-Control "public, immutable" always;
   }

   location ~ ^/api/listings/[^/]+/photos$ {
       proxy_pass http://nsusosed_api;
       proxy_http_version 1.1;
       proxy_set_header Connection "";
       proxy_set_header Host              $host;
       proxy_set_header X-Forwarded-For   $remote_addr;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_read_timeout 30s;
       client_max_body_size 11m;
   }
   ```
   An `add_header` inside a location drops the server-level headers for it, so copy the security headers into `location /media/` too (or leave out its `add_header` and keep the server's `no-cache`). The CSP's `img-src 'self'` already allows the photos.
3. **Backups:** back up `/var/lib/nsusosed/media` together with the database.

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
