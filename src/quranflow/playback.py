"""Detached mpv sessions with private, authenticated JSON IPC on Linux."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import shutil
import socket
import stat
import struct
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import QuranFlowError

_TIMEOUT = 3.0
_MAX_MESSAGE = 1_048_576

# mpv owns this lightweight recorder: there is no background Python daemon.
_RECORDER = """local utils = require 'mp.utils'
local destination = %s
local last = {}
local function save(event)
    if event.event == 'start-file' then last = {} end
    for k,v in pairs(event) do last[k] = v end
    local f = io.open(destination .. '.tmp', 'w')
    if f then
        f:write(utils.format_json(last)); f:close()
        os.rename(destination .. '.tmp', destination)
    end
end
mp.register_event('start-file', save)
mp.register_event('file-loaded', save)
mp.register_event('end-file', save)
"""


def _private_write(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + "." + secrets.token_hex(4))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _lua_path(path: Path) -> str:
    # Lua decimal byte escapes preserve all Linux filename bytes, including
    # non-ASCII and control bytes, without JSON's incompatible Unicode escapes.
    return '"' + "".join(f"\\{byte:03d}" for byte in os.fsencode(path)) + '"'


def _process_token(pid: int) -> str | None:
    """Linux boot identity plus process start ticks protects against PID reuse."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return f"{boot}:{fields[19]}"
    except (OSError, IndexError):
        return None


