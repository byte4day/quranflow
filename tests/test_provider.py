"""MP3Quran documentation fixtures; no external network/audio required."""

import copy
import io
import json
import logging
import os
import time
import urllib.error
from unittest.mock import Mock

import pytest

from quranflow.errors import QuranFlowError
from quranflow.provider import (
    API_URL,
    MAX_RESPONSE_BYTES,
    Provider,
    _TrustedRedirect,
    parse_catalog,
)
from quranflow.reciters import audio_url


@pytest.fixture
def payload():
    # Real documentation sample identity/server; partial chapter lists exercise availability.
    return {
        "reciters": [
            {
                "id": 1,
                "name": "Ibrahim Al-Akdar",
                "moshaf": [
                    {
                        "id": 1,
                        "name": "Rewayat Hafs A'n Assem - Murattal",
                        "server": "https://server6.mp3quran.net/akdr/",
                        "surah_total": 114,
                        "surah_list": "1,18,36,114",
                    }
                ],
            },
            {
                "id": 231,
                "name": "Hazza Al-Balushi",
                "moshaf": [
                    {
                        "id": 231,
                        "name": "Rewayat Hafs A'n Assem - Murattal",
                        "server": "https://server11.mp3quran.net/hazza/",
                        "surah_total": 83,
                        "surah_list": "1,6,18,36",
                    }
                ],
            },
        ]
    }


def test_documentation_response_preserves_identity_and_availability(payload):
    catalog = parse_catalog(payload)
    assert [(r.id, r.name) for r in catalog] == [(1, "Ibrahim Al-Akdar"), (231, "Hazza Al-Balushi")]
    assert catalog[0].editions[0].surahs == {1, 18, 36, 114}
    assert 2 not in catalog[1].editions[0].surahs
    assert audio_url(catalog[1].editions[0], 18) == "https://server11.mp3quran.net/hazza/018.mp3"


def test_multiple_editions_are_preserved(payload):
    second = copy.deepcopy(payload["reciters"][0]["moshaf"][0])
    second.update(id=999, name="Another provider edition", surah_list="18")
    payload["reciters"][0]["moshaf"].append(second)
    editions = parse_catalog(payload)[0].editions
    assert [edition.id for edition in editions] == [1, 999]
    assert editions[1].surahs == {18}


@pytest.mark.parametrize(
    "bad", [None, [], {}, {"reciters": []}, {"reciters": "bad"}, {"reciters": [{}]}]
)
def test_invalid_provider_top_level(bad):
    with pytest.raises(QuranFlowError):
        parse_catalog(bad)


@pytest.mark.parametrize(
    "key,value",
    [
        ("id", True),
        ("id", 0),
        ("name", ""),
        ("name", "escape\x1b[31m"),
        ("server", "https://evil.test/"),
        ("surah_list", "1,115"),
        ("surah_list", ""),
        ("surah_list", [1, 18]),
        ("surah_list", "1,chapter"),
    ],
)
def test_invalid_edition_fields(payload, key, value):
    payload["reciters"][0]["moshaf"][0][key] = value
    with pytest.raises(QuranFlowError):
        parse_catalog(payload)


def test_duplicate_provider_identity_rejected(payload):
    payload["reciters"].append(copy.deepcopy(payload["reciters"][0]))
    with pytest.raises(QuranFlowError):
        parse_catalog(payload)


def test_http_fetch_timeout_and_request_headers(tmp_path, payload, monkeypatch):
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr("quranflow.provider.urllib.request.build_opener", lambda _: opener)
    provider = Provider(tmp_path, timeout=2, retries=0)
    assert provider.catalog()[0].name == "Ibrahim Al-Akdar"
    request = opener.open.call_args.args[0]
    assert request.full_url == API_URL
    assert opener.open.call_args.kwargs["timeout"] == 2
    assert request.headers["Accept"] == "application/json"


def test_fresh_cache_avoids_network_and_is_private(tmp_path, payload, monkeypatch):
    provider = Provider(tmp_path / "cache")
    provider._write_cache(payload)
    monkeypatch.setattr(
        provider, "_fetch", Mock(side_effect=AssertionError("network should not run"))
    )
    assert len(provider.catalog()) == 2
    assert os.stat(provider.cache_file).st_mode & 0o777 == 0o600
    assert os.stat(provider.cache_dir).st_mode & 0o777 == 0o700


def test_refresh_bypasses_fresh_cache(tmp_path, payload, monkeypatch):
    provider = Provider(tmp_path)
    provider._write_cache(payload)
    fetch = Mock(return_value=payload)
    monkeypatch.setattr(provider, "_fetch", fetch)
    provider.catalog(refresh=True)
    fetch.assert_called_once()


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("timeout"), urllib.error.URLError("network unavailable"), ValueError("not JSON")],
)
def test_network_failure_is_bounded_and_actionable(tmp_path, monkeypatch, failure):
    provider = Provider(tmp_path, retries=1)
    fetch = Mock(side_effect=failure)
    monkeypatch.setattr(provider, "_fetch", fetch)
    monkeypatch.setattr("quranflow.provider.time.sleep", lambda _: None)
    with pytest.raises(QuranFlowError, match="network/DNS"):
        provider.catalog()
    assert fetch.call_count == 2


def test_validated_stale_cache_used_with_warning(tmp_path, payload, monkeypatch, caplog):
    provider = Provider(tmp_path, retries=0)
    provider.cache_file.write_text(
        json.dumps({"fetched_at": time.time() - 2 * 86400, "payload": payload})
    )
    monkeypatch.setattr(provider, "_fetch", Mock(side_effect=TimeoutError()))
    with caplog.at_level(logging.WARNING):
        assert len(provider.catalog()) == 2
    assert "validated cached" in caplog.text


@pytest.mark.parametrize("age", [31 * 86400, -3600, float("inf"), float("nan")])
def test_unusable_cache_timestamp(tmp_path, payload, monkeypatch, age):
    provider = Provider(tmp_path, retries=0)
    provider.cache_file.write_text(
        json.dumps({"fetched_at": time.time() - age, "payload": payload})
    )
    monkeypatch.setattr(provider, "_fetch", Mock(side_effect=TimeoutError()))
    with pytest.raises(QuranFlowError):
        provider.catalog()


def test_corrupt_cache_not_used(tmp_path, monkeypatch):
    provider = Provider(tmp_path, retries=0)
    provider.cache_file.write_text("not json")
    monkeypatch.setattr(provider, "_fetch", Mock(side_effect=TimeoutError()))
    with pytest.raises(QuranFlowError):
        provider.catalog()


def test_disabled_cache_leaves_no_files(tmp_path, payload, monkeypatch):
    provider = Provider(tmp_path / "unused", enabled=False)
    monkeypatch.setattr(provider, "_fetch", Mock(return_value=payload))
    provider.catalog()
    assert not provider.cache_dir.exists()


def test_oversized_response_rejected(tmp_path, monkeypatch):
    opener = Mock()
    opener.open.return_value = io.BytesIO(b"x" * (MAX_RESPONSE_BYTES + 1))
    monkeypatch.setattr("quranflow.provider.urllib.request.build_opener", lambda _: opener)
    with pytest.raises(QuranFlowError, match="safety limit"):
        Provider(tmp_path)._fetch()


@pytest.mark.parametrize(
    "url", ["http://www.mp3quran.net/api/v3/reciters", "https://evil.test/reciters"]
)
def test_untrusted_redirect_rejected(url):
    with pytest.raises(QuranFlowError, match="redirected"):
        _TrustedRedirect().redirect_request(None, None, 302, "redirect", {}, url)
