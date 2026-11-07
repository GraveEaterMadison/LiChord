from __future__ import annotations

import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import BoundedSemaphore, RLock
from typing import Protocol
from urllib.parse import quote

from .models import Stream, Track

log = logging.getLogger("lichord.providers")
_SEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="lichord-search")
_EXTRACTOR_LIMIT = BoundedSemaphore(4)


class Provider(Protocol):
    name: str
    def search(self, query: str, limit: int, region: str) -> list[Track]: ...
    def stream(self, track_id: str, quality: str) -> Stream: ...


class ProviderSearchError(RuntimeError):
    """Raised when every selected catalogue fails to answer a search."""


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _thumbnail(items: object) -> str | None:
    if isinstance(items, list):
        for item in reversed(items):
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])
    return None


class YouTubeMusicProvider:
    name = "youtube_music"

    def __init__(self) -> None:
        self._clients = {}
        self._client_lock = RLock()

    def _client(self, region: str):
        region = (region or "IN").upper()
        with self._client_lock:
            if region not in self._clients:
                try:
                    from ytmusicapi import YTMusic
                except ImportError as exc:
                    raise RuntimeError("Install the ytmusicapi dependency") from exc
                self._clients[region] = YTMusic(language="en", location=region)
            return self._clients[region]

    def search(self, query: str, limit: int, region: str) -> list[Track]:
        with _EXTRACTOR_LIMIT:
            results = self._client(region).search(query, filter="songs", limit=limit)
        tracks = []
        for item in results:
            video_id = _clean(item.get("videoId"))
            title = _clean(item.get("title"))
            if not video_id or not title:
                continue
            artists = item.get("artists") or []
            artist = ", ".join(_clean(a.get("name")) for a in artists if isinstance(a, dict))
            album = item.get("album") or {}
            tracks.append(Track(
                id=f"ytm:{video_id}", title=title, artist=artist,
                album=_clean(album.get("name")) if isinstance(album, dict) else "",
                duration=float(item["duration_seconds"]) if item.get("duration_seconds") else None,
                artwork=_thumbnail(item.get("thumbnails")), provider=self.name,
                webpage_url=f"https://music.youtube.com/watch?v={quote(video_id)}",
            ))
        return tracks

    def stream(self, track_id: str, quality: str) -> Stream:
        video_id = track_id.removeprefix("ytm:")
        return _yt_dlp_stream(f"https://music.youtube.com/watch?v={quote(video_id)}", quality)


class ExtractorSearchProvider:
    """Search YouTube or SoundCloud through yt-dlp without downloading media."""
    def __init__(self, name: str, prefix: str, search_prefix: str):
        self.name, self.prefix, self.search_prefix = name, prefix, search_prefix

    def search(self, query: str, limit: int, region: str) -> list[Track]:
        ydl = _ydl({"extract_flat": True, "playlistend": limit})
        with _EXTRACTOR_LIMIT:
            info = ydl.extract_info(f"{self.search_prefix}{limit}:{query}", download=False)
        entries = (info or {}).get("entries") or []
        out = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ident, title = _clean(entry.get("id")), _clean(entry.get("title"))
            if not ident or not title:
                continue
            webpage = entry.get("webpage_url") or entry.get("url")
            if self.prefix == "sc":
                if not isinstance(webpage, str) or not webpage.startswith("https://soundcloud.com/"):
                    continue
                opaque_id = base64.urlsafe_b64encode(webpage.encode()).decode().rstrip("=")
            else:
                opaque_id = ident
                webpage = f"https://www.youtube.com/watch?v={quote(ident)}"
            out.append(Track(
                id=f"{self.prefix}:{opaque_id}", title=title,
                artist=_clean(entry.get("uploader") or entry.get("channel") or entry.get("artist")),
                album=_clean(entry.get("album")), duration=float(entry["duration"]) if entry.get("duration") else None,
                artwork=entry.get("thumbnail"), provider=self.name, webpage_url=webpage,
            ))
        return out

    def stream(self, track_id: str, quality: str) -> Stream:
        ident = track_id.removeprefix(f"{self.prefix}:")
        if self.prefix == "sc":
            try:
                url = base64.urlsafe_b64decode(ident + "=" * (-len(ident) % 4)).decode()
            except Exception as exc:
                raise LookupError("Invalid SoundCloud track id") from exc
            if not url.startswith("https://soundcloud.com/"):
                raise LookupError("Invalid SoundCloud permalink")
        else:
            url = f"https://www.youtube.com/watch?v={quote(ident)}"
        return _yt_dlp_stream(url, quality)


