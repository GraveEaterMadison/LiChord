# BitChord addon protocol notes

LiChord implements the HTTP resources used by BitChord's addon client.

## Manifest

`GET /manifest.json` returns the addon identity, supported resources, settings and policy
flags. Settings are declared with defaults because the host sends these values as query
parameters.

## Search

`GET /search?q=...&provider=...&region=...&limit=...`

Response shape:

```json
{
  "tracks": [
    {
      "id": "ytm:VIDEO_ID",
      "title": "Example track",
      "artist": "Example artist",
      "album": "Example album",
      "duration": 213,
      "artworkURL": "https://example.invalid/cover.jpg",
      "format": "",
      "audioQuality": "HIGH"
    }
  ]
}
```

Optional metadata is omitted when unavailable.

## Stream

`GET /stream/{track_id}?quality=HIGH`

The response contains a fresh media URL and any available technical metadata such as codec,
container, bitrate and sample rate. `LOW`, `HIGH` and `LOSSLESS` are request preferences;
they do not guarantee an upstream encoding. LiChord reports the actual extracted format.

## Host capability boundary

The current host addon parser consumes track and stream metadata. Unknown JSON properties
do not create screens, player effects, comment actions, account sessions or OS integrations.
Such functionality requires first-class host support.
