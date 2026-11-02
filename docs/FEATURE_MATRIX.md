# Feature coverage matrix

| Feature | LiChord addon | Why / boundary |
|---|---|---|
| Search YouTube Music | Implemented | `ytmusicapi` adapter |
| Search YouTube | Implemented | `yt-dlp` search |
| Search SoundCloud | Implemented | `yt-dlp` search |
| Aggregate search | Implemented | Concurrent provider hub |
| Deduplication | Implemented | Normalized title + artist |
| Artwork / artist / album / duration | Best-effort | Provider metadata availability |
| Fresh audio stream resolution | Implemented | `yt-dlp` at request time |
| Quality preference | Partial | Selects lowest or best available; no guarantee of source quality |
| Codec / container / bitrate / sample rate | Best-effort | Only when extractor provides fields |
| Search cache | Implemented | Short bounded in-memory cache |
| Lyrics and word timings | Not possible in current addon contract | No lyrics resource in host HTTP addon API |
| Comments and comment actions | Not possible in current addon contract | Requires host auth, models, endpoints and UI |
| Playlists, likes, subscriptions, uploads | Not possible in current addon contract | Requires account-bound write operations |
| Music-video UI | Not possible in current addon contract | Host player owns video UI and playback |
| Tempo / pitch / reverb UI | Not possible in current addon contract | Host owns DSP and player controls |
| Scrobbling / history / statistics | Host responsibility | Playback lifecycle belongs to BitChord |
| Local library access | Host responsibility | Requires local filesystem access and UI |

“Not possible” here means not possible through the currently inspected HTTP addon protocol;
it does not mean these features are technically impossible in a BitChord fork.
