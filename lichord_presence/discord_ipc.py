from __future__ import annotations

import json
import os
import socket
import struct
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SONG = "https://music.youtube.com/watch?v="
ARTIST = "https://music.youtube.com/channel/"
ALBUM = "https://music.youtube.com/browse/"
MAX_IPC_FRAME = 1_048_576


def _https_url(value: object, limit: int = 512) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        return value
    except ValueError:
        return None


def _field(value: str | None) -> str | None:
    value = (value or "").strip()
    return value[:128] or None


def text_for(slot: str, track: dict[str, Any]) -> str | None:
    title = str(track.get("title") or "").strip()
    artist = str(track.get("artist") or "").strip()
    album = str(track.get("album") or "").strip()
    if slot == "title":
        return title or None
    if slot == "artist":
        return artist or None
    if slot == "album":
        return album or None
    if slot == "artist_album":
        return (artist + " — " + album).strip(" —") or None
    return None


def link_for(slot: str, track: dict[str, Any]) -> str | None:
    if track.get("local"):
        return None
    if slot == "title":
        candidate = track.get("url") or (
            (SONG + str(track["video_id"])) if track.get("video_id") else None
        )
    elif slot in {"artist", "artist_album"}:
        candidate = track.get("artist_url") or (
            (ARTIST + str(track["artist_id"])) if track.get("artist_id") else None
        )
    elif slot == "album":
        candidate = track.get("album_url") or (
            (ALBUM + str(track["album_id"])) if track.get("album_id") else None
        )
    else:
        return None
    return _https_url(candidate)


def _listen_label(track: dict[str, Any]) -> str:
    url = str(track.get("url") or "")
    if "soundcloud.com/" in url:
        return "Listen on SoundCloud"
    if "youtube.com/" in url or "youtu.be/" in url:
        return "Listen on YouTube"
    return "Listen to track"


def _button(kind: str, track: dict[str, Any], app_name: str, app_url: str) -> dict[str, str] | None:
    choices = {
        "listen": (_listen_label(track), link_for("title", track)),
        "album": ("View album", link_for("album", track)),
        "artist": ("View artist", link_for("artist", track)),
        "app": ("Get " + (app_name or "LiChord"), _https_url(app_url)),
    }
    label_url = choices.get(kind)
    if not label_url or not label_url[1]:
        return None
    return {"label": label_url[0][:32], "url": label_url[1]}


def build_activity(cfg, track: dict[str, Any], playing: bool, position: float,
                   duration: float, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    app_name = cfg.app_name or "LiChord"
    activity: dict[str, Any] = {"type": 2, "name": app_name}
    if cfg.hide_details:
        activity["status_display_type"] = 0
        return activity

    first = text_for(cfg.line1, track) or text_for("title", track) or "Unknown track"
    second = text_for(cfg.line2, track)
    activity["details"] = _field(first)
    if second:
        activity["state"] = _field(second)
    activity["status_display_type"] = {"app": 0, "line2": 1, "line1": 2}.get(
        cfg.status_line, 1
    )

    if cfg.link_line1:
        target = link_for(cfg.line1, track)
        if target:
            activity["details_url"] = target
    if cfg.link_line2 and second:
        target = link_for(cfg.line2, track)
        if target:
            activity["state_url"] = target

    if cfg.timestamps and playing and duration > 0:
        elapsed = max(0.0, min(position, duration))
        start = int(now - elapsed)
        activity["timestamps"] = {"start": start, "end": int(start + duration)}

    assets: dict[str, str] = {}
    artwork = _https_url(track.get("artwork"), 256)
    if cfg.cover and artwork:
        assets["large_image"] = artwork
        hover = text_for(cfg.line3, track)
        if hover:
            assets["large_text"] = _field(hover)
        if cfg.link_cover:
            target = link_for("album", track) or link_for("title", track)
            if target:
                assets["large_url"] = target
        badge_url = _https_url(cfg.badge_url, 256)
        if cfg.badge and badge_url:
            assets["small_image"] = badge_url
            assets["small_text"] = _field(app_name) or "LiChord"
    if assets:
        activity["assets"] = assets

    buttons = []
    for kind in (cfg.button1, cfg.button2):
        button = _button(kind, track, app_name, cfg.app_url)
        if button and len(buttons) < 2:
            buttons.append(button)
    if buttons:
        activity["buttons"] = buttons

    for key in ("details", "state"):
        if key in activity and activity[key] and len(activity[key]) < 2:
            activity[key] += " "
    return activity


def ipc_candidates() -> list[str]:
    paths: list[str] = []
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        paths += [f"{runtime}/discord-ipc-{i}" for i in range(10)]
        paths += [f"{runtime}/app/com.discordapp/discord-ipc-{i}" for i in range(10)]
    paths += [f"/tmp/discord-ipc-{i}" for i in range(10)]
    tmp = os.environ.get("TMPDIR")
    if tmp:
        paths += [f"{tmp}/discord-ipc-{i}" for i in range(10)]
    return list(dict.fromkeys(paths))


class DiscordIPC:
    def __init__(self, application_id: str):
        self.application_id = application_id
        self.sock: socket.socket | None = None

    def _send(self, opcode: int, payload: dict[str, Any]) -> None:
        if not self.sock:
            raise ConnectionError("Discord IPC is not connected")
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.sock.sendall(struct.pack("<II", opcode, len(body)) + body)

    def _read(self) -> tuple[int, dict[str, Any]]:
        if not self.sock:
            raise ConnectionError("Discord IPC is not connected")
        header = self._recv_exact(8)
        opcode, size = struct.unpack("<II", header)
        if size > MAX_IPC_FRAME:
            raise ConnectionError("Discord IPC frame exceeded the size limit")
        body = self._recv_exact(size)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectionError("Discord IPC returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ConnectionError("Discord IPC returned an invalid payload")
        return opcode, payload

    def _recv_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            part = self.sock.recv(size - len(data)) if self.sock else b""
            if not part:
                raise ConnectionError("Discord IPC closed")
            data.extend(part)
        return bytes(data)

    def connect(self) -> None:
        if not self.application_id.isdigit():
            raise ValueError("Set a numeric Discord Application ID in the settings page")
        last_error: Exception | None = None
        for path in ipc_candidates():
            if not Path(path).exists():
                continue
            try:
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.settimeout(3)
                client.connect(path)
                self.sock = client
                self._send(0, {"v": 1, "client_id": self.application_id})
                opcode, response = self._read()
                if opcode != 1 or response.get("evt") == "ERROR":
                    raise ConnectionError("Discord rejected the IPC handshake")
                return
            except (OSError, ValueError, ConnectionError) as exc:
                last_error = exc
                self.close()
        raise ConnectionError(
            f"Discord desktop IPC was not found or rejected the connection: {last_error}"
        )

    def set_activity(self, activity: dict[str, Any]) -> None:
        self._send(1, {"cmd": "SET_ACTIVITY", "args": {
            "pid": os.getpid(), "activity": activity
        }, "nonce": str(time.time_ns())})
        _opcode, response = self._read()
        if response.get("evt") == "ERROR":
            raise RuntimeError(response.get("data", {}).get("message", "Discord rejected activity"))

    def clear(self) -> None:
        if self.sock:
            self._send(1, {"cmd": "SET_ACTIVITY", "args": {
                "pid": os.getpid(), "activity": None
            }, "nonce": str(time.time_ns())})
            self._read()

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
