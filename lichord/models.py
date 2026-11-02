from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Track:
    id: str
    title: str
    artist: str = ""
    album: str = ""
    duration: float | None = None
    artwork: str | None = None
    provider: str = "youtube_music"
    webpage_url: str | None = None

    def addon_json(self) -> dict[str, Any]:
        """Serialize only fields BitChord's AddonTrack parser consumes."""
        row: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "format": "",
            "audioQuality": "HIGH",
        }
        if self.duration is not None and self.duration > 0:
            row["duration"] = float(self.duration)
        if self.artwork:
            row["artworkURL"] = self.artwork
        return row


@dataclass(frozen=True, slots=True)
class Stream:
    url: str
    ext: str = ""
    codec: str = ""
    bitrate_kbps: float | None = None
    sample_rate: int | None = None

    def addon_json(self) -> dict[str, Any]:
        # Do not label YouTube audio as lossless: the extractor's codec and
        # container are reported as observed, never inferred from requested tier.
        result: dict[str, Any] = {"url": self.url}
        if self.ext:
            result["format"] = self.ext
            result["container"] = self.ext
        if self.codec:
            result["codec"] = self.codec
        if self.bitrate_kbps is not None:
            result["bitrate"] = round(self.bitrate_kbps)
        if self.sample_rate is not None:
            result["sampleRate"] = self.sample_rate
        result["quality"] = "HIGH"
        return result
