"""Контакт автора карточки: Telegram, WhatsApp, Max, телефон или что-то другое."""

from __future__ import annotations
import re
from typing import Optional, Tuple

CONTACT_TYPES = ("telegram", "whatsapp", "max", "phone", "other")
CONTACT_VALUE_MAX = 100

_TELEGRAM_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")
_TELEGRAM_PREFIX_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/", re.IGNORECASE)


def _normalize_phone(value: str) -> Optional[str]:
    """Привести номер к E.164 (+79991234567). Российские 8XXXXXXXXXX → +7XXXXXXXXXX."""
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if not raw.startswith("+") and len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        return None
    return "+" + digits


def normalize_contact(contact_type: str, value: str) -> Tuple[Optional[str], Optional[str]]:
    """Вернуть (нормализованное значение, None) или (None, сообщение об ошибке)."""
    value = value.strip()
    if contact_type not in CONTACT_TYPES:
        return None, "Допустимо: " + ", ".join(CONTACT_TYPES)
    if contact_type == "telegram":
        username = _TELEGRAM_PREFIX_RE.sub("", value).lstrip("@")
        if not _TELEGRAM_RE.match(username):
            return None, "Telegram: 5-32 символа, латинские буквы, цифры, _"
        return username, None
    if contact_type in ("phone", "whatsapp"):
        phone = _normalize_phone(value)
        if phone is None:
            return None, "Неверный номер телефона"
        return phone, None
    if not value:
        return None, "Укажите контакт"
    if len(value) > CONTACT_VALUE_MAX:
        return None, f"Не длиннее {CONTACT_VALUE_MAX} символов"
    return value, None


def contact_url(contact_type: str, value: str) -> Optional[str]:
    if contact_type == "telegram":
        return f"https://t.me/{value}"
    if contact_type == "whatsapp":
        return f"https://wa.me/{value.lstrip('+')}"
    if contact_type == "phone":
        return f"tel:{value}"
    return None
