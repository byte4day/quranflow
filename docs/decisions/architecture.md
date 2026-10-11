# Scope, runtime and build decisions

Checked 2026-10-11. Runtime is Python 3.11+, standard library only. The development
host has Python 3.14.7, mpv 0.41.0, FFmpeg 9.0, uv 0.12.22 and Ruff 0.16.10.
Cached official Python distributions supplied pytest 9.1.1 and Hatchling 1.32.4;
these development/build versions are pinned in `pyproject.toml`.

Relevant contracts were checked before implementation:

- [Python 3.14 subprocess](https://docs.python.org/3.14/library/subprocess.html):
  argument arrays, detached sessions, child umask and bounded waits.
- [Python curses](https://docs.python.org/3.14/library/curses.html):
  wrapper restores terminal state; optional line-input fallback.
- [Python packaging specification](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
  and [Hatch build configuration](https://hatch.pypa.io/latest/config/build/):
  console entry point, factual bundled metadata, explicit sdist paths.
- [pytest 9.0 versioned monkeypatch documentation](https://github.com/pytest-dev/pytest/blob/9.0.0/doc/en/how-to/monkeypatch.md)
  via Context7 plus [official current pytest docs](https://docs.pytest.org/en/stable/):
  offline fixtures and monkeypatch; installed 9.1.1 was locally exercised.
- [Ruff configuration](https://docs.astral.sh/ruff/configuration/): Python 3.11
  compatibility, lint and formatting. Checks cover owned Python paths.
- [XDG base directory specification](https://specifications.freedesktop.org/basedir/latest/):
  absolute paths, private runtime and persistent settings/cache separation.
- [FFmpeg HTTP protocols](https://ffmpeg.org/ffmpeg-protocols.html): bounded
  reconnect attempts and total delay; [ffplay](https://ffmpeg.org/ffplay.html)
  does not offer mpv's JSON IPC for detached control.
- [checkout v5.0.0](https://github.com/actions/checkout/releases/tag/v5.0.0) and
  [setup-python v6.0.0](https://github.com/actions/setup-python/releases/tag/v6.0.0):
  verified release commit SHAs are pinned; CI has only contents-read permission.
- [GitHub CLI repo creation](https://cli.github.com/manual/gh_repo_create): public
  creation requires authenticated API access and an isolated source repository.

The environment's suggested `~/developer-environment/DOCUMENTATION.md` was absent;
official provider pages, OpenAI Docs MCP, Context7 and installed help supplied the
relevant evidence instead. Build artifacts and offline testing can run using cached
packages; external API/audio and GitHub operations require allowed network access.
