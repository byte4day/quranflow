#!/usr/bin/env python3
"""Remove only files owned by the installer; preserve user settings and edited files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from install import OWNER, check_path, digest, directories, read_manifest, subprocess_environment


def uninstall(home: Path) -> bool:
    home = home.expanduser().resolve()
    paths = directories(home)
    check_path(paths["manifest"], home)
    if not paths["manifest"].exists():
        print("QuranFlow has no installation manifest here; nothing was removed.")
        return False
    manifest = read_manifest(paths)
    player = paths["venv"] / "bin/play-quran"
    check_path(paths["venv"], home)
    marker = paths["venv"] / ".quranflow-managed.json"
    owns_venv = (
        not marker.is_symlink() and marker.is_file() and json.loads(marker.read_text()) == OWNER
    )
    if owns_venv and player.is_file():
        # stop communicates only with this user's QuranFlow IPC socket.
        subprocess.run(
            [str(player), "stop"],
            check=True,
            timeout=10,
            capture_output=True,
            text=True,
            env=subprocess_environment(home if home != Path.home().resolve() else None),
        )
    preserved = []
    for entry in reversed(manifest["files"]):
        path = Path(entry["path"])
        check_path(path, home)
        if path.exists() and (not path.is_file() or digest(path) != entry["sha256"]):
            print(f"Preserved modified file: {path}")
            preserved.append(entry)
            continue
        path.unlink(missing_ok=True)
        backups = entry.get("backups", [])
        if backups:
            backup = Path(backups[-1])
            check_path(backup, home)
            if backup.is_file():
                backup.replace(path)
                print(f"Restored previous file: {path}")
    if preserved:
        # A modified launcher/helper may still need its interpreter.
        manifest["files"] = preserved
        paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(
            "Edited files and the managed Python environment remain; inspect them before removing."
        )
        return False
    if owns_venv:
        shutil.rmtree(paths["venv"])
    else:
        print(f"Preserved environment without a valid ownership marker: {paths['venv']}")
    paths["manifest"].unlink()
    print("QuranFlow uninstalled. Configuration, metadata cache, and unused backups were retained.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home", type=Path, default=Path.home(), help="alternate installation home"
    )
    arguments = parser.parse_args()
    try:
        uninstall(arguments.home)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"QuranFlow uninstall failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
