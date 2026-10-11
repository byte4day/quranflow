#!/usr/bin/env python3
"""Resolve the installed executable without relying on the working directory."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def executable() -> str:
    installation = Path(__file__).with_name("installation.json")
    if installation.is_file():
        try:
            value = json.loads(installation.read_text(encoding="utf-8"))["executable"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "QuranFlow skill installation is damaged; rerun install.sh."
            ) from exc
        candidate = Path(value) if isinstance(value, str) else None
        if candidate is None or not candidate.is_absolute() or not os.access(candidate, os.X_OK):
            raise RuntimeError("QuranFlow executable is missing; rerun install.sh.")
        return str(candidate)
    candidate = Path.home() / ".local/bin/play-quran"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    found = shutil.which("play-quran")
    if found:
        return found
    raise RuntimeError("QuranFlow is not installed. Run ./install.sh in its checkout.")


def main() -> int:
    try:
        target = executable()
        os.execv(target, [target, *sys.argv[1:]])
    except (OSError, RuntimeError) as exc:
        print(f"QuranFlow: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
