"""Uploaded pictures. Files live under MEDIA_DIR and nginx serves them as /media/...

Every picture is re-encoded: rotated by EXIF, then all metadata (GPS included) is dropped,
it is scaled down, and saved as JPEG under a random name.
"""

from __future__ import annotations
import io
import uuid
import warnings
from pathlib import Path
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.database import on_commit, on_rollback
from app.utils.errors import photo_bad_type, photo_too_large

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
JPEG_QUALITY = 82
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_SIDE = 512
# Bomb guard: a 10 MB picture can unpack into gigabytes.
Image.MAX_IMAGE_PIXELS = 50_000_000


def reencode(data: bytes, *, max_side: int, square: bool = False) -> tuple[bytes, int, int]:
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
            if square:
                side = min(max_side, *img.size)
                img = ImageOps.fit(img, (side, side), Image.Resampling.LANCZOS)
            else:
                img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            # No exif=...: the source's metadata never reaches the file.
            img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            return out.getvalue(), img.width, img.height
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise photo_too_large()
    except (OSError, SyntaxError, ValueError):
        raise photo_bad_type()


async def read_upload(upload) -> bytes:
    """Read an uploaded file without accepting more than MAX_UPLOAD_BYTES."""
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise photo_too_large()
    return data


def store(db, folder: Path, jpeg: bytes) -> str:
    """Write a new file; it is removed again if the transaction rolls back."""
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.jpg"
    tmp = folder / f".{file_name}.tmp"
    tmp.write_bytes(jpeg)
    final = folder / file_name
    tmp.replace(final)
    on_rollback(db, lambda: final.unlink(missing_ok=True))
    return file_name


def remove_after_commit(db, path: Path) -> None:
    on_commit(db, lambda: path.unlink(missing_ok=True))


# ── Avatars ───────────────────────────────────────────

def avatar_dir() -> Path:
    return Path(settings.media_dir) / "avatars"


def avatar_url(file_name: str | None) -> str | None:
    return f"{settings.media_url}/avatars/{file_name}" if file_name else None


async def set_avatar(db, user, data: bytes) -> None:
    jpeg, _, _ = await run_in_threadpool(reencode, data, max_side=AVATAR_SIDE, square=True)
    drop_avatar(db, user)
    user.avatar_file = store(db, avatar_dir(), jpeg)
    await db.flush()


def drop_avatar(db, user) -> None:
    if user.avatar_file:
        remove_after_commit(db, avatar_dir() / user.avatar_file)
        user.avatar_file = None
