# Installation verification

Executed on 2026-10-11 with Python 3.14.7, uv 0.12.22, mpv available, and the built
`quranflow-0.1.0-py3-none-any.whl`. This environment cannot write the real user's
home directories, so integration installation was tested in an isolated temporary
home, including a path containing spaces.

The actual shell entrypoints were run twice, followed by uninstallation:

```sh
./install.sh --home "$TEST_HOME" --offline --wheel dist/quranflow-0.1.0-py3-none-any.whl
./install.sh --home "$TEST_HOME" --offline --wheel dist/quranflow-0.1.0-py3-none-any.whl
./uninstall.sh --home "$TEST_HOME"
```

The installed executable returned `QuranFlow 0.1.0`. The installed shared skill
helper invoked from `/tmp`, outside the checkout, returned all 114 Surahs as
JSON. The installed engine resolved `yasin` to 36, `al-kahf` to 18, and `36` to
36. The CLI rejected Surah 999 and an unknown Surah name before contacting an
audio provider.

With XDG directories isolated inside the test home, setting volume 65 persisted
across separate CLI processes. Volume -1 was rejected and did not change that
setting. `status --json` and `stop --json` returned `stopped` without an active
session. Repeat installation succeeded. Uninstallation removed the executable
and managed environment while retaining `config.json`.

Fourteen installation/integration tests passed with network-independent mocks,
including original-file backup/restore, idempotent installation, preserving
user-edited integrations, refusing symlinked destinations and foreign
environments, cleanup after failed package building, safe uninstallation when
stop times out, and forwarding argument arrays from an unrelated directory.
Ruff checks/formatting passed; `sh -n` passed for both shell scripts; the Codex
skill-creator validator reported `Skill is valid!`.

This verifies executable installation, shared skill packaging and helper
execution, configuration, and safe uninstallation. It does not verify that an
installed Cursor or Codex UI discovers the skill, that the real user's global
directories were modified, or that streamed Qur'an audio is audible. Those
limitations are separate from the isolated installation results above.
