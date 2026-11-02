# Deployment

## Local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
lichord
```

Set `LICHORD_HOST`, `LICHORD_PORT` and `LICHORD_LOG_LEVEL` as needed.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f lichord
```

## BitChord connection

- Same device: `http://127.0.0.1:8787`
- Another device on the same LAN: `http://SERVER_LAN_IP:8787`

The server must be reachable from the device running BitChord. Permit TCP 8787 only on a
trusted private network. Do not expose it publicly without an authenticated reverse proxy
and rate limiting.

## Troubleshooting

- `502` on search: one or more upstream providers may be unavailable; inspect server logs.
- Empty results: test each provider separately in BitChord settings or query the endpoint.
- Stream fails after a long delay: signed URLs are short-lived; start playback again so the
  addon resolves a fresh URL.
- Provider extraction breaks: update `yt-dlp` and `ytmusicapi`, then restart the service.
