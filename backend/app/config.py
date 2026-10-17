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
    allowed_email_domains: str = "g.nsu.ru"
    session_ttl_seconds: int = 604_800
    max_sessions_per_user: int = 5
    listing_ttl_days: int = 30
    invite_ttl_days: int = 7
    # Фото жилья: файлы на диске, nginx отдаёт их как /media/...
    media_dir: str = "/data/media"
    media_url: str = "/media"
    cookie_name: str = "__Host-nsusosed"

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
    otp_ttl_seconds: int = 120
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

    @property
    def email_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


settings = Settings()

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
with open(_CONFIG_DIR / "questionnaire_v2.json", encoding="utf-8") as _f:
    QUESTIONNAIRE: dict = json.load(_f)
with open(_CONFIG_DIR / "matching.json", encoding="utf-8") as _f:
    MATCHING_CONFIG: dict = json.load(_f)
