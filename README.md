# LiChord

A self-hosted, multi-catalogue HTTP addon for BitChord. LiChord searches YouTube Music, YouTube and SoundCloud, normalizes results and resolves fresh audio URLs for playback.

> LiChord is an HTTP addon, not a BitChord fork. The addon protocol supports search and stream resolution; native lyrics panels, comments, account screens, music-video controls, DSP controls, scrobbling and OS integrations remain host-app features.

## Features

- Three independently selectable catalogues or combined search.
- Normalized metadata and cross-catalogue deduplication.
- Fresh stream URL resolution; signed URLs are not cached.
- LOW, HIGH and LOSSLESS best-available extraction preferences.
- Observed codec, container, bitrate and sample-rate metadata.
- Provider failure isolation and bounded search cache.
- Docker/Compose deployment, tests, CI and developer documentation.

## Quick start

Requirements: Python 3.11+, BitChord addon support, and network access to upstream providers.

```bash
git clone https://github.com/GraveEaterMadison/LiChord.git
cd LiChord
python -m venv .venv
source .venv/bin/activate
# Fish: source .venv/bin/activate.fish
pip install -e .
lichord
```

Open BitChord → Addons and add `http://127.0.0.1:8787`. If the service runs on another device, use its LAN IP and allow TCP 8787 only from trusted devices.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/manifest.json` | Addon manifest and settings |
| GET | `/search?q=...` | Catalogue search |
| GET | `/stream/{track_id}?quality=HIGH` | Fresh audio stream |
| GET | `/health` | Health check |

## Docker

```bash
cp .env.example .env
docker compose up --build -d
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

Unit tests use fake providers; live provider checks are separate because upstream services may be unavailable or change extraction behaviour.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [BitChord protocol](docs/PROTOCOL.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)
- [Source feature audit](docs/FEATURE_AUDIT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

## Limitations

Upstream changes may temporarily break extraction. Availability depends on region and network. LOSSLESS requests the best available stream; it does not guarantee lossless encoding. Downloads are disabled. LiChord stores no Google credentials or provider cookies. Do not expose the service directly to the public internet.

## License

MIT. Independent project, not affiliated with BitChord, Google, YouTube or SoundCloud.
