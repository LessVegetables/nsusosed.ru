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
| 403 | `FORBIDDEN` | Not allowed (for example, not the listing's author), or a bad `Origin` |
| 403 | `OWNER_CANNOT_LEAVE` | The author tried to leave their own room (they must delete the listing) |
| 404 | `NOT_FOUND` | The listing doesn't exist, or isn't available to this user (hidden, expired, full, filtered out by hard conditions or budget) |
| 404 | `INVITE_INVALID` | Unknown invite token |
| 404 | `INVITE_EXPIRED` | Invite link has expired |
| 409 | `VERSION_CONFLICT` | `expected_version` is stale: reload, then retry |
| 409 | `LISTING_EXISTS` | The user already has a listing |
| 409 | `ROOM_TAKEN` | This dorm building and room already has a listing |
| 409 | `ALREADY_IN_ROOM` | The user is already a resident of another room |
| 409 | `ROOM_FULL` | The listing already has as many linked residents as occupied places |
| 409 | `OCCUPANCY_CONFLICT` | `occupied_count` is lower than the number of linked residents |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | The request body isn't JSON |
| 422 | `VALIDATION_ERROR` | Invalid input; see `fields` |
| 422 | `PROFILE_REQUIRED` | Fill in the questionnaire first |
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
| `REQUIRED` | Required for this listing type (`building`, `room_number`, `floor` for dorms; `district`, `monthly_cost_per_person_rub` for apartments), or the contact is empty |
| `MUST_BE_EMPTY` | The field doesn't apply here (a dorm field on an apartment or vice versa; `allowed` when `hard` is false) |
| `INVALID_CHOICE` | Not one of the allowed values (`kind`, `status`, `view`, `contact_type`, `situation`) |
| `EXCEEDS_CAPACITY` | `occupied_count` is greater than `capacity` |
| `INVALID_TELEGRAM` | Not a Telegram username (5–32 characters: Latin letters, digits, `_`) |
| `INVALID_PHONE` | Not a phone number (phone, WhatsApp) |
| `TOO_LONG` | The contact is longer than 100 characters |
| `DOMAIN_NOT_ALLOWED` | The email isn't on an allowed domain (`@g.nsu.ru`) |
| `INVALID_EMAIL` | Not an email address |
| `MUST_ACCEPT` | `privacy_accepted` must be true |
| `MUST_BE_DELETE` | Deleting the account needs `{"confirm": "DELETE"}` |
| `REQUIRED_WHEN_HARD` | `allowed` must not be empty when `hard` is true |
| `DUPLICATES` | `allowed` contains repeated values |
| `OUT_OF_SCALE` | An answer value (or a value in `allowed`) is outside the question's scale |
| `INVALID_QUESTION_SET` | `answers` must contain exactly the 9 question keys |
| `UNSUPPORTED_VERSION` | Only `questionnaire_version: 1` is supported |

Anything else is a pydantic error type, uppercased: `MISSING`, `STRING_TOO_SHORT`, `STRING_TOO_LONG`, `GREATER_THAN_EQUAL`, `LESS_THAN_EQUAL`, `INT_PARSING`, `BOOL_PARSING`, `STRING_PATTERN_MISMATCH`, and so on. The frontend can show a generic "invalid value" message for these.
