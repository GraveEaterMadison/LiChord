from __future__ import annotations

from threading import RLock
from typing import Any

_lock = RLock()
_snapshot: dict[str, Any] | None = None

def update_now_playing(value: dict[str, Any] | None) -> None:
    global _snapshot
    with _lock:
        _snapshot = dict(value) if value is not None else None

def get_now_playing() -> dict[str, Any] | None:
    with _lock:
        return dict(_snapshot) if _snapshot is not None else None
