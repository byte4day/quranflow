---
name: play-quran
description: Play, pause, resume, stop or change background Qur'an recitation (QuranFlow). Use when the user asks to play a Surah or reciter, or to control Qur'an playback.
---

# QuranFlow

Run exactly one command with the helper beside this file (resolve the path relative to
this SKILL.md, not the working repository), then reply with its single output line:

```text
python3 <skill-directory>/scripts/play_quran.py --brief <args>
```

- `<args>`: the user's choices as separate arguments, never one shell string built from
  their text. Examples: `yasin --reciter dosari`, `--surah 18`, `pause`, `resume`,
  `stop`, `status`, `replay`, `volume 40`, `change --reciter alafasy`.
- No Surah or reciter given: pass only what was given. `--brief` reuses the remembered
  Surah, reciter and edition and never opens a menu; it waits a few seconds for audio, so
  no follow-up `status` call is needed.
- Do not run `status`, `--help`, `config`, `reciters` or `surahs` first.
- Report an error line honestly in one sentence. Do not substitute another reciter; offer
  `reciters --surah N` output only when the user asks for options.
- Missing install: tell the user to run `./install.sh` in their QuranFlow checkout. Never
  install system packages.

Codex: `$play-quran`. Cursor: `/play-quran`. Claude Code: `/play-quran`.
