# LiChord

A self-hosted, multi-catalogue HTTP addon for BitChord. LiChord searches YouTube Music, YouTube and SoundCloud, normalizes results and resolves fresh audio URLs for playback.

The repository also includes **LiChord Presence**, an independent desktop companion that reads Linux MPRIS playback metadata and publishes a configurable Discord Listening activity.

## Addon features

- Three independently selectable catalogues or combined search.
- Normalized metadata and cross-catalogue deduplication.
- Fresh stream URL resolution; signed upstream media URLs are resolved on demand and never cached by LiChord.
- LOW, HIGH and LOSSLESS best-available extraction preferences.
- Observed codec, container, bitrate and sample-rate metadata.
- Provider failure isolation, bounded search concurrency and a bounded search cache.
- Optional BitChord request authentication using signed tokens and hardware-backed request proofs.
- Docker/Compose deployment and protocol tests.

## BitChord addon authentication

Authentication is optional. The manifest stays public; all other HTTP routes are protected when enforcement is enabled.

Set the public hostname(s) users enter in BitChord, without scheme, port or path:

```dotenv
BITCHORD_HOSTS=music.example.com,alias.example.net
BITCHORD_AUTH_MODE=log
```

Start in `log` mode. The verifier checks credentials and logs failures but does not block requests. Confirm that the hostname matches the URL entered in BitChord and that official Android clients work. Then switch to:

```dotenv
BITCHORD_AUTH_MODE=enforce
```

Enforcement requires `BITCHORD_HOSTS`; the server refuses to start if it is missing. The manifest advertises `bitchordAuth: true` only when the verifier is configured. Keep `/manifest.json` public. The verifier fetches and caches BitChord's public signing keys; the server needs outbound HTTPS access to `bitchord-auth.kushagrasingh.in`.

**Local HTTP installs:** leave authentication off. BitChord sends proof headers only over HTTPS, so enabling enforcement for `http://127.0.0.1` will prevent local playback. Desktop/web clients and unofficial Android builds cannot satisfy the official-app hardware proof.

The stream endpoint returns freshly extracted upstream media URLs. Those providers control their URL expiry; LiChord does not proxy media or mint its own HMAC media URLs.

## LiChord Presence

LiChord Presence is a separate process. It reads the active MPRIS player over the session D-Bus and communicates with the running Discord desktop client through its local IPC socket.

- Choose a specific MPRIS playback source or let automatic priority choose one.
- Configure the member-list status line and the three text/artwork lines.
- Show/hide artwork, timeline, badge, and paused cards.
- Make metadata lines and artwork clickable when a matching source URL exists.
- Configure two independent buttons.
- Use privacy mode to omit track-specific metadata.
- Configure everything through the local settings page.

Install and run:

```bash
python -m pip install -e ".[presence]"
lichord-presence
```

Open http://127.0.0.1:8790. Create a Discord application, copy its Application ID into the settings page, and keep the Discord desktop client running. The companion caches MPRIS player interfaces rather than introspecting them on every polling cycle, and reconnects when the session bus disappears.

## Addon quick start

Requirements: Python 3.11+, BitChord addon support, and network access to upstream providers.

```bash
git clone https://github.com/GraveEaterMadison/LiChord.git
cd LiChord
python -m venv .venv
source .venv/bin/activate
pip install -e .
lichord
```

Open BitChord → Addons and add http://127.0.0.1:8787.

## Addon endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /manifest.json | Public addon manifest and settings |
| GET | /search?q=... | Catalogue search |
| GET | /stream/{track_id}?quality=HIGH | Fresh audio stream |
| GET | /health | Health check |

## Docker

```bash
cp .env.example .env
docker compose up --build -d
```

The Compose port is bound to localhost by default. Docker runs the HTTP addon only; run LiChord Presence in the logged-in desktop session.

## Development

```bash
pip install -e ".[dev,presence]"
ruff check .
ruff format --check .
pytest
```

Tests use fake providers and do not require live upstream services.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [BitChord protocol](docs/PROTOCOL.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)
- [Source feature audit](docs/FEATURE_AUDIT.md)
- [Deployment](docs/DEPLOYMENT.md)

## Limitations

Upstream changes may temporarily break extraction. Availability depends on region and network. LOSSLESS requests the best available stream; it does not guarantee lossless encoding. Downloads are disabled. LiChord stores no Google credentials or provider cookies. Do not expose the HTTP addon publicly without authentication and rate limiting.

## License

MIT. Independent project, not affiliated with BitChord, Google, YouTube, SoundCloud or Discord.
