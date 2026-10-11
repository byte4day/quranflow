"""No network or audible playback is needed for these regression tests."""

import json
import os
import socket
import stat
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quranflow.errors import QuranFlowError
from quranflow.playback import Player


@pytest.fixture
def player(tmp_path):
    return Player(tmp_path / "runtime")


@pytest.fixture
def track():
    return {
        "surah": 36,
        "name": "Ya-Sin",
        "arabic": "يس",
        "reciter": "Yasser Al-Dosari",
        "reciter_id": 87,
        "edition": "Hafs",
        "edition_id": 1,
        "url": "https://server11.mp3quran.net/yasser/036.mp3",
    }


@pytest.fixture
def state(player, track):
    value = {
        "session": "0123456789ab",
        "pid": os.getpid(),
        "process_token": "test-token",
        "volume": 65,
        "tracks": [dict(track, playlist_id=7)],
    }
    player._save(value)
    return value


def test_private_runtime_and_state(player, state):
    assert stat.S_IMODE(player.runtime_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(player.state_file.stat().st_mode) == 0o600
    assert player._state() == state
    assert player.status()["status"] == "error"


def test_symlink_runtime_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target)
    with pytest.raises(QuranFlowError, match="symlink"):
        Player(alias)


def test_malformed_state_is_reported(player):
    player.state_file.write_text("[]")
    with pytest.raises(QuranFlowError, match="malformed"):
        player.status()


@pytest.mark.parametrize("value", [-1, 101, 0.5, "65", True])
def test_volume_validation(player, value):
    with pytest.raises(QuranFlowError, match="Volume"):
        player.set_volume(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/a.mp3",
        "/local/audio.mp3",
        "https://user:pass@example.org/a.mp3",
        "https://example.org:123/a.mp3",
        "https://mp3quran.net.evil.example/036.mp3",
        "https://server11.mp3quran.net:bad/036.mp3",
    ],
)
def test_reject_unsafe_stream_urls(player, track, url):
    with pytest.raises(QuranFlowError, match="HTTPS"):
        player.play([dict(track, url=url)])


def test_empty_playlist_and_bad_surah_rejected(player, track):
    with pytest.raises(QuranFlowError, match="between 1 and 114"):
        player.play([])
    with pytest.raises(QuranFlowError, match="Surah"):
        player.play([dict(track, surah=115)])


def test_controls_and_persistent_volume(player, state, monkeypatch):
    ipc = Mock(return_value=None)
    monkeypatch.setattr(player, "_ipc", ipc)
    monkeypatch.setattr(player, "_alive", lambda _: True)
    monkeypatch.setattr(player, "_status", lambda _: {"status": "playing"})
    player.pause()
    player.resume()
    player.replay()
    player.set_volume(40)
    commands = [call.args[1] for call in ipc.call_args_list]
    assert commands == [
        ["set_property", "pause", True],
        ["set_property", "pause", False],
        ["set_property", "pause", False],
        ["playlist-play-index", "current"],
        ["set_property", "volume", 40],
    ]
    assert player._state()["volume"] == 40


def test_controls_without_active_session(player):
    for operation in (player.pause, player.resume, player.replay):
        with pytest.raises(QuranFlowError, match="No active"):
            operation()
    assert player.stop()["status"] == "stopped"


def test_stop_uses_only_verified_ipc_never_stored_pid_signals(player, state, monkeypatch):
    alive = iter([True, False, False])
    monkeypatch.setattr(player, "_alive", lambda _: next(alive))
    ipc = Mock()
    monkeypatch.setattr(player, "_ipc", ipc)
    kill = Mock(side_effect=AssertionError("must not signal persisted PID"))
    monkeypatch.setattr(os, "kill", kill)
    assert player.stop()["status"] == "stopped"
    assert ipc.call_args.args[0]["session"] == state["session"]
    assert ipc.call_args.args[1] == ["quit"]
    assert player._state()["stopped"] is True


def test_reused_pid_is_never_controlled(player, state, monkeypatch):
    monkeypatch.setattr("quranflow.playback._process_token", lambda _: "different-token")
    ipc = Mock()
    monkeypatch.setattr(player, "_ipc", ipc)
    player.stop()
    ipc.assert_not_called()


def test_status_uses_playlist_id_for_autoplay(player, state, track, monkeypatch):
    state["tracks"].append(dict(track, surah=37, name="As-Saffat", playlist_id=9))
    player._save(state)
    monkeypatch.setattr(player, "_alive", lambda _: True)
    values = {
        "playlist": [{"id": 9, "playing": True}],
        "idle-active": False,
        "pause": False,
        "volume": 33,
        "time-pos": 8.0,
        "duration": 900.0,
    }
    monkeypatch.setattr(player, "_property", lambda _, name, default=None: values[name])
    result = player.status()
    assert result["track"]["surah"] == 37
    assert result["status"] == "playing"
    assert result["volume"] == 33


@pytest.mark.parametrize(
    ("event", "status"),
    [({"reason": "eof"}, "completed"), ({"reason": "error", "file_error": "broken"}, "error")],
)
def test_completion_and_error_retained_without_daemon(player, state, event, status):
    event["playlist_entry_id"] = 7
    player._path(state, ".event").write_text(json.dumps(event))
    result = player.status()
    assert result["status"] == status
    assert result["track"]["surah"] == 36
    if status == "error":
        assert result["error"] == "broken"


def mock_socket(monkeypatch, state):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.getsockopt.return_value = struct.pack("3i", os.getpid(), os.getuid(), 0)
    monkeypatch.setattr(socket, "socket", Mock(return_value=client))
    monkeypatch.setattr(
        Path, "lstat", lambda _: SimpleNamespace(st_mode=stat.S_IFSOCK | 0o600, st_uid=os.getuid())
    )
    return client


