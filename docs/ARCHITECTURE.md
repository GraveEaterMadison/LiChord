# Architecture

```text
BitChord AddonClient
       |
       | GET /manifest.json
       | GET /search?q=...&provider=...&region=...&limit=...
       | GET /stream/{namespaced-track-id}?quality=...
       v
FastAPI (lichord/server.py)
       |
       +-- manifest/settings serialization
       +-- input validation and bounded search cache
       +-- protocol error mapping
       |
       v
ProviderHub (lichord/providers.py)
       |
       +-- YouTubeMusicProvider (ytmusicapi)
       +-- ExtractorSearchProvider (yt-dlp / YouTube)
       +-- ExtractorSearchProvider (yt-dlp / SoundCloud)
       |
       v
Track / Stream (lichord/models.py)
       |
       v
BitChord AddonTrack / stream response
```

## Design decisions

- **HTTP addon, not executable module:** the host's HTTP addon protocol is the intended
  integration surface. LiChord does not execute code inside BitChord.
- **Namespaced IDs:** `ytm:`, `yt:` and `sc:` identify the resolver without exposing a
  caller-controlled URL as a fetch target.
- **No stream URL cache:** media URLs may be signed and expire. Every playback request
  performs a fresh extraction.
- **Short search cache:** identical catalogue queries are cached for a short bounded period.
- **Partial failure tolerance:** aggregate search runs providers concurrently and isolates
  individual provider failures.
- **Honest metadata:** output reflects extractor metadata; requested LOSSLESS is not
  presented as proof of a lossless source.
