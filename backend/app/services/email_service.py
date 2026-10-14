"""Отправка писем через Яндекс Cloud Postbox (REST API)."""

from __future__ import annotations
import logging
import httpx
from app.config import settings

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

    payload = {
        "Messages": [{
            "From": {"Address": settings.postbox_sender_email, "Name": "nsusosed"},
            "To": [{"Address": to_email}],
            "Subject": subject,
            "Text": {"Body": text},
            "HTML": {"Body": html},
        }]
    }
    headers = {
        "Authorization": f"Api-Key {settings.postbox_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.postbox_api_url, json=payload, headers=headers)
            if resp.status_code in (200, 201, 202):
                logger.info("OTP email sent to %s", to_email)
                return True
            logger.error("Postbox API error %s: %s", resp.status_code, resp.text)
            return False
    except httpx.HTTPError as e:
        logger.exception("Postbox HTTP error: %s", e)
        return False
