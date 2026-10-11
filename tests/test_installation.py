"""Filesystem tests keep installer behavior independent of package indexes and audio."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import install  # noqa: E402
import uninstall  # noqa: E402


@pytest.fixture
def package_install(monkeypatch: pytest.MonkeyPatch) -> Mock:
    def create_environment(paths: dict[str, Path], source: Path, offline: bool) -> None:
        location = paths["venv"]
        (location / "bin").mkdir(parents=True, exist_ok=True)
        install.write_file(location / ".quranflow-managed.json", json.dumps(install.OWNER).encode())
        (location / "bin/play-quran").write_text("placeholder", encoding="utf-8")

    mock = Mock(side_effect=create_environment)
    monkeypatch.setattr(install, "install_package", mock)
    monkeypatch.setattr(install, "run", Mock())
    monkeypatch.setattr(install, "dependency_message", Mock())
    monkeypatch.setattr(install.platform, "system", lambda: "Linux")
    return mock


def test_installs_absolute_shared_skill_and_callable_launcher(
    tmp_path: Path, package_install: Mock
) -> None:
    manifest = install.install(tmp_path)
    paths = install.directories(tmp_path)
    assert len(manifest["files"]) == 5
    configuration = json.loads((paths["skill"] / "scripts/installation.json").read_text())
    assert configuration["executable"] == str(paths["bin"])
    assert paths["bin"].stat().st_mode & 0o111
    assert str(paths["venv"] / "bin/play-quran") in paths["bin"].read_text()
    assert paths["manifest"].stat().st_mode & 0o777 == 0o600
    assert paths["command"].exists()
    package_install.assert_called_once()


def test_repeat_install_preserves_original_backup_and_restores_on_uninstall(
    tmp_path: Path, package_install: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = install.directories(tmp_path)
    paths["command"].parent.mkdir(parents=True)
    paths["command"].write_text("personal command", encoding="utf-8")
    (tmp_path / ".config/quranflow").mkdir(parents=True)
    settings = tmp_path / ".config/quranflow/config.json"
    settings.write_text('{"volume": 65}')
    first = install.install(tmp_path)
    second = install.install(tmp_path)
    first_command = next(
        entry for entry in first["files"] if entry["path"] == str(paths["command"])
    )
    second_command = next(
        entry for entry in second["files"] if entry["path"] == str(paths["command"])
    )
    assert first_command["backups"] == second_command["backups"]
    assert len(second_command["backups"]) == 1
    stop = Mock()
    monkeypatch.setattr(uninstall.subprocess, "run", stop)
    assert uninstall.uninstall(tmp_path)
    assert paths["command"].read_text() == "personal command"
    assert settings.read_text() == '{"volume": 65}'
    assert not paths["bin"].exists()
    assert not paths["venv"].exists()
    assert stop.call_args.kwargs["env"]["XDG_STATE_HOME"] == str(tmp_path / ".local/state")


def test_uninstall_preserves_user_edits_and_required_environment(
    tmp_path: Path, package_install: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    install.install(tmp_path)
    paths = install.directories(tmp_path)
    paths["command"].write_text("my customized command")
    monkeypatch.setattr(uninstall.subprocess, "run", Mock())
    assert not uninstall.uninstall(tmp_path)
    assert paths["command"].read_text() == "my customized command"
    assert paths["venv"].exists()
    assert paths["manifest"].exists()


def test_symlink_destination_is_rejected_without_modifying_target(
    tmp_path: Path, package_install: Mock
) -> None:
    target = tmp_path / "valuable"
    target.write_text("keep")
    paths = install.directories(tmp_path)
    paths["bin"].parent.mkdir(parents=True)
    paths["bin"].symlink_to(target)
    with pytest.raises(RuntimeError, match="symlink"):
        install.install(tmp_path)
    assert target.read_text() == "keep"
    package_install.assert_not_called()


def test_uninstall_rejects_manifest_paths_outside_owned_files(tmp_path: Path) -> None:
    paths = install.directories(tmp_path)
    valuable = tmp_path / "valuable"
    valuable.write_text("keep")
    install.write_file(
        paths["manifest"],
        json.dumps(
            {
                **install.OWNER,
                "files": [{"path": str(valuable), "sha256": install.digest(valuable)}],
            }
        ).encode(),
    )
    with pytest.raises(RuntimeError, match="unexpected file"):
        uninstall.uninstall(tmp_path)
    assert valuable.read_text() == "keep"


def test_uninstall_does_not_remove_environment_if_stop_fails(
    tmp_path: Path, package_install: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    install.install(tmp_path)
    paths = install.directories(tmp_path)
    monkeypatch.setattr(
        uninstall.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("stop", 10))
    )
    with pytest.raises(subprocess.TimeoutExpired):
        uninstall.uninstall(tmp_path)
    assert paths["venv"].exists()
    assert paths["bin"].exists()


def test_uninstall_without_manifest_does_not_modify_other_install(tmp_path: Path) -> None:
    paths = install.directories(tmp_path)
    paths["bin"].parent.mkdir(parents=True)
    paths["bin"].write_text("some other tool")
    assert not uninstall.uninstall(tmp_path)
    assert paths["bin"].read_text() == "some other tool"


def test_package_install_refuses_foreign_venv(tmp_path: Path) -> None:
    paths = install.directories(tmp_path)
    paths["venv"].mkdir(parents=True)
    with pytest.raises(RuntimeError, match="unrelated environment"):
        install.install_package(paths, ROOT, offline=True)


def test_failed_package_install_remains_uninstallable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_install(paths: dict[str, Path], source: Path, offline: bool) -> None:
        paths["venv"].mkdir(parents=True)
        install.write_file(
            paths["venv"] / ".quranflow-managed.json", json.dumps(install.OWNER).encode()
        )
        raise RuntimeError("build failed")

    monkeypatch.setattr(install, "install_package", broken_install)
    with pytest.raises(RuntimeError, match="build failed"):
        install.install(tmp_path)
    assert uninstall.uninstall(tmp_path)
    assert not install.directories(tmp_path)["venv"].exists()


def test_helper_runs_from_unrelated_directory_without_path_lookup(tmp_path: Path) -> None:
    helper = tmp_path / "skill" / "play_quran.py"
    helper.parent.mkdir()
    helper.write_bytes((ROOT / ".agents/skills/play-quran/scripts/play_quran.py").read_bytes())
    player = tmp_path / "target with spaces"
    player.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
    player.chmod(0o755)
    helper.with_name("installation.json").write_text(json.dumps({"executable": str(player)}))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    expected = ["--surah", "18", "--reciter", "Yasser Al-Dosari"]
    result = subprocess.run(
        [sys.executable, str(helper), *expected],
        cwd=unrelated,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == expected


def test_helper_executes_installed_path_and_preserves_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    helper_source = ROOT / ".agents/skills/play-quran/scripts/play_quran.py"
    helper_path = tmp_path / "play_quran.py"
    helper_path.write_bytes(helper_source.read_bytes())
    player = tmp_path / "player with spaces"
    player.write_text("#!/bin/sh\nexit 0\n")
    player.chmod(0o755)
    (tmp_path / "installation.json").write_text(json.dumps({"executable": str(player)}))
    spec = importlib.util.spec_from_file_location("skill_helper_test", helper_path)
    assert spec and spec.loader
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    monkeypatch.setattr(sys, "argv", [str(helper_path), "--surah", "18", "--reciter", "dosari"])
    execute = Mock()
    monkeypatch.setattr(os, "execv", execute)
    assert helper.main() == 0
    execute.assert_called_once_with(
        str(player), [str(player), "--surah", "18", "--reciter", "dosari"]
    )


def test_helper_reports_missing_recorded_executable(tmp_path: Path) -> None:
    helper_path = tmp_path / "play_quran.py"
    helper_path.write_bytes((ROOT / ".agents/skills/play-quran/scripts/play_quran.py").read_bytes())
    (tmp_path / "installation.json").write_text('{"executable": "/missing-quranflow-player"}')
    result = subprocess.run(
        [sys.executable, str(helper_path), "status"], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "rerun install.sh" in result.stderr
