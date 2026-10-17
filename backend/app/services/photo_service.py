"""Фото жилья. Файлы лежат в MEDIA_DIR/listings/<listing_id>/, nginx отдаёт их как /media/..."""

from __future__ import annotations
import shutil
import uuid
from pathlib import Path
from app.config import settings


def listing_dir(listing_id: uuid.UUID) -> Path:
    return Path(settings.media_dir) / "listings" / str(listing_id)


def photo_url(listing_id: uuid.UUID, file_name: str) -> str:
    return f"{settings.media_url}/listings/{listing_id}/{file_name}"


def delete_listing_files(listing_id: uuid.UUID) -> None:
    shutil.rmtree(listing_dir(listing_id), ignore_errors=True)
