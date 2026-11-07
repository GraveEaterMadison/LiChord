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
from .state import update_now_playing, update_players

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
    artwork = art if art.startswith("https://") else None
    return {"title": title, "artist": artist, "album": album, "artwork": artwork,
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

        bus = None
        retry_delay = 1.0
        player_cache = {}
        names_checked_at = 0.0
        services = []
        try:
            while True:
                self.config = PresenceConfig.load()
                if self.client and self.client.application_id != self.config.application_id:
                    self._clear()
                try:
                    if bus is None:
                        bus = await MessageBus().connect()
                        retry_delay = 1.0
                        player_cache.clear()
                        names_checked_at = 0.0
                        log.info("Connected to the session D-Bus; watching MPRIS players")

                    if time.monotonic() - names_checked_at >= 5.0:
                        names_reply = await bus.call(Message(
                            destination="org.freedesktop.DBus",
                            path="/org/freedesktop/DBus",
                            interface="org.freedesktop.DBus",
                            member="ListNames",
                        ))
                        services = sorted(
                            name for name in (
                                names_reply.body[0]
                                if names_reply.message_type == MessageType.METHOD_RETURN else []
                            )
                            if name.startswith("org.mpris.MediaPlayer2.")
                        )
                        for service in list(player_cache):
                            if service not in services:
                                player_cache.pop(service, None)
                        update_players([{"service": name, "name": name.removeprefix("org.mpris.MediaPlayer2.").replace("-", " ").replace(".", " · ")} for name in services])
                        names_checked_at = time.monotonic()

                    selected = self.config.player_service
                    active_services = [selected] if selected else services
                    snapshots = []
                    for service in active_services:
                        try:
                            props = player_cache.get(service)
                            if props is None:
                                intro = await bus.introspect(service, "/org/mpris/MediaPlayer2")
                                obj = bus.get_proxy_object(service, "/org/mpris/MediaPlayer2", intro)
                                props = obj.get_interface("org.freedesktop.DBus.Properties")
                                player_cache[service] = props
                            data = await props.call_get_all("org.mpris.MediaPlayer2.Player")
                            values = {key: variant.value for key, variant in data.items()}
                            status = values.get("PlaybackStatus", "Stopped")
                            snapshots.append((status == "Playing", status, service,
                                              values.get("Metadata", {}), values.get("Position", 0)))
                        except Exception:
                            player_cache.pop(service, None)
                            log.debug("MPRIS player %s unavailable", service, exc_info=True)

                    def priority(snapshot):
                        service = snapshot[2].lower()
                        if "bitchord" in service:
                            return (0, service)
                        if "youtube" in service:
                            return (1, service)
                        return (2, service)

                    playing = sorted((item for item in snapshots if item[0]), key=priority)
                    paused = sorted((item for item in snapshots if item[1] == "Paused"), key=priority)
                    current = (playing or paused or [None])[0]
                    if current:
                        is_playing, _status, _service, metadata, pos_us = current
                        track = _track(metadata)
                        if track:
                            duration_us = metadata.get("mpris:length", 0)
                            duration_us = getattr(duration_us, "value", duration_us) or 0
                            position = max(0.0, float(pos_us or 0) / 1_000_000)
                            duration = max(0.0, float(duration_us) / 1_000_000)
                            update_now_playing({"track": track, "playing": is_playing,
                                                "position": position, "duration": duration})
                            await self._publish(track, is_playing, position, duration)
                        else:
                            update_now_playing(None)
                            self._clear()
                    else:
                        update_now_playing(None)
                        self._clear()
                    await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.warning("MPRIS session unavailable; reconnecting", exc_info=True)
                    if bus is not None:
                        try:
                            bus.disconnect()
                        except Exception:
                            pass
                        bus = None
                    player_cache.clear()
                    update_players([])
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(15.0, retry_delay * 2)
        finally:
            update_now_playing(None)
            update_players([])
            self._clear()
            if bus is not None:
                try:
                    bus.disconnect()
                except Exception:
                    pass

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
            log.debug("Discord is not available; retrying in %.0fs", self.connect_backoff, exc_info=True)
            return False

    async def _publish(self, track, playing, position, duration):
        cfg = self.config
        if not cfg.enabled or (not playing and not cfg.show_paused):
            self._clear()
            return
        if not cfg.application_id:
            return

        key = "|".join(str(track.get(key) or "") for key in ("title", "artist", "album", "url"))
        if key != self.last_track_key:
            self.last_track_key = key
            self.last_signature = None
            self.last_start_ms = None

        now_wall = time.time()
        start_ms = int((now_wall - max(0.0, position)) * 1000) if playing and cfg.timestamps and duration > 0 else None
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
        if not (changed or seeked or refresh) or now - self.last_send < 1.5:
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
