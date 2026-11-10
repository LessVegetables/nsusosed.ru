"""Contact methods a person can list: where a seeker writes to a host.

Primary (the audience really uses them): phone, Telegram, VK.
Extra (nice to have): Max, Instagram, Snapchat, WeChat.
Anyone who lists a contact at all must list a primary one, so a listing never ends up
reachable only through a messenger most students don't have.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

PRIMARY_TYPES = ("phone", "telegram", "vk")
EXTRA_TYPES = ("max", "instagram", "snapchat", "wechat")
CONTACT_TYPES = PRIMARY_TYPES + EXTRA_TYPES
CONTACT_VALUE_MAX = 100

_PREFIX = {
    "telegram": re.compile(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/", re.I),
    "vk": re.compile(r"^(?:https?://)?(?:www\.|m\.)?(?:vk\.com|vk\.ru)/", re.I),
    "instagram": re.compile(r"^(?:https?://)?(?:www\.)?instagram\.com/", re.I),
    "snapchat": re.compile(r"^(?:https?://)?(?:www\.)?snapchat\.com/add/", re.I),
}
_USERNAME = {
    "telegram": (re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{3,31}$"), "INVALID_TELEGRAM"),
    "vk": (re.compile(r"^[a-zA-Z0-9_.]{2,32}$"), "INVALID_VK"),
    "instagram": (re.compile(r"^[a-zA-Z0-9_.]{1,30}$"), "INVALID_INSTAGRAM"),
    "snapchat": (re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{2,14}$"), "INVALID_SNAPCHAT"),
    "wechat": (re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-]{5,19}$"), "INVALID_WECHAT"),
}
_URL = {
    "phone": "tel:{}",
    "telegram": "https://t.me/{}",
    "vk": "https://vk.com/{}",
    "instagram": "https://instagram.com/{}",
    "snapchat": "https://www.snapchat.com/add/{}",
}


def normalize_phone(value: str) -> Optional[str]:
    """Russian mobile number → +7XXXXXXXXXX. Accepts +7…, 8…, 7… and the bare ten digits."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "+7" + digits


def normalize_contact(contact_type: str, value: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (normalized value, None) or (None, reason code)."""
    value = value.strip()
    if contact_type not in CONTACT_TYPES:
        return None, "INVALID_CHOICE"
    if not value:
        return None, "REQUIRED"
    if len(value) > CONTACT_VALUE_MAX:
        return None, "TOO_LONG"
    if contact_type == "phone":
        phone = normalize_phone(value)
        return (phone, None) if phone else (None, "INVALID_PHONE")
    if contact_type == "max":
        # Max accounts are tied to a phone number; people share either that or a profile link.
        phone = normalize_phone(value)
        if phone:
            return phone, None
        return (value, None) if len(value) >= 2 else (None, "INVALID_MAX")
    if contact_type in _PREFIX:
        value = _PREFIX[contact_type].sub("", value).split("?")[0].rstrip("/")
    value = value.lstrip("@")
    pattern, reason = _USERNAME[contact_type]
    return (value, None) if pattern.match(value) else (None, reason)


def contact_url(contact_type: str, value: str) -> Optional[str]:
    template = _URL.get(contact_type)
    return template.format(value) if template else None
