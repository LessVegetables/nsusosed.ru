from __future__ import annotations
import hashlib
import secrets
import unicodedata


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_building(building: str) -> str:
    s = unicodedata.normalize("NFKC", building).strip().upper()
    if s.isdigit():
        s = str(int(s))
    return s


def validate_email_domain(email: str, allowed_domains: list[str]) -> bool:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return False
    domain = normalized.rsplit("@", 1)[1]
    return domain in allowed_domains

