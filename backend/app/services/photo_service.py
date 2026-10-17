"""Фото жилья. Файлы лежат в MEDIA_DIR/listings/<listing_id>/, nginx отдаёт их как /media/...

Каждое фото перекодируется: поворот по EXIF, затем все метаданные (в том числе
GPS-координаты) отбрасываются, длинная сторона — не больше MAX_SIDE, формат — JPEG.
"""

from __future__ import annotations
import io
import logging
import shutil
import uuid
import warnings
from pathlib import Path
from PIL import Image, ImageOps
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.models.listing import Listing, ListingPhoto
from app.utils.errors import photo_bad_type, photo_too_large, too_many_photos, not_found, validation_error

logger = logging.getLogger("nsusosed")

MAX_PHOTOS = 10
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600
JPEG_QUALITY = 82
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Защита от «бомб»: картинка в 10 МБ может разжиматься в гигабайты.
Image.MAX_IMAGE_PIXELS = 50_000_000


def listing_dir(listing_id: uuid.UUID) -> Path:
    return Path(settings.media_dir) / "listings" / str(listing_id)


def photo_url(listing_id: uuid.UUID, file_name: str) -> str:
    return f"{settings.media_url}/listings/{listing_id}/{file_name}"


def delete_listing_files(listing_id: uuid.UUID) -> None:
    shutil.rmtree(listing_dir(listing_id), ignore_errors=True)


def _reencode(data: bytes) -> tuple[bytes, int, int]:
    try:
        with warnings.catch_warnings(), Image.open(io.BytesIO(data)) as img:
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            if img.format not in ACCEPTED_FORMATS:
                raise photo_bad_type()
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.getchannel("A"))
                img = background
            else:
                img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            # Без exif=...: метаданные исходника в файл не попадают.
            img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            return out.getvalue(), img.width, img.height
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise photo_too_large()
    except (OSError, SyntaxError, ValueError):
        raise photo_bad_type()


async def read_upload(upload) -> bytes:
    """Прочитать загруженный файл, не принимая больше MAX_UPLOAD_BYTES."""
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise photo_too_large()
    return data


async def add_photo(db, listing: Listing, data: bytes) -> None:
    count = len((await db.execute(select(ListingPhoto.id).where(ListingPhoto.listing_id == listing.id))).all())
    if count >= MAX_PHOTOS:
        raise too_many_photos()
    jpeg, width, height = await run_in_threadpool(_reencode, data)

    folder = listing_dir(listing.id)
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.jpg"
    tmp = folder / f".{file_name}.tmp"
    tmp.write_bytes(jpeg)
    tmp.replace(folder / file_name)

    db.add(ListingPhoto(listing_id=listing.id, position=count, file_name=file_name, width=width, height=height))
    await db.flush()


async def _photos(db, listing_id: uuid.UUID) -> list[ListingPhoto]:
    result = await db.execute(
        select(ListingPhoto).where(ListingPhoto.listing_id == listing_id).order_by(ListingPhoto.position))
    return list(result.scalars().all())


async def delete_photo(db, listing: Listing, photo_id: uuid.UUID) -> None:
    photos = await _photos(db, listing.id)
    photo = next((p for p in photos if p.id == photo_id), None)
    if photo is None:
        raise not_found("Фото не найдено.")
    await db.delete(photo)
    for i, p in enumerate(p for p in photos if p.id != photo_id):
        p.position = i
    await db.flush()
    (listing_dir(listing.id) / photo.file_name).unlink(missing_ok=True)


async def reorder_photos(db, listing: Listing, photo_ids: list[uuid.UUID]) -> None:
    photos = {p.id: p for p in await _photos(db, listing.id)}
    if len(photo_ids) != len(photos) or set(photo_ids) != set(photos):
        raise validation_error("Порядок должен перечислять все фото жилья.", {"photo_ids": "INVALID_SET"})
    for i, photo_id in enumerate(photo_ids):
        photos[photo_id].position = i
    await db.flush()


async def sweep_orphan_folders(db) -> None:
    """Удалить папки фото жилья, которого больше нет (например, после сбоя)."""
    root = Path(settings.media_dir) / "listings"
    if not root.is_dir():
        return
    existing = {str(row[0]) for row in (await db.execute(select(Listing.id))).all()}
    for folder in root.iterdir():
        if folder.is_dir() and folder.name not in existing:
            logger.info("Removing photos of a deleted listing: %s", folder.name)
            shutil.rmtree(folder, ignore_errors=True)
