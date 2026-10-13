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
