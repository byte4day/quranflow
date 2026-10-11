# Agent integrations and installation

Documentation checked on 2026-10-11. Local tooling: Python 3.14.7 and uv 0.12.22.
The package supports Python 3.11+ and has no runtime Python dependencies.

- [OpenAI build-skills documentation](https://learn.chatgpt.com/docs/build-skills)
  describes YAML `name`/`description`, `SKILL.md`, supporting scripts, shared
  `.agents/skills` discovery, and explicit `$skill-name` invocation. QuranFlow's
  primary Codex integration is `~/.agents/skills/play-quran/SKILL.md`. No native
  Codex `/play-quran` alias or legacy prompts adapter is claimed.
- [Cursor skills documentation](https://cursor.com/help/customization/skills)
  documents shared `~/.agents/skills` discovery and `/skill-name` invocation.
  The former command documentation now directs users toward skills. QuranFlow
  installs the shared skill for current Cursor and also supplies the requested
  `.cursor/commands/play-quran.md` and user-level `~/.cursor/commands` adapter for
  command-compatible releases. Older releases may require updating Cursor;
  existence of a Markdown file does not prove command discovery in an IDE.
- [Python 3.14 venv](https://docs.python.org/3.14/library/venv.html),
  [pip install](https://pip.pypa.io/en/stable/cli/pip_install/), and
  [uv's CLI reference](https://docs.astral.sh/uv/reference/cli/)
  support an isolated user environment and installing a local source or wheel.
  Existing uv is preferred, avoiding an ensurepip requirement on Arch's Python;
  otherwise the installer uses stdlib venv plus pip. Neither path installs
  system packages or modifies shell profiles.

`./install.sh` installs the CLI in `~/.local/bin`, its private environment under
`~/.local/share/quranflow/venv`, and global agent integrations. The helper records
the absolute executable path in `scripts/installation.json`, generated only at
installation time. Invocation does not depend on the current repository or PATH.
Python 3 and mpv must be installed; missing mpv produces distro-specific package
instructions without executing sudo. Ensure `~/.local/bin` is on PATH.

`--home PATH` makes installation tests independent of real user configuration.
`--offline` prevents package-index access; uv needs cached build requirements,
and pip source builds need locally available build dependencies. A prebuilt
wheel supplied with `--wheel PATH --offline` avoids source-build dependencies.
The installer does not copy anything into unrelated repositories. Current
Cursor user skills are local-machine features and do not automatically install
audio software on Cloud Agents or remote workers.

Conflicting regular files are backed up before replacement. An ownership
manifest records installed-file hashes and backups; repeat installation does
not duplicate unchanged backups. Symlinked destinations and unrelated Python
environments are refused. Uninstall first requests a bounded stop through
QuranFlow's own IPC interface, removes unchanged owned files, restores original
backups, and retains user edits, configuration, cache, and unused backups. An
edited integration leaves the managed environment available until reviewed;
stop errors abort uninstallation so an active player is not orphaned.
