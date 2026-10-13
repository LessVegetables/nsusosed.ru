from __future__ import annotations
import json
from pathlib import Path
from typing import List
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
    cookie_name: str = "__Host-nsusosed"

    # ── Yandex Cloud Postbox ────────────────────────────
    postbox_api_key: str = ""
    postbox_sender_email: str = ""
    postbox_api_url: str = "https://postbox.cloud.yandex.net/api/v1/send"

    # ── OTP ─────────────────────────────────────────────
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_code_length: int = 6

    @property
    def email_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


settings = Settings()

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
with open(_CONFIG_DIR / "questionnaire_v1.json", encoding="utf-8") as _f:
    QUESTIONNAIRE_V1: dict = json.load(_f)
with open(_CONFIG_DIR / "matching.json", encoding="utf-8") as _f:
    MATCHING_CONFIG: dict = json.load(_f)
