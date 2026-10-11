# Playback and process ownership

QuranFlow uses mpv's newline-delimited JSON IPC protocol. One detached mpv process
owns the entire selected playlist. Python exits after queuing the validated HTTPS
URLs; mpv streams and advances without a running coding agent or Python service.
The player disables the user's mpv configuration and automatically loaded scripts
so unrelated settings cannot alter session controls. It leaves the user's normal
audio output available to mpv.

The runtime directory belongs to the current user and has mode `0700`. The lock,
session JSON, generated Lua event recorder, diagnostics and IPC socket have mode
`0600`; the child inherits umask `077`. A file lock serializes control operations.
The process start time plus Linux boot ID prevents PID reuse. Before sending any
IPC command, the client verifies the socket owner and Linux `SO_PEERCRED` PID and
UID against the recorded session. Stop sends mpv's `quit` command; it never signals
a persisted PID or terminates unrelated audio players. Startup failure terminates
and reaps only the child created by that invocation.

Each IPC request has a random integer `request_id`. Events and unrelated responses
are filtered, socket reads have a three-second deadline, and the total response is
bounded to one MiB. Playlist metadata is associated with mpv's unique entry IDs,
so status follows autoplay rather than continuing to report the first Surah.
mpv's small embedded Lua recorder atomically retains the most recent start/load/end
event. After mpv exits, status distinguishes normal EOF from an error and keeps the
correct track attribution. `--idle=once` lets mpv wait for initial IPC setup and
exit when its playlist finishes. Replay restarts the current entry while active
or starts the last entry again after completion or stop.

Streaming uses TLS peer verification, a 15-second network timeout, a bounded
16 MiB forward and 4 MiB backward cache, and HTTP reconnect options with a
three-second maximum backoff, three retries, and ten seconds of total retry delay.
The provider cannot extend this budget through a Retry-After header.
Retries apply to interrupted streams and connection
errors; normal EOF is never retried. Recent FFmpeg versions support these options;
older builds may ignore unsupported stream options. Audio files are never saved.
Only HTTPS URLs on `mp3quran.net` and its subdomains, without credentials or custom
ports, are accepted. The provider additionally validates recording metadata.

ffplay was considered but is not implemented: its CLI does not offer an equivalent
stable authenticated IPC contract for all required controls. mpv is required.

## Sources and local evidence

- [mpv JSON IPC](https://mpv.io/manual/stable/#json-ipc): request IDs, asynchronous
  events, commands, playlist IDs, `--idle=once`, Lua event hooks, network timeout,
  TLS verification and `--stream-lavf-o`.
- [FFmpeg HTTP options](https://ffmpeg.org/ffmpeg-protocols.html#http): reconnect,
  reconnecting streamed content, network errors and maximum reconnect delay.
- [Lua string literals](https://www.lua.org/manual/5.2/manual.html#3.1): decimal
  byte escapes preserve Unicode and other Linux filename bytes in recorder paths.
- Installed backend examined: mpv **0.41.0**, libavformat **63.1.102**;
  `mpv --list-options` and `ffmpeg -h protocol=https` confirmed the selected options.

On 2026-10-11, mocked playback tests passed locally. A real mpv invocation decoded
a generated 0.1-second silent WAV with `--ao=null`, exited with code zero and
produced an `end-file` event with `reason=eof` and the correct playlist entry ID.
This verified Lua recorder compatibility and decoding, not audible playback.

An actual detached-engine IPC smoke test was attempted. The managed execution
sandbox denies Unix socket binding: Python received `PermissionError: [Errno 1]
Operation not permitted`, and mpv reported `Could not bind IPC socket`.
QuranFlow timed out and terminated its own spawned child. Real pause/resume/status,
background survival, network streaming and audible output could not be verified
inside this sandbox. Run those checks on an ordinary Linux session with audio and
network access; automated tests use fixtures and mocks without these facilities.
