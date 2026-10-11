# Manual playback smoke test

Run this in a local Linux terminal with network, sound and Unix IPC permissions.
The test streams provider audio without saving recordings.

1. Install with `./install.sh`, then run `play-quran --version` and `mpv --version`.
2. Run `play-quran reciters --reciter dosari --surah 36 --json`.
   Confirm the provider identity, edition ID and actual availability.
3. Run `play-quran --surah 36 --reciter dosari --edition ID` with an available ID.
   Listen for recitation and verify `play-quran status` shows the selected attribution.
4. Run `pause`; confirm audio pauses. Run `resume`; confirm audio resumes.
   Set `volume 30`, then `volume 65`, and `replay`; check the audible effects.
5. In another terminal, verify `status`. Close only the original invoking terminal;
   verify playback continues and controls still work in the second terminal.
6. Use `change 18` and `change --reciter alafasy`. If multiple editions are offered,
   choose an available edition explicitly. Check attribution changes correctly.
7. Use a short chapter with `--autoplay`, for example 112. Confirm status advances
   to 113/114 only when this edition has those chapters, then reports completion.
8. Run `stop` twice. Confirm no QuranFlow audio remains and unrelated mpv sessions
   are still running. Start `--last` and stop it again.
9. Verify menu search by English, Arabic and number, keyboard selection and cancel.
   Test the input fallback with `TERM=dumb play-quran` and status with `NO_COLOR=1`.
10. Reload Cursor and Codex. From unrelated repositories invoke `/play-quran` and
    `$play-quran`, including explicit selections and controls. Confirm shared helper
    resolution works and missing input is requested in conversation.

Record operating system, Python/mpv versions, actual audible results, and any
failures. A null audio sink or mocked subprocess is not audible verification.
Avoid posting personal paths/logs without redaction. Stop playback before uninstall.
