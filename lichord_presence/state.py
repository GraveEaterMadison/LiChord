from __future__ import annotations

from threading import RLock
from typing import Any

_lock = RLock()
_snapshot: dict[str, Any] | None = None
_players: list[dict[str, str]] = []


def update_now_playing(value: dict[str, Any] | None) -> None:
    global _snapshot
    with _lock:
        _snapshot = dict(value) if value is not None else None


def get_now_playing() -> dict[str, Any] | None:
    with _lock:
        return dict(_snapshot) if _snapshot is not None else None


def update_players(value: list[dict[str, str]]) -> None:
    global _players
    with _lock:
        _players = [dict(item) for item in value]


def get_players() -> list[dict[str, str]]:
    with _lock:
        return [dict(item) for item in _players]
