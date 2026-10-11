# Changelog

## 0.1.0 — 2026-10-11

- Standalone `play-quran` CLI with searchable bilingual selection of all 114 Surahs.
- MP3Quran v3 reciter catalog with edition-specific availability and metadata caching.
- Detached mpv sessions with authenticated private Unix IPC and playback controls.
- Persistent validated XDG settings, previous selection and optional next-Surah queue.
- Shared Codex/Cursor Agent Skill and Cursor Markdown command compatibility adapter.
- User-scoped install/uninstall, offline regression tests and Python package CI.

Initial development ran in a sandbox without shell DNS or Unix socket creation.
Live playback, audible output, global home installation and GitHub publication
require verification in an environment allowing those operations.
