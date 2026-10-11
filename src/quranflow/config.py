"""Validated settings and private, atomic XDG storage."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import QuranFlowError


def xdg_path(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable, "")
    return Path(value) if value and Path(value).is_absolute() else fallback


@dataclass(frozen=True)
class Paths:
    config: Path
    cache: Path
    state: Path
    runtime: Path

    @classmethod
    def discover(cls) -> Paths:
        home = Path.home()
        state = xdg_path("XDG_STATE_HOME", home / ".local/state") / "quranflow"
        return cls(
            xdg_path("XDG_CONFIG_HOME", home / ".config") / "quranflow",
            xdg_path("XDG_CACHE_HOME", home / ".cache") / "quranflow",
            state,
            xdg_path("XDG_RUNTIME_DIR", state) / "quranflow-runtime",
        )


def private_dir(path: Path) -> None:
    if path.is_symlink():
        raise QuranFlowError(f"Refusing symlink storage directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise QuranFlowError(f"Storage directory is owned by another user: {path}")
    path.chmod(0o700)


def atomic_json(path: Path, value: object) -> None:
    private_dir(path.parent)
    fd, filename = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


@dataclass
class Settings:
    default_reciter: str = ""
    last_surah: int = 1
    last_edition: int = 0
    volume: int = 65
    backend: str = "mpv"
    language: str = "eng"
    autoplay: bool = False
    cache_enabled: bool = True
    cache_ttl_hours: int = 24


def validate(key: str, value: object) -> object:
    if key in {"volume", "last_surah", "last_edition", "cache_ttl_hours"}:
        ranges = {
            "volume": (0, 100),
            "last_surah": (1, 114),
            "last_edition": (0, 1000000),
            "cache_ttl_hours": (1, 720),
        }
        low, high = ranges[key]
        if isinstance(value, bool):
            raise QuranFlowError(f"{key} must be an integer from {low} to {high}.")
        try:
            number = int(str(value))
        except ValueError:
            raise QuranFlowError(f"{key} must be an integer from {low} to {high}.") from None
        if not low <= number <= high:
            raise QuranFlowError(f"{key} must be between {low} and {high}.")
        return number
    if key in {"autoplay", "cache_enabled"}:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise QuranFlowError(f"{key} must be true or false.")
    if key == "backend":
        if value != "mpv":
            raise QuranFlowError("Only the mpv backend supports all QuranFlow controls.")
    elif key == "language":
        if value not in {"eng", "ar"}:
            raise QuranFlowError("language must be eng or ar (bilingual names remain available).")
    elif key == "default_reciter":
        if not isinstance(value, str) or len(value) > 200 or any(ord(c) < 32 for c in value):
            raise QuranFlowError("default_reciter must be a reciter name or provider ID.")
    else:
        raise QuranFlowError(f"Unknown setting: {key}. Run play-quran config for available keys.")
    return value


class Config:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.path = directory / "config.json"

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected object")
            return Settings(**{key: validate(key, value) for key, value in data.items()})
        except (ValueError, TypeError) as exc:
            raise QuranFlowError(f"Invalid configuration in {self.path}: {exc}") from exc

    @contextmanager
    def locked(self) -> Iterator[None]:
        private_dir(self.directory)
        fd = os.open(self.directory / "config.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def update(self, **changes: object) -> Settings:
        validated = {key: validate(key, value) for key, value in changes.items()}
        with self.locked():
            values = asdict(self.load())
            values.update(validated)
            settings = Settings(**values)
            atomic_json(self.path, asdict(settings))
            return settings
