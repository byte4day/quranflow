#!/usr/bin/env python3
"""User-scoped QuranFlow installer. No system packages or shell profiles are changed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OWNER = {"owner": "quranflow", "schema": 1}


def directories(home: Path) -> dict[str, Path]:
    data = home / ".local/share/quranflow"
    return {
        "home": home,
        "data": data,
        "venv": data / "venv",
        "manifest": data / "install-manifest.json",
        "backups": data / "backups",
        "bin": home / ".local/bin/play-quran",
        "skill": home / ".agents/skills/play-quran",
        "claude_skill": home / ".claude/skills/play-quran",
        "command": home / ".cursor/commands/play-quran.md",
    }


def allowed_files(paths: dict[str, Path]) -> set[Path]:
    return {
        paths["bin"],
        paths["command"],
        paths["skill"] / "SKILL.md",
        paths["skill"] / "scripts/play_quran.py",
        paths["skill"] / "scripts/installation.json",
        paths["claude_skill"] / "SKILL.md",
        paths["claude_skill"] / "scripts/play_quran.py",
        paths["claude_skill"] / "scripts/installation.json",
    }


def check_path(path: Path, home: Path) -> None:
    """Refuse symlinked destinations, including parent directories."""
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(home):
        raise RuntimeError(f"Destination outside installation home: {path}")
    current = path
    while current != home:
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlinked installation destination: {current}")
        current = current.parent


def write_file(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(mode)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_manifest(paths: dict[str, Path]) -> dict[str, Any]:
    manifest = paths["manifest"]
    if not manifest.exists():
        return {**OWNER, "files": []}
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(payload.get(k) != v for k, v in OWNER.items()):
        raise RuntimeError("Invalid QuranFlow installation manifest; refusing to overwrite it.")
    entries = payload.get("files")
    if not isinstance(entries, list):
        raise RuntimeError("Invalid QuranFlow installation file list.")
    for entry in entries:
        if not isinstance(entry, dict) or Path(entry.get("path", "")) not in allowed_files(paths):
            raise RuntimeError("Installation manifest contains an unexpected file path.")
        if not isinstance(entry.get("sha256"), str) or not isinstance(
            entry.get("backups", []), list
        ):
            raise RuntimeError("Invalid QuranFlow installation file metadata.")
        for backup in entry.get("backups", []):
            if not isinstance(backup, str) or not Path(backup).is_relative_to(paths["backups"]):
                raise RuntimeError("Installation manifest contains an unexpected backup path.")
    return payload


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def managed_file(
    path: Path, content: bytes, mode: int, paths: dict[str, Path], previous: dict[str, Any]
) -> dict[str, Any]:
    check_path(path, paths["home"])
    backups = list(previous.get("backups", []))
    wanted = hashlib.sha256(content).hexdigest()
    if path.exists():
        if not path.is_file():
            raise RuntimeError(f"Installation destination is not a file: {path}")
        current = digest(path)
        if current != wanted and current != previous.get("sha256"):
            backup = paths["backups"] / f"{path.name}.{uuid.uuid4().hex}.bak"
            write_file(backup, path.read_bytes(), path.stat().st_mode & 0o777)
            backups.append(str(backup))
            print(f"Backed up existing file: {path} -> {backup}")
        if current == wanted:
            path.chmod(mode)
            return {"path": str(path), "sha256": wanted, "backups": backups}
    write_file(path, content, mode)
    return {"path": str(path), "sha256": wanted, "backups": backups}


def subprocess_environment(home: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if home is not None:
        env.update(
            {
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_RUNTIME_DIR": str(home / ".local/run"),
            }
        )
        runtime = home / ".local/run"
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        runtime.chmod(0o700)
    return env


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, timeout=180, **kwargs)


def install_package(paths: dict[str, Path], source: Path, offline: bool) -> None:
    location = paths["venv"]
    marker = location / ".quranflow-managed.json"
    if location.exists():
        if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != OWNER:
            raise RuntimeError(f"Refusing to modify an unrelated environment: {location}")
    uv = shutil.which("uv")
    if not location.exists():
        venv.EnvBuilder(with_pip=uv is None).create(location)
        write_file(marker, json.dumps(OWNER).encode())
    python = location / "bin/python"
    if uv:
        command = [uv, "pip", "install", "--python", str(python), "--no-deps", "--reinstall"]
        if offline:
            command.append("--offline")
        if source.suffix == ".whl":
            command.append("--no-cache")
        command.extend(["--no-python-downloads", str(source)])
    else:
        command = [str(python), "-m", "pip", "install", "--no-deps", "--force-reinstall"]
        if offline:
            command.append("--no-index")
        command.append(str(source))
    run(command)
    run([str(location / "bin/play-quran"), "--version"])


def dependency_message() -> None:
    if shutil.which("mpv"):
        print(f"Audio backend: {shutil.which('mpv')}")
        return
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    distro = f"{release.get('ID', '')} {release.get('ID_LIKE', '')}"
    if "arch" in distro:
        command = "sudo pacman -S mpv"
    elif "debian" in distro or "ubuntu" in distro:
        command = "sudo apt install mpv python3-venv"
    elif "fedora" in distro or "rhel" in distro:
        command = "sudo dnf install mpv"
    else:
        command = "install the mpv package using your Linux distribution's package manager"
    print(f"mpv is missing. Playback requires mpv; run: {command}")


def install(home: Path, *, offline: bool = False, wheel: Path | None = None) -> dict[str, Any]:
    if platform.system() != "Linux":
        raise RuntimeError("QuranFlow currently supports Linux only.")
    if sys.version_info < (3, 11):  # noqa: UP036 - standalone installer runs before packaging checks
        raise RuntimeError("QuranFlow requires Python 3.11 or newer.")
    home = home.expanduser().resolve()
    paths = directories(home)
    for path in {*allowed_files(paths), paths["venv"], paths["manifest"], paths["backups"]}:
        check_path(path, home)
    previous = read_manifest(paths)
    paths["data"].mkdir(parents=True, exist_ok=True, mode=0o700)
    paths["data"].chmod(0o700)
    source = ROOT
    if wheel is not None:
        source = wheel.expanduser().resolve()
        if not source.is_file() or source.suffix != ".whl":
            raise RuntimeError("--wheel must identify an existing Python wheel file.")
    # Record ownership before package building, so a failed first install can be cleaned up.
    write_file(paths["manifest"], json.dumps(previous, indent=2).encode())
    install_package(paths, source, offline)
    records = {entry["path"]: entry for entry in previous["files"]}
    player = paths["venv"] / "bin/play-quran"
    launcher = (
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        f"os.execv({str(player)!r}, [{str(player)!r}, *sys.argv[1:]])\n"
    ).encode()
    sources: list[tuple[Path, bytes, int]] = [(paths["bin"], launcher, 0o755)]
    helper = (ROOT / ".agents/skills/play-quran/scripts/play_quran.py").read_bytes()
    installation = json.dumps({"executable": str(paths["bin"])}).encode()
    for destination, origin in (
        (paths["skill"], ROOT / ".agents/skills/play-quran"),
        (paths["claude_skill"], ROOT / ".claude/skills/play-quran"),
    ):
        sources.extend(
            [
                (destination / "SKILL.md", (origin / "SKILL.md").read_bytes(), 0o644),
                (destination / "scripts/play_quran.py", helper, 0o755),
                (destination / "scripts/installation.json", installation, 0o600),
            ]
        )
    sources.append(
        (paths["command"], (ROOT / ".cursor/commands/play-quran.md").read_bytes(), 0o644)
    )
    manifest = {**OWNER, "files": list(previous["files"])}
    for path, content, mode in sources:
        entry = managed_file(path, content, mode, paths, records.get(str(path), {}))
        manifest["files"] = [item for item in manifest["files"] if item["path"] != str(path)]
        manifest["files"].append(entry)
        # Persist ownership immediately so an interrupted installation can be uninstalled.
        write_file(paths["manifest"], json.dumps(manifest, indent=2).encode())
    run([str(paths["bin"]), "--version"])
    dependency_message()
    print(f"Installed CLI: {paths['bin']}")
    print(f"Installed shared Codex/Cursor skill: {paths['skill']}")
    print(f"Installed Claude Code skill (/play-quran): {paths['claude_skill']}")
    print(f"Installed Cursor command compatibility adapter: {paths['command']}")
    if str(paths["bin"].parent) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"Add {paths['bin'].parent} to PATH to invoke play-quran by name.")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home", type=Path, default=Path.home(), help="alternate installation home"
    )
    parser.add_argument(
        "--offline", action="store_true", help="disable package-index network access"
    )
    parser.add_argument("--wheel", type=Path, help="install a previously built local wheel")
    arguments = parser.parse_args()
    try:
        install(arguments.home, offline=arguments.offline, wheel=arguments.wheel)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"QuranFlow installation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
