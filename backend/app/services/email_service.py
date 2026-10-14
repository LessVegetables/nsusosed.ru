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


async def send_otp_email(to_email: str, code: str) -> bool:
    """
    Отправить код подтверждения через Postbox API.
    При EMAIL_MODE=log код пишется в лог (только для разработки).
    """
    subject = "Код подтверждения nsusosed"
    ttl = _minutes_ru(max(1, settings.otp_ttl_seconds // 60))
    text = (
        f"Ваш код для входа в nsusosed: {code}\n\n"
        f"Код действителен {ttl}.\n"
        f"Никому его не сообщайте."
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px;">
        <h2>Код подтверждения nsusosed</h2>
        <p>Ваш код для входа:</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 6px;
                    background: #f0f0f0; padding: 16px; text-align: center;
                    border-radius: 8px; margin: 16px 0;">
            {code}
        </div>
        <p>Код действителен <b>{ttl}</b>.</p>
        <p>Если вы не запрашивали код — проигнорируйте это письмо.</p>
    </div>
    """

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
