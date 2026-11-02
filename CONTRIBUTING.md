# Contributing

Thanks for helping improve LiChord.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # fish: source .venv/bin/activate.fish
python -m pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
pytest
```

Keep provider-specific extraction in `lichord/providers.py`, protocol serialization in
`lichord/models.py`, and HTTP validation/caching in `lichord/server.py`.

## Provider adapter rules

- Use stable, namespaced IDs (`ytm:`, `yt:`, `sc:`).
- Never accept arbitrary caller-supplied URLs as stream targets.
- Resolve signed media URLs at playback time; do not cache them.
- Report only observed codec/container/bitrate/sample-rate metadata.
- Do not claim lossless quality unless the upstream source proves it.
- A failed catalogue must not suppress healthy catalogues.
- Add deterministic tests with fake provider responses; do not make CI depend on live services.

## Scope

This project targets the public BitChord HTTP addon contract. Features that need new host UI,
authentication flows, playback lifecycle hooks or new HTTP resources belong in a BitChord
upstream proposal, not in undocumented addon JSON fields.
