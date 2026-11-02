# LiMusic / BitChord source audit (addon scope)

Audit basis: feature-oriented inspection of the public LiMusic and BitChord repositories. This is not a claim that every line of either repository was manually reviewed.

## BitChord addon contract

The addon client consumes a manifest, search results and resolved stream URLs over ordinary HTTP GET requests. The host parser ignores unknown JSON fields; adding an arbitrary field does not create a new screen, playback hook or feature.

## Feature comparison

| Capability | LiMusic | BitChord | Can this HTTP addon provide it? |
|---|---|---|---|
| YouTube Music search/stream | Yes | Yes | Yes, as an alternate source |
| YouTube and SoundCloud search | Provider support | Source resolvers | Yes |
| Unified multi-source search | Yes | Source architecture | Yes |
| Lyrics and word timing | Lyrics models/providers/UI | Native lyrics support | No lyrics endpoint in addon contract |
| Account sessions and library writes | Yes | Native account/session flows | No; requires host authentication and write APIs |
| Playlist mutation, likes, subscriptions | Yes | Native library UI | No; requires host write operations |
| Music-video interface | Yes | Native player | No; host owns video UI/playback |
| Comments and replies | Yes | No matching public addon surface | No; requires new host endpoints and UI |
| Last.fm / ListenBrainz scrobbling | Yes | Native integrations | No; host owns playback lifecycle |
| Discord RPC / OS media controls | Yes | Native integrations | No; host owns OS integration |
| Local files and local library | Yes | Native local source | No; requires local filesystem permissions |
| DSP, equalizer, pitch and effects UI | Yes | Native audio processing | No; host owns audio pipeline and controls |
| Themes and appearance | Yes | Native UI settings | No; host UI only |

## LiChord implementation scope

LiChord implements the capabilities the HTTP addon can actually expose: multi-catalogue search, provider selection, normalized track metadata, deduplication, fresh stream resolution, quality preferences, technical metadata, bounded concurrency, provider failure isolation and health reporting.

## Explicit non-goals

LiChord does not pretend to add lyrics, comments, playlist writes, user cookies, local files or new UI through undocumented JSON fields. Those features require upstream BitChord changes.

## Test strategy

Unit tests should use fake providers and the FastAPI test client. Live provider checks are separate because upstream services can change extraction behaviour or be unavailable in CI.
