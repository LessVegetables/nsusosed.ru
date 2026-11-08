"""Отправка писем через Yandex Cloud Postbox (Amazon SES v2-совместимый API).

POST {POSTBOX_ENDPOINT}/v2/email/outbound-emails, подпись AWS SigV4
статическим ключом доступа сервисного аккаунта с ролью postbox.sender.
https://yandex.cloud/ru/docs/postbox/aws-compatible-api/api-ref/send-email
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.utils.sigv4 import sign_headers

logger = logging.getLogger("nsusosed.email")


def _minutes_ru(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        word = "минуту"
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = "минуты"
    else:
        word = "минут"
    return f"{n} {word}"


def otp_email(code: str) -> tuple[str, str, str]:
    """Тема, текст и HTML письма с кодом.

    Код стоит первым в теме, а первая строка письма продолжает тему
    («123456 — ваш код» → «Для подтверждения входа на NSUsosed.ru: 123456»):
    так код виден прямо в списке писем и в уведомлении, не открывая письмо.

    HTML годится для светлой и тёмной темы: ни фона, ни цвета основного текста
    не задаём (почтовый клиент подставит свои), рамка и второстепенный текст —
    средне-серые, читаемые на обоих фонах; для клиентов, понимающих
    prefers-color-scheme, серые чуть подстраиваются.
    """
    ttl = _minutes_ru(max(1, settings.otp_ttl_seconds // 60))
    subject = f"{code} — ваш код"
    text = (
        f"Для подтверждения входа на NSUsosed.ru:\n\n"
        f"{code}\n\n"
        f"Код действует {ttl}. Никому его не сообщайте.\n"
        f"Если вы не входили на сайт, просто проигнорируйте это письмо."
    )
    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{subject}</title>
<style>
  :root {{ color-scheme: light dark; supported-color-schemes: light dark; }}
  @media (prefers-color-scheme: dark) {{
    .code {{ border-color: #5c636d !important; }}
    .muted {{ color: #a3abb5 !important; }}
  }}
</style>
</head>
<body style="margin:0; padding:24px 16px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; font-size:16px; line-height:1.5;">
  <p style="margin:0 0 16px;">Для подтверждения входа на NSUsosed.ru:</p>
  <div class="code" style="display:inline-block; margin:0 0 16px; padding:12px 20px; border:1px solid #c4c9d0; border-radius:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:32px; font-weight:700; letter-spacing:6px;">{code}</div>
  <p class="muted" style="margin:0; font-size:14px; color:#7a828c;">Код действует {ttl}. Никому его не сообщайте.<br>Если вы не входили на сайт, просто проигнорируйте это письмо.</p>
</body>
</html>"""
    return subject, text, html


async def send_otp_email(to_email: str, code: str) -> bool:
    """
    Отправить код подтверждения через Postbox API.
    При EMAIL_MODE=log код пишется в лог (только для разработки).
    """
    subject, text, html = otp_email(code)

    # ── Тестовый режим ──────────────────────────────────
    if settings.email_mode == "log":
        logger.warning("[EMAIL TEST MODE] To: %s | Code: %s", to_email, code)
        return True

    url = settings.postbox_endpoint.rstrip("/") + "/v2/email/outbound-emails"
    payload = {
        "FromEmailAddress": settings.postbox_sender_email,
        "Destination": {"ToAddresses": [to_email]},
        "Content": {
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text, "Charset": "UTF-8"},
                    "Html": {"Data": html, "Charset": "UTF-8"},
                },
            }
        },
    }
    # Подписываются ровно эти байты — их же и отправляем.
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = sign_headers(
        "POST", url, {"Content-Type": "application/json"}, body,
        access_key_id=settings.postbox_access_key_id,
        secret_access_key=settings.postbox_secret_access_key,
        region=settings.postbox_region,
        service="ses",
        now=datetime.now(timezone.utc),
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
            if resp.is_success:
                logger.info("OTP email sent to %s, MessageId %s", to_email, _message_id(resp))
                return True
            logger.error("Postbox API error %s: %s", resp.status_code, resp.text)
            return False
    except httpx.HTTPError as e:
        logger.exception("Postbox HTTP error: %s", e)
        return False


def _message_id(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("MessageId", "?"))
    except ValueError:
        return "?"