def _ydl(options: dict):
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("Install the yt-dlp dependency") from exc
    base = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "ignoreerrors": False,
        "extractor_retries": 2, "socket_timeout": 15,
    }
    base.update(options)
    return yt_dlp.YoutubeDL(base)


def _yt_dlp_stream(url: str, quality: str) -> Stream:
    fmt = "worstaudio/best" if quality.upper() == "LOW" else "bestaudio/best"
    with _EXTRACTOR_LIMIT:
        info = _ydl({"format": fmt}).extract_info(url, download=False)
    if not isinstance(info, dict):
        raise LookupError("No playable stream was returned")
    formats = info.get("requested_formats") or []
    audio = [f for f in formats if isinstance(f, dict) and f.get("acodec") not in (None, "none")]
    chosen = max(audio, key=lambda f: float(f.get("abr") or 0)) if audio else info
    stream_url = chosen.get("url") or info.get("url")
    if not isinstance(stream_url, str) or not stream_url.startswith("https://"):
        raise LookupError("Extractor returned no secure HTTPS audio URL")
    return Stream(
        url=stream_url, ext=_clean(chosen.get("ext") or info.get("ext")),
        codec=_clean(chosen.get("acodec") or info.get("acodec")),
        bitrate_kbps=float(chosen["abr"]) if chosen.get("abr") else None,
        sample_rate=int(chosen["asr"]) if chosen.get("asr") else None,
    )


class ProviderHub:
    def __init__(self, providers: dict[str, Provider] | None = None):
        self.providers = providers or {
            "youtube_music": YouTubeMusicProvider(),
            "youtube": ExtractorSearchProvider("youtube", "yt", "ytsearch"),
            "soundcloud": ExtractorSearchProvider("soundcloud", "sc", "scsearch"),
        }

    def search(self, query: str, limit: int, region: str, selection: str) -> list[Track]:
        names = list(self.providers) if selection == "all" else [selection]
        if selection not in self.providers and selection != "all":
            raise ValueError(f"Unsupported provider: {selection}")
        if not names:
            raise ProviderSearchError("No search providers are configured")
        results_by_provider: dict[str, list[Track]] = {}
        failed = []
        futures = {
            _SEARCH_EXECUTOR.submit(self.providers[name].search, query, limit, region): name
            for name in names
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results_by_provider[name] = future.result()
            except Exception:
                failed.append(name)
                log.exception("Search provider %s failed", name)
        if len(failed) == len(names):
            raise ProviderSearchError("Every selected search provider failed")
        found = [
            track
            for name in names
            for track in results_by_provider.get(name, [])
        ]
        seen, deduped = set(), []
        for track in found:
            key = (_clean(track.title).casefold(), _clean(track.artist).casefold())
            if key not in seen:
                seen.add(key)
                deduped.append(track)
        return deduped[:limit]

    def stream(self, track_id: str, quality: str) -> Stream:
        prefix = track_id.split(":", 1)[0]
        provider_name = {"ytm": "youtube_music", "yt": "youtube", "sc": "soundcloud"}.get(prefix)
        if not provider_name or provider_name not in self.providers:
            raise LookupError("Unknown LiChord track id")
        return self.providers[provider_name].stream(track_id, quality)
