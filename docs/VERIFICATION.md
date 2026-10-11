# Verification record — 2026-10-11

QuranFlow 0.1.0 was built and reviewed in an isolated repository directory.
The acceptance criteria requiring live streaming, real IPC, actual global agent
activation and public publication are **not completed** under the current environment.

## Passed

- Python 3.14.7: **320 pytest tests passed**. Fixtures/mocks cover all 114 Surah
  IDs/names/verse counts, aliases/fuzzy matching, reciter identity, partial recording
  availability, provider parsing/URLs/network failures/timeouts/caching, persistent
  settings, CLI validation, process lifecycle/controls, and installer/integration ownership.
- Ruff 0.16.10 lint and formatting for `src`, `tests`, `scripts`, `.agents`.
- Python bytecode compilation and shell syntax checks.
- Wheel and source distribution built with Hatchling 1.32.4; package contents
  checked for Surah data, integrations, documentation/license and exclusion of audio,
  personal state, credentials, bytecode and unrelated workspace content.
- Actual isolated wheel installation, repeat installation and clean uninstall.
  A temporary home containing spaces was tested. CLI/skill helper worked from an
  unrelated directory; all 114 Surahs and separate-process configuration persistence
  were checked. Invalid input was rejected without altering settings.
- Codex skill-creator validator: `Skill is valid!`; CI YAML/matrix/permissions parsed.
  The GitHub Actions workflow is configured, but has not run on a remote repository.
- Actual curses selector in a pseudo-terminal: typing `yasin` selected 36 and restored
  terminal state. Plain `TERM=dumb` fallback: `An-Nas` selected 114.
- Real mpv 0.41.0 decoded generated 0.1-second silence through `--ao=null` and its
  embedded Lua recorder saved EOF with a playlist entry ID. The recorder also passed
  with an Arabic filesystem path. This was **not audible Qur'an playback**.
- Independent review found/fixed menu alias matching, reciter/edition memory,
  early volume validation and ignored control flags; regression tests pass.

A usable installation remains under the writable workspace's `quranflow-install`
sibling directory. Its `.local/bin/play-quran` and installed skill helper work by
absolute path. This is an alternate installation home, not the real user's global
PATH or agent skill location.

## Blocked / not verified

- Shell DNS cannot resolve `api.github.com` or the MP3Quran API. Real catalog/stream
  integration could not be verified. Official reciter pages/documentation and the
  full AlQuran Cloud factual chapter index were accessible through documentation tools.
- Unix socket binding returns `EPERM`; mpv cannot create its IPC socket. The actual
  startup-failure path reaped its own child. Real detached streaming survival,
  pause/resume/volume/replay/status and audible output remain unverified.
- Actual default installation failed with a read-only-filesystem error at the
  user's `~/.local/share/quranflow`. The sandbox also protects `~/.agents` and
  `~/.cursor`. Global installation and GUI skill discovery were not claimed.
- GitHub CLI 2.102.0 reports a stored active account `byte4day`, but `gh auth status`
  reports its token invalid. `gh api user` and `gh repo view byte4day/quranflow`
  fail to connect. Restricted DNS prevents independent authentication validation
  or repository-name availability verification. No public repository was created
  or pushed, and there is no verified repository URL.

## Remaining release steps

Run `./install.sh` from a normal local Linux terminal to activate the global CLI,
Codex skill and Cursor adapter. Follow `docs/SMOKE_TEST.md` with a real provider
catalog and audible audio. Reload the agent clients and verify discovery.

After restoring shell network access, run `gh auth status` and `gh api user --jq .login`;
refresh/login only if authentication still fails. Confirm `quranflow` is available
under the authenticated account (a name lookup must return an actual 404, not a network
or authorization error), or select `quranflow-cli` after checking it. Then publish
the dedicated local main branch:

```sh
gh repo create quranflow --public --source=. --remote=origin --push
gh repo view --json url,defaultBranchRef
git ls-remote origin refs/heads/main
```

Use the checked available name in that command. Add the confirmed clone URL to the
README/project links and verify remote files and CI. Do not mistake these pending
commands for publication evidence.
