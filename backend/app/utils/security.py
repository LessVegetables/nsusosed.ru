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
    local, domain = normalized.rsplit("@", 1)
    if not local or ".." in domain or domain.startswith("."):
        return False
    # An allowed domain covers its subdomains at any depth: nsu.ru → g.nsu.ru, a.b.nsu.ru.
    return any(domain == d or domain.endswith("." + d) for d in allowed_domains)

