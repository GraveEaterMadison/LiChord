# LiChord

A self-hosted, multi-catalogue HTTP addon for BitChord. LiChord searches YouTube Music, YouTube and SoundCloud, normalizes results and resolves fresh audio URLs for playback.

The repository also includes **LiChord Presence**, an independent desktop companion that reads Linux MPRIS playback metadata and publishes a fully configurable Discord Listening activity. It runs separately from the HTTP addon.

## Addon features

- Three independently selectable catalogues or combined search.
- Normalized metadata and cross-catalogue deduplication.
- Fresh stream URL resolution; signed URLs are not cached.
- LOW, HIGH and LOSSLESS best-available extraction preferences.
- Observed codec, container, bitrate and sample-rate metadata.
- Provider failure isolation and bounded search cache.
- Docker/Compose deployment and protocol tests.

## LiChord Presence

LiChord Presence is a separate process. It does not modify BitChord or run inside the addon server. On Linux desktops it reads the active MPRIS player over the session D-Bus and communicates with the running Discord desktop client through its local IPC socket.

It reproduces LiMusic's configurable Rich Presence card controls:

- Enable/disable presence and set a custom application-name override.
- Choose the member-list status line: app name, line 1, or line 2.
- Configure line 1 as title, artist, or album.
- Configure line 2 as title, artist, album, artist + album, or off.
- Show/hide artwork; configure line 3 / artwork hover text.
- Independently make line 1, line 2, and artwork clickable when source URLs exist.
- Show/hide the elapsed/duration timeline; paused cards never show a misleading running timeline.
- Show/hide a small artwork badge and configure its HTTPS image URL.
- Keep the card visible while paused.
- Privacy mode that omits all track-specific metadata.
- Two independent buttons: Listen, View album, View artist, Get LiChord, or Off.
- Local settings page with a Discord-style live card preview, persistent settings, and reset defaults.

The companion also reconnects when Discord is unavailable, avoids rapid duplicate updates, refreshes a live card periodically, and clears presence when playback stops. Local-file paths are not published. MPRIS players that do not expose artist/album IDs or webpage URLs cannot provide those links, so unavailable buttons/links are omitted.

### Install and run on Linux

~~~bash
python -m pip install -e ".[presence]"
lichord-presence
~~~

Open http://127.0.0.1:8790 to configure it. Create a Discord application at https://discord.com/developers/applications, copy its Application ID into the settings page, and keep the Discord desktop client running.

The player must expose MPRIS metadata on the same Linux desktop session. BitChord must expose MPRIS for its own playback to be detected; otherwise the companion will follow whichever other MPRIS player is active.

Configuration is saved at ~/.config/lichord-presence/config.json. The settings page binds to localhost only by default. To run only the settings page, use lichord-presence --web-only.

### Important compatibility note

The first companion implementation targets Linux MPRIS + Discord desktop IPC. It does not use Discord OAuth, does not require a bot token, and does not upload credentials. Windows/macOS playback-source adapters and native BitChord integration can be added separately.

## Addon quick start

Requirements: Python 3.11+, BitChord addon support, and network access to upstream providers.

~~~bash
git clone https://github.com/GraveEaterMadison/LiChord.git
cd LiChord
python -m venv .venv
source .venv/bin/activate
# Fish: source .venv/bin/activate.fish
pip install -e .
lichord
~~~

Open BitChord → Addons and add http://127.0.0.1:8787.

## Addon endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /manifest.json | Addon manifest and settings |
| GET | /search?q=... | Catalogue search |
| GET | /stream/{track_id}?quality=HIGH | Fresh audio stream |
| GET | /health | Health check |

## Docker

~~~bash
cp .env.example .env
docker compose up --build -d
~~~

Docker deployment runs the HTTP addon only. Run LiChord Presence in the logged-in desktop session, not inside the headless addon container.

## Development

~~~bash
pip install -e ".[dev,presence]"
ruff check .
ruff format --check .
pytest
~~~

Unit tests use fake providers; live provider checks are separate because upstream services may be unavailable or change extraction behaviour.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [BitChord protocol](docs/PROTOCOL.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)
- [Source feature audit](docs/FEATURE_AUDIT.md)
- [Deployment](docs/DEPLOYMENT.md)

## Limitations

Upstream changes may temporarily break extraction. Availability depends on region and network. LOSSLESS requests the best available stream; it does not guarantee lossless encoding. Downloads are disabled. LiChord stores no Google credentials or provider cookies. Do not expose the HTTP addon publicly without an authenticated reverse proxy and rate limiting.

## License

MIT. Independent project, not affiliated with BitChord, Google, YouTube, SoundCloud or Discord.
