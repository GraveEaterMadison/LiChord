# Deployment

## HTTP addon

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
lichord
~~~

Set LICHORD_HOST, LICHORD_PORT and LICHORD_LOG_LEVEL as needed. Connect BitChord to http://127.0.0.1:8787.

## Discord Rich Presence companion (Linux desktop)

Install the optional MPRIS dependency and run the companion inside the logged-in desktop session:

~~~bash
python -m pip install -e ".[presence]"
lichord-presence
~~~

Open http://127.0.0.1:8790. The settings UI listens on localhost only. Create a Discord application in the Developer Portal, enter its numeric Application ID, then leave the Discord desktop client running.

LiChord Presence discovers active org.mpris.MediaPlayer2.* services on the session D-Bus. If BitChord does not publish MPRIS metadata, it cannot be detected; the companion will use another available MPRIS player instead. Album/artist click-through requires those URLs or IDs to be present in MPRIS metadata. Artwork must be a URL Discord can fetch.

Settings are stored in ~/.config/lichord-presence/config.json. Run lichord-presence --web-only to open the settings page without the playback monitor.

### systemd user service (optional)

Create ~/.config/systemd/user/lichord-presence.service:

~~~ini
[Unit]
Description=LiChord Discord Rich Presence companion
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/lichord-presence
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
~~~

Adjust ExecStart to the actual path returned by command -v lichord-presence, then run:

~~~bash
systemctl --user daemon-reload
systemctl --user enable --now lichord-presence.service
~~~

## Docker Compose

~~~bash
cp .env.example .env
docker compose up --build -d
~~~

Docker runs the HTTP addon only. Do not put Discord IPC or session D-Bus integration in the headless container.

## Security

The settings server binds to 127.0.0.1 by default. Do not expose it to the LAN: it has no authentication. The addon service must be reachable by BitChord; permit TCP 8787 only on a trusted private network.

## Troubleshooting

- No Discord activity: verify Discord desktop is running, Application ID is numeric, and the companion runs in the same user session.
- No playback detected: inspect playerctl -l or busctl --user list for MPRIS services.
- No artwork: confirm MPRIS publishes an HTTPS mpris:artUrl.
- Album/artist links missing: the MPRIS player must publish the relevant IDs or URLs.
- Addon extraction errors: update yt-dlp and ytmusicapi, then restart the addon.
