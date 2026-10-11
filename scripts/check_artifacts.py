"""Validate packaged metadata and absence of local settings/audio in wheel/sdist."""

from __future__ import annotations

import json
import sys
import tarfile
import zipfile
from pathlib import Path


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    (wheel,) = directory.glob("quranflow-*.whl")
    (archive,) = directory.glob("quranflow-*.tar.gz")
    with zipfile.ZipFile(wheel) as package:
        names = package.namelist()
        assert "quranflow/data/surahs.json" in names
        data = json.loads(package.read("quranflow/data/surahs.json"))
        assert len(data["data"] if isinstance(data, dict) else data) == 114
        assert any(name.endswith("/entry_points.txt") for name in names)
    with tarfile.open(archive) as package:
        sdist_names = package.getnames()
    required = [
        "LICENSE",
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "install.sh",
        "uninstall.sh",
        "scripts/install.py",
        "scripts/uninstall.py",
        ".agents/skills/play-quran/SKILL.md",
        ".agents/skills/play-quran/scripts/play_quran.py",
        ".cursor/commands/play-quran.md",
        ".github/workflows/ci.yml",
    ]
    for name in required:
        assert any(path.endswith("/" + name) for path in sdist_names), f"Missing {name}"
    for name in names + sdist_names:
        path = Path(name)
        assert path.suffix not in {".mp3", ".wav", ".ogg", ".sock", ".pyc"}, name
        assert path.name not in {
            "config.json",
            "session.json",
            "installation.json",
            "install-manifest.json",
            ".env",
        }, name
        assert "video" not in path.parts and "node_modules" not in path.parts, name
    print(
        "Wheel/sdist contents verified: 114 Surahs, integrations, license, no audio or personal state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
