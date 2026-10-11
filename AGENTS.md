# QuranFlow engineering notes

Python 3.11+, zero runtime Python dependencies, Linux mpv JSON IPC. Keep original
code MIT and third-party audio attribution separate. Do not bundle audio or guess
provider reciter IDs, servers or availability. See `docs/decisions/` for contracts.

Modules live in `src/quranflow/`; factual Surah data in `src/quranflow/data/`.
`cli.py` connects selectors, provider, config and playback. Agent integrations in
`.agents/skills/play-quran/` and `.cursor/commands/` only invoke the same CLI.
`scripts/install.py` owns user-scoped venv/integrations and tracks conflict backups;
uninstall keeps settings and user-edited files. No changes to system packages,
shell profiles or unrelated repositories.

Checks: `python -m pytest -q`, `ruff check src tests scripts .agents`,
`ruff format --check src tests scripts .agents`, `python -m hatchling build`,
`python scripts/check_artifacts.py`, `sh -n install.sh uninstall.sh`.
Development dependencies are pinned in `pyproject.toml`. CI checks Python 3.11–3.14.
Use offline fixtures/mocks; a real manual smoke procedure is in `docs/SMOKE_TEST.md`.

Configuration uses XDG_CONFIG_HOME, XDG_CACHE_HOME, XDG_STATE_HOME, XDG_RUNTIME_DIR;
there are no secret/API-key environment variables. Private session controls must
validate process identity and socket peer before commands; never kill unrelated mpv.
Read official version-relevant docs before external API or backend changes. Report
audio, network, global installation and GUI verification limitations honestly.