def test_ipc_filters_events_and_mismatched_request_ids(player, state, monkeypatch):
    monkeypatch.setattr(player, "_alive", lambda _: True)
    client = mock_socket(monkeypatch, state)

    def respond(_):
        request = json.loads(client.sendall.call_args.args[0])
        payload = [
            {"event": "file-loaded"},
            {"request_id": -1, "error": "success"},
            {"request_id": request["request_id"], "error": "success", "data": 65},
        ]
        return ("\n".join(json.dumps(item) for item in payload) + "\n").encode()

    client.recv.side_effect = respond
    assert player._ipc(state, ["get_property", "volume"]) == 65


def test_ipc_rejects_different_peer_pid(player, state, monkeypatch):
    monkeypatch.setattr(player, "_alive", lambda _: True)
    state["pid"] = os.getpid() + 1
    client = mock_socket(monkeypatch, state)
    with pytest.raises(QuranFlowError, match="identity"):
        player._ipc(state, ["quit"])
    client.sendall.assert_not_called()


def test_ipc_timeout_is_actionable(player, state, monkeypatch):
    monkeypatch.setattr(player, "_alive", lambda _: True)
    client = mock_socket(monkeypatch, state)
    client.recv.side_effect = TimeoutError("timed out")
    with pytest.raises(QuranFlowError, match="timed out"):
        player._ipc(state, ["get_property", "volume"])


def test_ipc_event_flood_is_bounded(player, state, monkeypatch):
    monkeypatch.setattr(player, "_alive", lambda _: True)
    monkeypatch.setattr("quranflow.playback._MAX_MESSAGE", 32)
    client = mock_socket(monkeypatch, state)
    client.recv.return_value = b'{"event":"file-loaded","padding":"too much"}\n'
    with pytest.raises(QuranFlowError, match="size limit"):
        player._ipc(state, ["get_property", "volume"])


def test_replay_completed_surah_retains_attribution(player, state, monkeypatch):
    monkeypatch.setattr(player, "_alive", lambda _: False)
    play = Mock(return_value={"status": "loading"})
    monkeypatch.setattr(player, "play", play)
    assert player.replay()["status"] == "loading"
    selected, volume = play.call_args.args
    assert selected[0]["surah"] == 36
    assert selected[0]["reciter"] == "Yasser Al-Dosari"
    assert volume == 65


def test_failed_child_start_is_reaped(player, track, monkeypatch):
    monkeypatch.setattr("quranflow.playback.shutil.which", lambda _: "/usr/bin/mpv")
    child = Mock(pid=8765)
    child.poll.return_value = 1
    monkeypatch.setattr("quranflow.playback.subprocess.Popen", Mock(return_value=child))
    with pytest.raises(QuranFlowError, match="could not start"):
        player.play([track])
    assert player._state()["stopped"] is True
    child.terminate.assert_not_called()


def test_startup_timeout_terminates_only_spawned_child(player, track, monkeypatch):
    monkeypatch.setattr("quranflow.playback.shutil.which", lambda _: "/usr/bin/mpv")
    child = Mock(pid=8765)
    child.poll.return_value = None
    monkeypatch.setattr("quranflow.playback.subprocess.Popen", Mock(return_value=child))
    monkeypatch.setattr("quranflow.playback._TIMEOUT", 0.005)
    with pytest.raises(QuranFlowError, match="in time"):
        player.play([track])
    child.terminate.assert_called_once()
    child.wait.assert_called_once()


def test_missing_backend_message(player, track, monkeypatch):
    monkeypatch.setattr("quranflow.playback.shutil.which", lambda _: None)
    with pytest.raises(QuranFlowError, match="mpv is required"):
        player.play([track])


def test_lua_recorder_path_preserves_unicode_and_control_bytes():
    from quranflow.playback import _lua_path

    path = Path('/tmp/قرآن/"quoted"\\name\x01.event')
    quoted = _lua_path(path)
    assert quoted.startswith('"') and quoted.endswith('"')
    encoded = bytes(int(quoted[index : index + 3]) for index in range(2, len(quoted) - 1, 4))
    assert encoded == os.fsencode(path)


def test_start_builds_detached_playlist_and_private_session(player, track, monkeypatch):
    monkeypatch.setattr("quranflow.playback.shutil.which", lambda _: "/usr/bin/mpv")
    monkeypatch.setattr("quranflow.playback._process_token", lambda _: "test-token")
    child = Mock(pid=8765)

    def spawn(arguments, **kwargs):
        path = Path(
            next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--input-ipc-server="))
        )
        path.touch()  # IPC is mocked; lifecycle, arguments and modes are real.
        assert kwargs["start_new_session"] is True
        assert kwargs["umask"] == 0o077
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert "--tls-verify=yes" in arguments
        return child

    monkeypatch.setattr("quranflow.playback.subprocess.Popen", spawn)
    ipc = Mock()
    monkeypatch.setattr(player, "_ipc", ipc)
    monkeypatch.setattr(player, "_property", lambda *_: [{"id": 31}, {"id": 45}])
    monkeypatch.setattr(player, "_status", lambda _: {"status": "playing"})
    player.play([track, dict(track, surah=37)], volume=70)
    state = player._state()
    assert [item["playlist_id"] for item in state["tracks"]] == [31, 45]
    assert state["volume"] == 70
    assert [call.args[1][0] for call in ipc.call_args_list] == [
        "loadfile",
        "loadfile",
        "playlist-play-index",
    ]
    assert stat.S_IMODE(player._path(state, ".sock").stat().st_mode) == 0o600
