from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "lichord-presence"
CONFIG_PATH = CONFIG_DIR / "config.json"

@dataclass
class PresenceConfig:
    enabled: bool = True
    application_id: str = ""
    app_name: str = ""
    status_line: str = "line2"
    line1: str = "title"
    line2: str = "artist"
    cover: bool = True
    line3: str = "album"
    link_line1: bool = False
    link_line2: bool = False
    link_cover: bool = False
    timestamps: bool = True
    badge: bool = True
    badge_url: str = ""
    show_paused: bool = False
    hide_details: bool = False
    button1: str = "listen"
    button2: str = "app"
    app_url: str = "https://github.com/GraveEaterMadison/LiChord"

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "PresenceConfig":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            allowed = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in raw.items() if k in allowed})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        temp.replace(path)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "PresenceConfig":
        allowed = {f.name for f in fields(cls)}
        current = asdict(cls())
        for key, value in data.items():
            if key in allowed and isinstance(value, type(current[key])):
                current[key] = value
        cfg = cls(**current)
        cfg.status_line = cfg.status_line if cfg.status_line in {"app", "line1", "line2"} else "line2"
        cfg.line1 = cfg.line1 if cfg.line1 in {"title", "artist", "album"} else "title"
        cfg.line2 = cfg.line2 if cfg.line2 in {"title", "artist", "album", "artist_album", "off"} else "artist"
        cfg.line3 = cfg.line3 if cfg.line3 in {"album", "title", "artist", "off"} else "album"
        for name in ("button1", "button2"):
            if getattr(cfg, name) not in {"listen", "album", "artist", "app", "off"}:
                setattr(cfg, name, "off")
        cfg.application_id = cfg.application_id.strip()
        cfg.app_name = cfg.app_name.strip()[:128]
        cfg.badge_url = cfg.badge_url.strip()[:256]
        cfg.app_url = cfg.app_url.strip()[:512]
        return cfg
