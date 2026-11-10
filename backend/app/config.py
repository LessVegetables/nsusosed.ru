from __future__ import annotations
import json
from pathlib import Path
from typing import List, Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://nsusosed:nsusosed@localhost:5432/nsusosed"
    public_origin: str = "http://localhost:8000"
    # Each domain also allows all of its subdomains (nsu.ru → g.nsu.ru, …).
    allowed_email_domains: str = "nsu.ru"
    # 90 days, sliding: every visit in the second half of the term renews it.
    session_ttl_seconds: int = 7_776_000
    max_sessions_per_user: int = 5
    # Удалённый аккаунт сначала только скрыт: вход в течение этого срока его восстанавливает.
    account_deletion_grace_days: int = 14
    # Фото жилья: файлы на диске, nginx отдаёт их как /media/...
    media_dir: str = "/data/media"
    media_url: str = "/media"
    cookie_name: str = "__Host-nsusosed"
    # Secure cookies need https. Chrome makes an exception for http://localhost, Safari and
    # some in-app browsers do not, so local development over http drops the flag (and the
    # __Host- prefix, which browsers only accept on Secure cookies). Derived from PUBLIC_ORIGIN.
    cookie_secure: bool = True

    # ── Yandex Cloud Postbox ────────────────────────────
    # postbox — отправлять письма; log — писать коды в лог (только для разработки)
    email_mode: Literal["postbox", "log"] = "postbox"
    # Статический ключ доступа сервисного аккаунта с ролью postbox.sender
    # (не API-ключ: API-ключи Postbox принимает только по SMTP).
    postbox_access_key_id: str = ""
    postbox_secret_access_key: str = ""
    postbox_sender_email: str = ""
    postbox_endpoint: str = "https://postbox.cloud.yandex.net"
    postbox_region: str = "ru-central1"

    # ── OTP ─────────────────────────────────────────────
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_code_length: int = 6

    # ── Ограничение частоты входа ───────────────────────
    otp_resend_cooldown_seconds: int = 60
    otp_max_requests_per_hour: int = 5
    otp_max_failed_verifies_per_hour: int = 10
    auth_ip_max_requests: int = 20
    auth_ip_window_seconds: int = 600

    @model_validator(mode="after")
    def check_email_settings(self) -> "Settings":
        if self.email_mode == "postbox" and not (
            self.postbox_access_key_id and self.postbox_secret_access_key and self.postbox_sender_email
        ):
            raise ValueError(
                "EMAIL_MODE=postbox requires POSTBOX_ACCESS_KEY_ID, POSTBOX_SECRET_ACCESS_KEY "
                "and POSTBOX_SENDER_EMAIL (set EMAIL_MODE=log for local development)"
            )
        return self

    @model_validator(mode="after")
    def relax_cookie_for_http(self) -> "Settings":
        if self.public_origin.startswith("http://"):
            self.cookie_secure = False
            self.cookie_name = self.cookie_name.removeprefix("__Host-")
        return self

    @property
    def email_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


settings = Settings()

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
with open(_CONFIG_DIR / "faculties.json", encoding="utf-8") as _f:
    FACULTIES: list[dict] = json.load(_f)["faculties"]
with open(_CONFIG_DIR / "dorms.json", encoding="utf-8") as _f:
    DORMS: list[dict] = json.load(_f)["dorms"]
FACULTY_IDS = {f["id"] for f in FACULTIES}
