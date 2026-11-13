"""Address search for the "add an apartment" form.

The host types an address to find their building on the map. The address goes to
OpenStreetMap's Nominatim and the candidates come straight back to the browser; nothing about
it is stored or written to a log here. The browser then moves the point off the real spot and
only that obfuscated circle is ever saved (see schemas/home.py).
"""

from __future__ import annotations
import asyncio
import logging
import time
import httpx
from app.utils.errors import AppError, rate_limited

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy asks for an identifying User-Agent and at most one request a second.
USER_AGENT = "nsusosed.ru/1.0 (support@nsusosed.ru)"
# Novosibirsk, Akademgorodok, Koltsovo, Berdsk: left, top, right, bottom.
VIEWBOX = "82.3,55.4,83.9,54.5"
USER_COOLDOWN_SECONDS = 2.0

# httpx logs every request URL at INFO, and this URL contains the address being searched.
# Addresses must not end up in our logs, so httpx only gets to log warnings and errors.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=8.0, headers={"User-Agent": USER_AGENT})


_last_by_user: dict[str, float] = {}
_upstream = asyncio.Lock()
_last_upstream = 0.0


def _district(address: dict) -> str:
    for key in ("suburb", "city_district", "neighbourhood", "quarter", "town", "village", "city"):
        if address.get(key):
            return str(address[key])[:60]
    return ""


def _label(item: dict) -> str:
    a = item.get("address", {})
    street = " ".join(str(a[k]) for k in ("road", "house_number") if a.get(k))
    place = a.get("suburb") or a.get("city_district") or a.get("city") or a.get("town") or a.get("village") or ""
    return ", ".join(p for p in (street, place) if p) or str(item.get("display_name", ""))[:120]


async def search(user_id, query: str, language: str) -> list[dict]:
    """Up to five places matching the address: [{label, lat, lon, district}]."""
    global _last_upstream
    now = time.monotonic()
    key = str(user_id)
    wait = USER_COOLDOWN_SECONDS - (now - _last_by_user.get(key, 0.0))
    if wait > 0:
        raise rate_limited(max(1, round(wait)))
    _last_by_user[key] = now
    if len(_last_by_user) > 10_000:
        _last_by_user.clear()

    params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5, "countrycodes": "ru",
              "viewbox": VIEWBOX, "bounded": 1, "accept-language": "zh-CN" if language == "zh" else language}
    async with _upstream:  # one request a second to Nominatim, whoever is asking
        pause = 1.0 - (time.monotonic() - _last_upstream)
        if pause > 0:
            await asyncio.sleep(pause)
        try:
            async with _client() as client:
                response = await client.get(NOMINATIM_URL, params=params)
        except httpx.HTTPError:
            raise AppError(503, "GEO_UNAVAILABLE", "Поиск по карте сейчас недоступен. Поставьте точку на карте вручную.")
        finally:
            _last_upstream = time.monotonic()
    if not response.is_success:
        raise AppError(503, "GEO_UNAVAILABLE", "Поиск по карте сейчас недоступен. Поставьте точку на карте вручную.")
    results: dict[str, dict] = {}
    for item in response.json():
        label = _label(item)
        # One building is often several map objects (the building, its entrance, an office in it).
        results.setdefault(label, {"label": label, "lat": round(float(item["lat"]), 6), "lon": round(float(item["lon"]), 6),
                                   "district": _district(item.get("address", {}))})
    return list(results.values())
