from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from threading import Lock, RLock
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import __version__
from .providers import ProviderHub

log = logging.getLogger("lichord")

app = FastAPI(title="LiChord BitChord Addon", version=__version__)
hub = ProviderHub()

# Tiny bounded in-memory search cache. Stream URLs are deliberately never cached:
# signed media URLs expire and must be freshly resolved on every playback request.
_CACHE: OrderedDict[tuple, tuple[float, list[dict]]] = OrderedDict()
_CACHE_LOCK = RLock()
_CACHE_KEY_LOCKS: dict[tuple, Lock] = {}
_CACHE_TTL = 90
_CACHE_MAX = 128


def _setting(value: str | None, default: str) -> str:
    return (value or default).strip()


def _cached_search(key: tuple, loader):
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > now:
            _CACHE.move_to_end(key)
            return hit[1]
        if hit:
            del _CACHE[key]
        key_lock = _CACHE_KEY_LOCKS.setdefault(key, Lock())

    try:
        with key_lock:
            now = time.monotonic()
            with _CACHE_LOCK:
                hit = _CACHE.get(key)
                if hit and hit[0] > now:
                    _CACHE.move_to_end(key)
                    return hit[1]
            result = loader()
            with _CACHE_LOCK:
                _CACHE[key] = (time.monotonic() + _CACHE_TTL, result)
                _CACHE.move_to_end(key)
                while len(_CACHE) > _CACHE_MAX:
                    _CACHE.popitem(last=False)
            return result
    finally:
        with _CACHE_LOCK:
            if not key_lock.locked():
                _CACHE_KEY_LOCKS.pop(key, None)


@app.get("/manifest.json")
def manifest():
    return {
        "id": "lichord-multicatalogue",
        "name": "LiChord · Multi-catalogue",
        "version": __version__,
        "description": "Search and stream tracks from YouTube Music, YouTube and SoundCloud.",
        "resources": ["search", "stream"],
        "settings": [
            {"key": "provider", "type": "select", "label": "Catalogue", "default": "all",
             "options": [{"value": "all", "label": "All catalogues"},
                         {"value": "youtube_music", "label": "YouTube Music"},
                         {"value": "youtube", "label": "YouTube"},
                         {"value": "soundcloud", "label": "SoundCloud"}]},
            {"key": "region", "type": "text", "label": "Region", "default": "IN"},
            {"key": "limit", "type": "select", "label": "Results per search", "default": "15",
             "options": [{"value": "5"}, {"value": "10"}, {"value": "15"}, {"value": "25"}]},
        ],
        "allowDownloads": 0,
        "checkValidLossless": 0,
    }


@app.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    provider: str = "all", region: str = "IN", limit: str = "15", quality: str = "HIGH",
):
    query = q.strip()
    if not query:
        return {"tracks": []}
    try:
        count = max(1, min(int(limit), 25))
    except ValueError:
        count = 15
    region = re.sub(r"[^A-Za-z]", "", region).upper()[:2] or "IN"
    provider = provider if provider in {"all", "youtube_music", "youtube", "soundcloud"} else "all"
    key = (query.casefold(), provider, region, count)
    try:
        rows = _cached_search(key, lambda: [t.addon_json() for t in hub.search(query, count, region, provider)])
        return {"tracks": rows}
    except Exception as exc:
        log.exception("Search failed")
        raise HTTPException(status_code=502, detail="Search providers are temporarily unavailable") from exc


@app.get("/stream/{track_id:path}")
def stream(track_id: str, quality: str = "HIGH", provider: str | None = None):
    # IDs are intentionally opaque but bounded. The provider is encoded in the ID
    # so no caller-supplied URL can turn this endpoint into an open proxy.
    track_id = unquote(track_id)
    if not track_id or len(track_id) > 300 or "/" in track_id or "\\" in track_id:
        raise HTTPException(status_code=404, detail="Unknown track")
    if quality.upper() not in {"LOW", "HIGH", "LOSSLESS"}:
        quality = "HIGH"
    try:
        return hub.stream(track_id, quality.upper()).addon_json()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Stream resolution failed for %s", track_id)
        raise HTTPException(status_code=502, detail="Could not resolve a playable stream") from exc


@app.get("/health")
def health():
    return {"status": "ok", "addon": "LiChord", "version": __version__}


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, exc: Exception):
    log.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal addon error"})


def run() -> None:
    import uvicorn
    uvicorn.run("lichord.server:app", host=os.getenv("LICHORD_HOST", "0.0.0.0"),
                port=int(os.getenv("LICHORD_PORT", "8787")), reload=False)
