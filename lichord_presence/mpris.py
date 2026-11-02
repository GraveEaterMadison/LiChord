from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from .discord_ipc import DiscordIPC, build_activity

log = logging.getLogger("lichord.presence")

def _value(metadata: dict[str, Any], key: str, default=None):
    item = metadata.get(key)
    return getattr(item, "value", item) if item is not None else default

def _track(metadata: dict[str, Any]) -> dict[str, Any] | None:
    title = str(_value(metadata, "xesam:title", "") or "").strip()
    if not title:
        return None
    artists = _value(metadata, "xesam:artist", []) or []
    artist = ", ".join(str(x) for x in artists) if isinstance(artists, (list, tuple)) else str(artists)
    album = str(_value(metadata, "xesam:album", "") or "")
    art = str(_value(metadata, "mpris:artUrl", "") or "")
    url = str(_value(metadata, "xesam:url", "") or "")
    track_id = str(_value(metadata, "mpris:trackid", "") or "")
    parsed = urlparse(url or track_id)
    video_id = parse_qs(parsed.query).get("v", [None])[0]
    if not video_id and parsed.netloc.endswith("youtu.be"):
        video_id = parsed.path.strip("/")
    return {"title": title, "artist": artist, "album": album, "artwork": art or None,
            "url": url if url.startswith(("https://", "http://")) else None,
            "video_id": video_id, "local": not bool(url.startswith(("https://", "http://")))}

class MprisPresence:
    def __init__(self, config):
        self.config = config
        self.client: DiscordIPC | None = None
        self.last_payload: str | None = None
        self.last_send = 0.0
        self.last_track_key: str | None = None
        self.was_playing = False
        self._last_status = ""

    async def run(self):
        try:
            from dbus_next import Message, MessageType
            from dbus_next.aio import MessageBus
        except ImportError as exc:
            raise RuntimeError("Install the presence extra: pip install 'lichord-addon[presence]'") from exc

        bus = await MessageBus().connect()
        log.info("Connected to the session D-Bus; waiting for MPRIS players")
        while True:
            try:
                names_reply = await bus.call(Message(destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus", interface="org.freedesktop.DBus",
                    member="ListNames"))
                names = names_reply.body[0] if names_reply.message_type == MessageType.METHOD_RETURN else []
                services = [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]
                snapshots = []
                for service in services:
                    try:
                        intro = await bus.introspect(service, "/org/mpris/MediaPlayer2")
                        obj = bus.get_proxy_object(service, "/org/mpris/MediaPlayer2", intro)
                        props = obj.get_interface("org.freedesktop.DBus.Properties")
                        data = await props.call_get_all("org.mpris.MediaPlayer2.Player")
                        values = {k: v.value for k, v in data.items()}
                        status = values.get("PlaybackStatus", "Stopped")
                        metadata = values.get("Metadata", {})
                        snapshots.append((status == "Playing", status, metadata,
                                          values.get("Position", 0)))
                    except Exception:
                        log.debug("MPRIS player %s unavailable", service, exc_info=True)
                playing = next((x for x in snapshots if x[0]), None)
                current = playing or next((x for x in snapshots if x[1] == "Paused"), None)
                if current:
                    is_playing, status, metadata, pos_us = current
                    track = _track(metadata)
                    if track:
                        duration_us = _value(metadata, "mpris:length", 0) or 0
                        position = max(0.0, float(pos_us or 0) / 1_000_000)
                        duration = max(0.0, float(duration_us) / 1_000_000)
                        await self._publish(track, is_playing, position, duration)
                    else:
                        self._clear()
                else:
                    self._clear()
            except Exception:
                log.warning("MPRIS poll failed", exc_info=True)
            await asyncio.sleep(1.0)

    async def _publish(self, track, playing, position, duration):
        if not self.config.enabled:
            self._clear()
            return
        if not playing and not self.config.show_paused:
            self._clear()
            return
        key = "|".join(str(track.get(k) or "") for k in ("title", "artist", "album", "url"))
        if key != self.last_track_key:
            self.last_track_key = key
            self.last_payload = None
        if not self.config.application_id:
            return
        import time
        now = time.time()
        activity = build_activity(self.config, track, playing, position, duration, now)
        payload = __import__("json").dumps(activity, sort_keys=True)
        # Refresh every 45 seconds, and immediately for track/config/pause/seek changes.
        expected_elapsed = now - (position if playing else 0)
        if payload == self.last_payload and now - self.last_send < 45:
            return
        if now - self.last_send < 1.5:
            return
        if self.client is None:
            self.client = DiscordIPC(self.config.application_id)
            try:
                self.client.connect()
            except Exception:
                self.client = None
                return
        try:
            self.client.set_activity(activity)
            self.last_payload = payload
            self.last_send = now
            self.was_playing = playing
        except Exception:
            log.warning("Discord presence update failed; reconnecting", exc_info=True)
            self.client.close()
            self.client = None

    def _clear(self):
        if self.client:
            try: self.client.clear()
            except Exception: pass
            self.client.close()
            self.client = None
        self.last_payload = None
        self.last_track_key = None
