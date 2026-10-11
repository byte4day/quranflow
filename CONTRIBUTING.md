# Contributing to QuranFlow

Changes should preserve accurate reciter attribution, recording availability,
and a small runtime footprint. Open an issue describing a reproducible problem
or proposed improvement before a substantial change. Include your Linux,
Python and mpv versions, relevant command, and a redacted error message.

Use Python 3.11 or newer. Create an isolated environment and install development
tools with `python3 -m venv .venv`, then `.venv/bin/python -m pip install -e '.[dev]'`.
Run `.venv/bin/python -m pytest`, `.venv/bin/ruff check .`,
`.venv/bin/ruff format --check .` and `.venv/bin/python -m pip wheel --no-deps .`.
uv may be used for the same pinned development dependencies.

Keep tests offline and independent of audio hardware. Add regression tests for
failures, especially identity matching, partial catalogs, IPC, settings and
installation ownership. Read official API/mpv documentation before changing
external contracts; update `docs/decisions/` with consequential evidence.
Do not introduce telemetry, a daemon, a web UI or bundled audio.

Verify Surah names against an independent complete index when changing metadata.
Reciter aliases must resolve against actual provider names, not guessed IDs or
hardcoded stream URLs. Ambiguous requests must ask for an explicit selection.

For a manual smoke test outside CI, run the sequence in
`docs/SMOKE_TEST.md`. State explicitly whether you heard audio, tested only
headless controls, or could not test playback. Never label mocks as real playback.
Do not commit user settings, credentials, downloaded recordings or terminal logs
with private paths. Contributions are licensed under the repository's MIT license;
this does not grant rights to third-party recordings.
