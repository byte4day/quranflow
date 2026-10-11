import json
from unittest.mock import Mock

import pytest

from quranflow import cli
from quranflow.config import Config, Paths
from quranflow.reciters import Edition, Reciter


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    paths = Paths(tmp_path / "config", tmp_path / "cache", tmp_path / "state", tmp_path / "run")
    monkeypatch.setattr(cli.Paths, "discover", lambda: paths)
    player = Mock()
    player.play.return_value = {"status": "loading", "track": None}
    player.status.return_value = {"status": "stopped", "track": None}
    for action in ["pause", "resume", "stop", "replay", "set_volume"]:
        getattr(player, action).return_value = {"status": "stopped", "track": None}
    monkeypatch.setattr(cli, "Player", lambda _: player)
    catalog = [
        Reciter(
            123,
            "Yasser Al-Dosari",
            (
                Edition(
                    456,
                    "Hafs - Murattal",
                    "https://server11.mp3quran.net/yasser/",
                    frozenset({1, 18, 36, 114}),
                ),
            ),
        )
    ]
    provider = Mock()
    provider.catalog.return_value = catalog
    monkeypatch.setattr(cli, "Provider", lambda *a, **k: provider)
    return paths, player, provider


@pytest.mark.parametrize(
    "arguments",
    [
        ["yasin", "--reciter", "dosari"],
        ["--surah", "36", "--reciter", "dosari"],
        ["play", "Ya-Sin", "--reciter", "dosari"],
    ],
)
def test_play_variants(arguments, isolated):
    paths, player, _ = isolated
    assert cli.main(arguments + ["--json"]) == 0
    tracks = player.play.call_args.args[0]
    assert tracks[0]["surah"] == 36
    assert tracks[0]["reciter"] == "Yasser Al-Dosari"
    assert tracks[0]["url"].endswith("/036.mp3")
    assert Config(paths.config).load().last_surah == 36


def test_autoplay_uses_availability_only(isolated):
    _, player, _ = isolated
    assert cli.main(["18", "--reciter", "dosari", "--autoplay", "--json"]) == 0
    assert [t["surah"] for t in player.play.call_args.args[0]] == [18, 36, 114]


def test_no_recording_no_play(isolated, capsys):
    _, player, _ = isolated
    assert cli.main(["2", "--reciter", "dosari"]) == 1
    player.play.assert_not_called()
    assert "has no recording" in capsys.readouterr().err


def test_multiple_editions_require_selection(isolated, capsys):
    _, player, provider = isolated
    first = provider.catalog.return_value[0]
    provider.catalog.return_value = [
        Reciter(
            first.id,
            first.name,
            first.editions
            + (
                Edition(
                    789, "Another edition", "https://server11.mp3quran.net/yasser/", frozenset({36})
                ),
            ),
        )
    ]
    assert cli.main(["36", "--reciter", "dosari"]) == 1
    player.play.assert_not_called()
    assert "requires a terminal" in capsys.readouterr().err
    assert cli.main(["36", "--reciter", "dosari", "--edition", "789", "--json"]) == 0
    assert player.play.call_args.args[0][0]["edition_id"] == 789


@pytest.mark.parametrize("action", ["pause", "resume", "stop", "status", "replay"])
def test_controls(action, isolated):
    _, player, _ = isolated
    assert cli.main([action, "--json"]) == 0
    getattr(player, action).assert_called_once()


def test_volume_persistence(isolated):
    paths, player, _ = isolated
    assert cli.main(["volume", "30", "--json"]) == 0
    player.set_volume.assert_called_once_with(30)
    assert Config(paths.config).load().volume == 30


def test_change_reciter_does_not_reuse_old_edition(isolated):
    paths, player, _ = isolated
    Config(paths.config).update(default_reciter="999", last_edition=999)
    player.status.return_value = {"track": {"surah": 36, "reciter_id": 999, "edition_id": 999}}
    assert cli.main(["change", "--reciter", "dosari", "--json"]) == 0
    assert player.play.call_args.args[0][0]["edition_id"] == 456


def test_last_memory(isolated):
    paths, player, _ = isolated
    Config(paths.config).update(default_reciter="123", last_surah=18, last_edition=456)
    assert cli.main(["--last", "--json"]) == 0
    assert player.play.call_args.args[0][0]["surah"] == 18


def test_noninteractive_no_args_actionable(isolated, capsys):
    assert cli.main([]) == 1
    assert "Specify --surah and --reciter" in capsys.readouterr().err


def test_offline_surahs_json(isolated, capsys):
    _, player, provider = isolated
    assert cli.main(["surahs", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 114
    provider.catalog.assert_not_called()
    player.play.assert_not_called()


def test_reciter_json_availability(isolated, capsys):
    assert cli.main(["reciters", "--surah", "2", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


@pytest.mark.parametrize(
    "arguments",
    [
        ["--surah", "0", "--reciter", "dosari"],
        ["yasin", "--surah", "36", "--reciter", "dosari"],
        ["volume", "200"],
        ["stop", "extra"],
        ["config", "set", "backend", "ffplay"],
    ],
)
def test_invalid_input(arguments, isolated):
    assert cli.main(arguments) == 1


def test_config_reciter_resolution(isolated):
    paths, _, _ = isolated
    assert cli.main(["config", "set", "default_reciter", "dosari", "--json"]) == 0
    assert Config(paths.config).load().default_reciter == "123"


def test_preferred_reciter_change_resets_edition(isolated):
    paths, player, provider = isolated
    Config(paths.config).update(default_reciter="999", last_edition=999, last_surah=36)
    assert cli.main(["config", "set", "default_reciter", "dosari", "--json"]) == 0
    assert Config(paths.config).load().last_edition == 0
    assert cli.main(["--last", "--json"]) == 0
    assert player.play.call_args.args[0][0]["edition_id"] == 456


def test_same_preferred_reciter_retains_edition(isolated):
    paths, _, _ = isolated
    Config(paths.config).update(default_reciter="123", last_edition=456)
    assert cli.main(["config", "set", "default_reciter", "dosari", "--json"]) == 0
    assert Config(paths.config).load().last_edition == 456


@pytest.mark.parametrize(
    "arguments",
    [
        ["pause", "--volume", "200"],
        ["status", "--autoplay"],
        ["stop", "--edition", "0"],
        ["surahs", "--reciter", "dosari"],
        ["config", "--refresh"],
    ],
)
def test_unused_options_are_rejected(arguments, isolated):
    assert cli.main(arguments) == 1


def test_invalid_start_volume_fails_before_network(isolated):
    _, player, provider = isolated
    assert cli.main(["--volume", "200"]) == 1
    provider.catalog.assert_not_called()
    player.play.assert_not_called()
