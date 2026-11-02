from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import PresenceConfig
from .discord_ipc import DiscordIPC

log = logging.getLogger("lichord.presence")

def _track(metadata: dict[str, Any]) -> dict[str, Any] | None:
    def val(key, default=None):
        item = metadata.get(key)
        return getattr(item, "value", item) if item is not None else default
    title = str(val("xesam:title", "") or "").strip()
    if not title:
        return None
    artists = val("xesam:artist", []) or []
    artist = ", ".join(str(x) for x in artists) if isinstance(artists, (list, tuple)) else str(artists)
    album = str(val("xesam:album", "") or "")
    art = str(val("mpris:artUrl", "") or "")
    url = str(val("xesam:url", "") or "")
    track_id = str(val("mpris:trackid", "") or "")
    parsed = urlparse(url or track_id)
    video_id = parse_qs(parsed.query).get("v", [None])[0]
    if not video_id and parsed.netloc.endswith("youtu.be"):
        video_id = parsed.path.strip("/")
    external_url = url if url.startswith(("https://", "http://")) else None
    return {"title": title, "artist": artist, "album": album, "artwork": art or None,
            "url": external_url, "video_id": video_id,
            "local": not bool(external_url or video_id)}

class MprisPresence:
    def __init__(self, config: PresenceConfig):
        self.config = config
        self.client: DiscordIPC | None = None
        self.last_signature: str | None = None
        self.last_send = 0.0
        self.last_start_ms: int | None = None
        self.last_track_key: str | None = None
        self.last_connect_try = 0.0
        self.connect_backoff = 1.0
        self.frames: deque[float] = deque()
        self.visible = False

    async def run(self):
        try:
            from dbus_next import Message, MessageType
            from dbus_next.aio import MessageBus
        except ImportError as exc:
            raise RuntimeError("Install the presence extra: pip install 'lichord-addon[presence]'") from exc

        bus = await MessageBus().connect()
        log.info("Connected to the session D-Bus; watching MPRIS players")
        while True:
            self.config = PresenceConfig.load()
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
                        snapshots.append((status == "Playing", status, values.get("Metadata", {}),
                                          values.get("Position", 0)))
                    except Exception:
                        log.debug("MPRIS player %s unavailable", service, exc_info=True)
                current = next((x for x in snapshots if x[0]), None)
                if current is None:
                    current = next((x for x in snapshots if x[1] == "Paused"), None)
                if current:
                    is_playing, _status, metadata, pos_us = current
                    track = _track(metadata)
                    if track:
                        duration_us = metadata.get("mpris:length", 0)
                        duration_us = getattr(duration_us, "value", duration_us) or 0
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

    def _connect(self) -> bool:
        now = time.monotonic()
        if now - self.last_connect_try < self.connect_backoff:
            return False
        self.last_connect_try = now
        client = DiscordIPC(self.config.application_id)
        try:
            client.connect()
            self.client = client
            self.connect_backoff = 1.0
            self.last_signature = None
            log.info("Connected to Discord desktop IPC")
            return True
        except Exception:
            client.close()
            self.connect_backoff = min(15.0, self.connect_backoff * 2)
            log.debug("Discord is not available; retrying in %.0fs", self.connect_backoff,
                      exc_info=True)
            return False

    async def _publish(self, track, playing, position, duration):
        cfg = self.config
        if not cfg.enabled or (not playing and not cfg.show_paused):
            self._clear()
            return
        if not cfg.application_id:
            return

        key = "|".join(str(track.get(k) or "") for k in ("title", "artist", "album", "url"))
        if key != self.last_track_key:
            self.last_track_key = key
            self.last_signature = None
            self.last_start_ms = None

        now_wall = time.time()
        start_ms = int((now_wall - max(0.0, position)) * 1000) if playing and cfg.timestamps and duration > 0 else None
        # Exclude timestamps from the signature: position advances continuously, but Discord
        # should only receive a new frame for a seek, state/config change, track change or refresh.
        from .discord_ipc import build_activity
        activity = build_activity(cfg, track, playing, position, duration, now_wall)
        signature_payload = dict(activity)
        signature_payload.pop("timestamps", None)
        signature = json.dumps(signature_payload, sort_keys=True)
        now = time.monotonic()
        seeked = (start_ms is not None and self.last_start_ms is not None
                  and abs(start_ms - self.last_start_ms) > 2000)
        changed = signature != self.last_signature
        refresh = now - self.last_send >= 45.0
        if not (changed or seeked or refresh):
            return
        if now - self.last_send < 1.5:
            return
        while self.frames and now - self.frames[0] > 21.0:
            self.frames.popleft()
        if len(self.frames) >= 5:
            return
        if self.client is None and not self._connect():
            return
        try:
            self.client.set_activity(activity)
            self.frames.append(now)
            self.last_signature = signature
            self.last_send = now
            self.last_start_ms = start_ms
            self.visible = True
        except Exception:
            log.warning("Discord presence update failed; reconnecting", exc_info=True)
            self.client.close()
            self.client = None
            self.visible = False
            self.last_signature = None

    def _clear(self):
        if self.client:
            try:
                if self.visible:
                    self.client.clear()
            except Exception:
                pass
            self.client.close()
            self.client = None
        self.last_signature = None
        self.last_track_key = None
        self.last_start_ms = None
        self.visible = False
