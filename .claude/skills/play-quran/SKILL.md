---
name: play-quran
description: Play, pause, resume, stop or change background Qur'an recitation (QuranFlow). Use when the user asks to play a Surah or reciter, or to control Qur'an playback.
argument-hint: "[surah] [--reciter NAME] | pause | resume | stop | status | volume N"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/play_quran.py *)
effort: low
---

Run exactly one Bash command, then reply with its single output line and nothing else:

`python3 ${CLAUDE_SKILL_DIR}/scripts/play_quran.py --brief <args>`

- `<args>` = the user's request as separate shell-quoted words: a Surah name or number
  (`yasin`, `36`, `al-kahf`), `--reciter NAME`, `--edition ID`, or one control word:
  `pause`, `resume`, `stop`, `status`, `replay`, `volume N`, `change`.
- Nothing chosen ("play Quran")? Pass no args: the CLI reuses the remembered Surah and reciter.
- Do not run `status`, `--help`, `reciters` or `surahs` first. Do not read files or explore.
- On an error, report it in one sentence. List options (`reciters --surah N`) only
  when the user asks for them.

Slash-command arguments, if any: $ARGUMENTS
