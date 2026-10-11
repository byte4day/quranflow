---
name: play-quran
description: Play and control background Qur'an recitation with QuranFlow when the user requests a Surah, reciter, or playback control while coding.
---

# QuranFlow

Use the installed QuranFlow CLI through `scripts/play_quran.py` beside this skill.
It uses the same playback engine as the standalone terminal command, and returns
after starting an independent background player. Run the helper with Python 3
and argument arrays; preserve the user's Surah, reciter, edition, and control
arguments. Never construct a shell command from untrusted text.

Examples (resolve the helper relative to this SKILL.md, not the working repository):

```text
python3 <skill-directory>/scripts/play_quran.py yasin --reciter dosari
python3 <skill-directory>/scripts/play_quran.py --surah 18 --reciter dosari
python3 <skill-directory>/scripts/play_quran.py pause
python3 <skill-directory>/scripts/play_quran.py resume
python3 <skill-directory>/scripts/play_quran.py stop
python3 <skill-directory>/scripts/play_quran.py status
```

An agent shell is usually noninteractive. When the user has not selected a Surah,
run `surahs --json` through the helper and ask them to choose. When the reciter is
missing, inspect `config --json` for `default_reciter`; pass that remembered ID
with `--reciter`. If none is configured, run `reciters --json` and offer the
provider's available reciters. The standalone CLI
opens its keyboard selector only in a real terminal. Do not launch an interactive
selector in an agent shell or claim that it was shown to the user.

For multiple suitable recordings, list
`reciters --reciter NAME --surah NUMBER --json` and ask the user to choose an
edition, unless their remembered `last_edition` is available for this selection.
Pass the chosen `--edition ID`. If the
provider reports that the Surah is unavailable for that reciter, explain this and
offer only the alternatives it returns. Do not silently substitute a reciter or
invent an audio URL. Use `status` after starting playback; report any network,
backend, or audio-device error honestly. Starting a process alone does not prove
that audio is audible.

The global installation records an absolute executable path beside the helper;
it works from unrelated repositories. If QuranFlow is missing, explain that the
user must run `./install.sh` from their QuranFlow checkout. Do not install system
packages or alter agent permissions to play audio.

Codex invokes this skill with `$play-quran`; Cursor supports `/play-quran` through
its shared skill discovery. A native Codex `/play-quran` alias is not provided.
