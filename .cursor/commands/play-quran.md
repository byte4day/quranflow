# Play Qur'an with QuranFlow

Play or control background Qur'an recitation using the installed `play-quran`
CLI. Forward the arguments following `/play-quran` as separate arguments, for
example `yasin`, `al-kahf`, `36`, or `--surah 18 --reciter dosari`.

Use the shared `play-quran` skill in `~/.agents/skills/play-quran/SKILL.md` and its
`scripts/play_quran.py` helper. The helper finds the executable by absolute
installed path and works from any repository. If the skill is absent, locate
`play-quran` on PATH or `~/.local/bin/play-quran` and report a missing installation.

For unspecified selections in a noninteractive agent shell, list `surahs --json`
or `reciters --json` and ask the user to choose; honor the remembered reciter in
`config` where available. Forward playback controls such as pause, resume, stop,
replay, volume, and status. Never invent recordings or substitute a reciter.
After starting playback, inspect status and report backend or network failures.
Do not claim audible playback merely because the player started.

Current Cursor versions discover this same skill globally and invoke it with
`/play-quran`. This Markdown command remains a compatibility adapter for versions
supporting `.cursor/commands/` and `~/.cursor/commands/`.
