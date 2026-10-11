import json
import stat

import pytest

from quranflow.config import Config, Paths, Settings, validate
from quranflow.errors import QuranFlowError


def test_persistence_and_privacy(tmp_path):
    config = Config(tmp_path / "config")
    assert config.load() == Settings()
    config.update(volume=80, autoplay=True, default_reciter="123")
    assert Config(config.directory).load().volume == 80
    config.update(language="ar")
    assert config.load().autoplay is True
    assert config.load().default_reciter == "123"
    assert stat.S_IMODE(config.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config.directory.stat().st_mode) == 0o700


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("volume", -1),
        ("volume", 101),
        ("volume", True),
        ("volume", "3.5"),
        ("last_surah", 115),
        ("last_surah", 0),
        ("cache_ttl_hours", 0),
        ("backend", "ffplay"),
        ("language", "invalid"),
        ("autoplay", "yes"),
        ("cache_enabled", 1),
        ("default_reciter", "name\x1b"),
        ("unknown", "value"),
    ],
)
def test_invalid_config(key, value):
    with pytest.raises(QuranFlowError):
        validate(key, value)


def test_bad_configuration_not_overwritten(tmp_path):
    config = Config(tmp_path)
    config.path.write_text('{"volume": "bad"}')
    with pytest.raises(QuranFlowError):
        config.update(volume=10)
    assert json.loads(config.path.read_text()) == {"volume": "bad"}


def test_xdg_absolute_and_relative(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("XDG_CACHE_HOME", "relative")
    paths = Paths.discover()
    assert paths.config == tmp_path / "cfg/quranflow"
    assert paths.runtime == tmp_path / "run/quranflow-runtime"
    assert paths.cache.is_absolute()


def test_symlink_storage_refused(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(QuranFlowError, match="symlink"):
        Config(link).update(volume=10)
