from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from concurrent.futures import Future
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import __version__
from .providers import ProviderHub

log = logging.getLogger("lichord")
app = FastAPI(title="LiChord BitChord Addon", version=__version__)
hub = ProviderHub()

_CACHE: OrderedDict[tuple, tuple[float, list[dict]]] = OrderedDict()
_CACHE_LOCK = __import__("threading").RLock()
_CACHE_INFLIGHT: dict[tuple, Future] = {}
_CACHE_TTL = 90
_CACHE_MAX = 128

AUTH_HOSTS = tuple(
    host.strip().lower().rstrip(".")
    for host in os.getenv("BITCHORD_HOSTS", "").split(",")
    if host.strip()
)
AUTH_MODE = os.getenv("BITCHORD_AUTH_MODE", "log" if AUTH_HOSTS else "off").strip().lower()
if AUTH_MODE not in {"off", "log", "enforce"}:
    raise RuntimeError("BITCHORD_AUTH_MODE must be off, log, or enforce")
if AUTH_MODE == "enforce" and not AUTH_HOSTS:
    raise RuntimeError("BITCHORD_HOSTS must list the public addon hostname before auth enforcement")
if AUTH_MODE != "off" and AUTH_HOSTS:
    from bitchord_addon_auth import BitChordAuth
    _BITCHORD_AUTH = BitChordAuth(hosts=AUTH_HOSTS)
else:
    _BITCHORD_AUTH = None


def _cached_search(key: tuple, loader):
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > now:
            _CACHE.move_to_end(key)
            return hit[1]
        if hit:
            del _CACHE[key]
        future = _CACHE_INFLIGHT.get(key)
        owner = future is None
        if owner:
            future = Future()
            _CACHE_INFLIGHT[key] = future
    if not owner:
        return future.result()
    try:
        result = loader()
        with _CACHE_LOCK:
            _CACHE[key] = (time.monotonic() + _CACHE_TTL, result)
            _CACHE.move_to_end(key)
            while len(_CACHE) > _CACHE_MAX:
                _CACHE.popitem(last=False)
        future.set_result(result)
        return result
    except BaseException as exc:
        future.set_exception(exc)
        raise
    finally:
        with _CACHE_LOCK:
            _CACHE_INFLIGHT.pop(key, None)


@app.middleware("http")
async def protect_addon_routes(request: Request, call_next):
    if request.url.path == "/manifest.json" or _BITCHORD_AUTH is None:
        return await call_next(request)
    result = await run_in_threadpool(_BITCHORD_AUTH.verify_headers, request.headers)
    if not result.ok:
        log.warning("BitChord authentication check failed: %s", result.error)
        if AUTH_MODE == "enforce":
            return Response(result.body, status_code=result.status, headers=result.headers,
                            media_type="application/json")
    return await call_next(request)


@app.get("/manifest.json")
def manifest():
    data = {
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
    if _BITCHORD_AUTH is not None:
        data["bitchordAuth"] = True
    return data


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
        rows = _cached_search(key, lambda: [
            track.addon_json() for track in hub.search(query, count, region, provider)
        ])
        return {"tracks": rows}
    except Exception as exc:
        log.exception("Search failed")
        raise HTTPException(status_code=502, detail="Search providers are temporarily unavailable") from exc


@app.get("/stream/{track_id:path}")
def stream(track_id: str, quality: str = "HIGH", provider: str | None = None):
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
    level = os.getenv("LICHORD_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))
    uvicorn.run("lichord.server:app", host=os.getenv("LICHORD_HOST", "0.0.0.0"),
                port=int(os.getenv("LICHORD_PORT", "8787")), reload=False)