class Player:
    """A single user's QuranFlow session; all public operations serialize."""

    def __init__(self, runtime_dir: Path):
        self.runtime_dir = Path(runtime_dir)
        if self.runtime_dir.is_symlink():
            raise QuranFlowError("Playback runtime directory must not be a symlink.")
        self.runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.runtime_dir.stat()
        if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode):
            raise QuranFlowError("Playback runtime directory must belong to the current user.")
        self.runtime_dir.chmod(0o700)
        self.state_file = self.runtime_dir / "session.json"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        fd = os.open(
            self.runtime_dir / "session.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _state(self) -> dict[str, Any]:
        try:
            fd = os.open(self.state_file, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise QuranFlowError(f"Cannot read playback state: {exc}") from exc
        try:
            with os.fdopen(fd, encoding="utf-8") as stream:
                value = json.load(stream)
            if not isinstance(value, dict):
                raise ValueError("expected object")
            if value and (
                not isinstance(value.get("pid"), int)
                or not isinstance(value.get("tracks"), list)
                or not isinstance(value.get("session"), str)
                or not all(c in "0123456789abcdef" for c in value["session"])
                or len(value["session"]) != 12
            ):
                raise ValueError("invalid session fields")
            return value
        except (ValueError, TypeError) as exc:
            raise QuranFlowError(
                "Playback state is malformed; remove the private session.json "
                "file after checking no QuranFlow session is active."
            ) from exc

    def _save(self, state: dict[str, Any]) -> None:
        _private_write(self.state_file, json.dumps(state, ensure_ascii=False))

    def _path(self, state: dict[str, Any], suffix: str) -> Path:
        return self.runtime_dir / (state["session"] + suffix)

    def _alive(self, state: dict[str, Any]) -> bool:
        token = _process_token(state.get("pid", -1))
        return token is not None and token == state.get("process_token")

    def _ipc(self, state: dict[str, Any], command: list[Any]) -> Any:
        if not self._alive(state):
            raise QuranFlowError("No active QuranFlow playback session.")
        path = self._path(state, ".sock")
        try:
            info = path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise QuranFlowError("Playback IPC socket is not owned by the current user.")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(_TIMEOUT)
                client.connect(str(path))
                peer_pid, peer_uid, _ = struct.unpack(
                    "3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                )
                if peer_pid != state["pid"] or peer_uid != os.getuid():
                    raise QuranFlowError(
                        "Playback IPC process identity does not match the session."
                    )
                request_id = secrets.randbits(52)
                client.sendall(
                    json.dumps({"command": command, "request_id": request_id}).encode() + b"\n"
                )
                deadline = time.monotonic() + _TIMEOUT
                buffer = b""
                total = 0
                while time.monotonic() < deadline:
                    client.settimeout(max(0.001, deadline - time.monotonic()))
                    chunk = client.recv(65536)
                    if not chunk:
                        # quit is allowed to close IPC without delivering its reply.
                        if command == ["quit"]:
                            return None
                        raise QuranFlowError("The playback process closed its IPC connection.")
                    buffer += chunk
                    total += len(chunk)
                    if total > _MAX_MESSAGE:
                        raise QuranFlowError("Playback IPC response exceeded its size limit.")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        message = json.loads(line)
                        if message.get("request_id") != request_id:
                            continue
                        if message.get("error") != "success":
                            raise QuranFlowError(f"mpv: {message.get('error', 'unknown error')}")
                        return message.get("data")
                raise QuranFlowError("Playback IPC response timed out.")
        except (OSError, ValueError, AttributeError) as exc:
            raise QuranFlowError(f"Cannot communicate with mpv: {exc}") from exc

    def _event(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            value = json.loads(self._path(state, ".event").read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _property(self, state: dict[str, Any], name: str, default: Any = None) -> Any:
        try:
            return self._ipc(state, ["get_property", name])
        except QuranFlowError as exc:
            if "property unavailable" in str(exc):
                return default
            raise

    def _status(self, state: dict[str, Any]) -> dict[str, Any]:
        if not state:
            return {"status": "stopped", "track": None}
        event = self._event(state)
        tracks = state["tracks"]
        entry_id = event.get("playlist_entry_id")
        track = next(
            (item for item in tracks if item.get("playlist_id") == entry_id),
            tracks[0] if tracks else None,
        )
        result: dict[str, Any] = {
            "status": "stopped",
            "track": track,
            "volume": state.get("volume", 65),
            "pid": state["pid"],
        }
        if state.get("stopped"):
            return result
        if not self._alive(state):
            result["status"] = "completed" if event.get("reason") == "eof" else "error"
            if result["status"] == "error":
                result["error"] = event.get(
                    "file_error",
                    event.get(
                        "error", "Playback ended unexpectedly. Check your audio device and network."
                    ),
                )
            return result
        playlist = self._property(state, "playlist", [])
        current = next((item for item in playlist if item.get("playing")), None)
        if current:
            result["track"] = next(
                (item for item in tracks if item.get("playlist_id") == current["id"]), None
            )
        idle = self._property(state, "idle-active", False)
        result["status"] = (
            "loading" if idle else "paused" if self._property(state, "pause", False) else "playing"
        )
        result["volume"] = self._property(state, "volume", result["volume"])
        result["time_pos"] = self._property(state, "time-pos")
        result["duration"] = self._property(state, "duration")
        if result["time_pos"] is None and result["status"] == "playing":
            result["status"] = "loading"
        return result

    def status(self) -> dict[str, Any]:
        with self._lock():
            return self._status(self._state())

    def _stop(self, state: dict[str, Any]) -> dict[str, Any]:
        if state and self._alive(state):
            self._ipc(state, ["quit"])
            deadline = time.monotonic() + _TIMEOUT
            while self._alive(state) and time.monotonic() < deadline:
                time.sleep(0.025)
            if self._alive(state):
                raise QuranFlowError("mpv did not exit after its quit command; try stop again.")
        if state:
            state["stopped"] = True
            self._save(state)
            self._path(state, ".sock").unlink(missing_ok=True)
        return {"status": "stopped", "track": None}

    def stop(self) -> dict[str, Any]:
        with self._lock():
            return self._stop(self._state())

    @staticmethod
    def _validate_tracks(tracks: list[dict[str, Any]]) -> None:
        if not tracks or len(tracks) > 114:
            raise QuranFlowError("Playback requires between 1 and 114 Surahs.")
        for track in tracks:
            try:
                url = urlsplit(str(track.get("url", "")))
                valid = (
                    url.scheme == "https"
                    and bool(url.hostname)
                    and (url.hostname == "mp3quran.net" or url.hostname.endswith(".mp3quran.net"))
                    and not url.username
                    and not url.password
                    and url.port in (None, 443)
                    and not url.fragment
                )
            except ValueError:
                valid = False
            if not valid:
                raise QuranFlowError("Playback requires validated HTTPS audio URLs.")
            if type(track.get("surah")) is not int or not 1 <= track["surah"] <= 114:
                raise QuranFlowError("Surah number must be between 1 and 114.")

    @staticmethod
    def _validate_volume(volume: int) -> None:
        if type(volume) is not int or not 0 <= volume <= 100:
            raise QuranFlowError("Volume must be an integer between 0 and 100.")

    def play(self, tracks: list[dict[str, Any]], volume: int = 65) -> dict[str, Any]:
        self._validate_tracks(tracks)
        self._validate_volume(volume)
        executable = shutil.which("mpv")
        if not executable:
            raise QuranFlowError(
                "mpv is required. Install it with your Linux package manager "
                "(Arch: sudo pacman -S mpv; Debian/Ubuntu: sudo apt install mpv)."
            )
        with self._lock():
            previous = self._state()
            self._stop(previous)
            if previous:
                for suffix in (".lua", ".event", ".event.tmp", ".log"):
                    self._path(previous, suffix).unlink(missing_ok=True)
            state: dict[str, Any] = {
                "session": secrets.token_hex(6),
                "tracks": [],
                "volume": volume,
                "pid": -1,
            }
            ipc_path = self._path(state, ".sock")
            if len(os.fsencode(ipc_path)) >= 104:
                raise QuranFlowError(
                    "Playback runtime path is too long for a Unix IPC socket. "
                    "Use a shorter XDG_RUNTIME_DIR."
                )
            script = self._path(state, ".lua")
            event_path = self._path(state, ".event")
            _private_write(script, _RECORDER % _lua_path(event_path))
            log_path = self._path(state, ".log")
            _private_write(log_path, "")
            command = [
                executable,
                "--no-config",
                "--load-scripts=no",
                "--no-video",
                "--terminal=yes",
                "--msg-level=all=warn",
                "--input-terminal=no",
                "--idle=once",
                "--audio-client-name=QuranFlow",
                "--tls-verify=yes",
                "--network-timeout=15",
                "--cache=yes",
                "--cache-secs=20",
                "--demuxer-max-bytes=16777216",
                "--demuxer-max-back-bytes=4194304",
                "--stream-lavf-o=reconnect=1,reconnect_streamed=1,"
                "reconnect_on_network_error=1,reconnect_delay_max=3,"
                "reconnect_max_retries=3,reconnect_delay_total_max=10,respect_retry_after=0",
                f"--volume={volume}",
                f"--input-ipc-server={ipc_path}",
                f"--script={script}",
            ]
            process: subprocess.Popen[bytes] | None = None
            try:
                with log_path.open("ab") as log:
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                        close_fds=True,
                        umask=0o077,
                    )
                state["pid"] = process.pid
                state["process_token"] = _process_token(process.pid)
                deadline = time.monotonic() + _TIMEOUT
                while not ipc_path.exists():
                    if process.poll() is not None:
                        raise QuranFlowError(
                            "mpv could not start. Check installation and audio support."
                        )
                    if time.monotonic() > deadline:
                        detail = log_path.read_text(errors="replace")[:1024].strip()
                        raise QuranFlowError(
                            "mpv did not create its IPC socket in time."
                            + (f" {detail}" if detail else "")
                        )
                    time.sleep(0.025)
                ipc_path.chmod(0o600)
                for track in tracks:
                    self._ipc(state, ["loadfile", track["url"], "append"])
                playlist = self._property(state, "playlist", [])
                if len(playlist) != len(tracks):
                    raise QuranFlowError("mpv returned an unexpected playlist.")
                state["tracks"] = [
                    dict(track, playlist_id=item["id"])
                    for track, item in zip(tracks, playlist, strict=True)
                ]
                self._save(state)
                self._ipc(state, ["playlist-play-index", 0])
                return self._status(state)
            except BaseException:
                if process is not None and process.poll() is None:
                    # The child handle is ours, unlike an untrusted persisted PID.
                    process.terminate()
                    try:
                        process.wait(timeout=_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=_TIMEOUT)
                state["stopped"] = True
                if process is not None:
                    self._save(state)
                ipc_path.unlink(missing_ok=True)
                raise

    def _control(self, command: list[Any], volume: int | None = None) -> dict[str, Any]:
        with self._lock():
            state = self._state()
            if not state or state.get("stopped"):
                raise QuranFlowError("No active QuranFlow playback session.")
            self._ipc(state, command)
            if volume is not None:
                state["volume"] = volume
                self._save(state)
            return self._status(state)

    def pause(self) -> dict[str, Any]:
        return self._control(["set_property", "pause", True])

    def resume(self) -> dict[str, Any]:
        return self._control(["set_property", "pause", False])

    def set_volume(self, volume: int) -> dict[str, Any]:
        self._validate_volume(volume)
        return self._control(["set_property", "volume", volume], volume=volume)

    def replay(self) -> dict[str, Any]:
        restart: tuple[list[dict[str, Any]], int] | None = None
        with self._lock():
            state = self._state()
            if not state or not state["tracks"]:
                raise QuranFlowError(
                    "No active QuranFlow session. Start the Surah again to replay."
                )
            if state.get("stopped") or not self._alive(state):
                event = self._event(state)
                track = next(
                    (
                        item
                        for item in state["tracks"]
                        if item.get("playlist_id") == event.get("playlist_entry_id")
                    ),
                    state["tracks"][0],
                )
                restart = ([track], state.get("volume", 65))
            else:
                self._ipc(state, ["set_property", "pause", False])
                self._ipc(state, ["playlist-play-index", "current"])
                return self._status(state)
        return self.play(*restart)
