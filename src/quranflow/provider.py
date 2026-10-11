"""MP3Quran API v3 catalog, bounded HTTPS requests, and private metadata cache."""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .errors import QuranFlowError
from .reciters import Edition, Reciter, validate_server

API_URL = "https://www.mp3quran.net/api/v3/reciters?language=eng"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_STALE_SECONDS = 30 * 86400
LOGGER = logging.getLogger(__name__)


def _positive_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("invalid ID")
    number = int(value)
    if number <= 0:
        raise ValueError("invalid ID")
    return number


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise ValueError("invalid name")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("unsafe name")
    return value.strip()


def parse_catalog(payload: Any) -> list[Reciter]:
    """Preserve provider IDs and recording availability; reject malformed metadata."""
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get("reciters"), list):
            raise ValueError("missing reciters array")
        result = []
        seen: set[int] = set()
        for raw in payload["reciters"]:
            identifier = _positive_id(raw["id"])
            if identifier in seen:
                raise ValueError("duplicate reciter ID")
            seen.add(identifier)
            editions = []
            edition_ids: set[int] = set()
            if not isinstance(raw["moshaf"], list):
                raise ValueError("missing moshaf array")
            for item in raw["moshaf"]:
                edition_id = _positive_id(item["id"])
                if edition_id in edition_ids:
                    raise ValueError("duplicate edition ID")
                edition_ids.add(edition_id)
                if not isinstance(item["surah_list"], str):
                    raise ValueError("invalid availability list")
                chapters = frozenset(
                    int(s.strip()) for s in item["surah_list"].split(",") if s.strip()
                )
                if not chapters or any(not 1 <= number <= 114 for number in chapters):
                    raise ValueError("invalid chapter availability")
                # surah_list is authoritative; documentation examples occasionally truncate it.
                editions.append(
                    Edition(
                        edition_id, _name(item["name"]), validate_server(item["server"]), chapters
                    )
                )
            if editions:
                result.append(Reciter(identifier, _name(raw["name"]), tuple(editions)))
        if not result:
            raise ValueError("no available recording editions")
        return result
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise QuranFlowError(
            "MP3Quran returned an invalid reciter catalog. Try again later with play-quran reciters --refresh."
        ) from exc


class _TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        # API redirects may move between the root and www; never follow an unrelated host.
        from urllib.parse import urlsplit

        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname not in {"mp3quran.net", "www.mp3quran.net"}:
            raise QuranFlowError(
                "The catalog request redirected outside the trusted HTTPS provider."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Provider:
    def __init__(
        self,
        cache_dir: Path,
        ttl_hours: int = 24,
        enabled: bool = True,
        *,
        timeout: float = 8.0,
        retries: int = 1,
    ):
        if not 1 <= ttl_hours <= 720 or not 0 < timeout <= 30 or not 0 <= retries <= 2:
            raise QuranFlowError("Invalid provider cache, timeout, or retry setting.")
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "mp3quran-v3-eng.json"
        self.ttl_hours = ttl_hours
        self.enabled = enabled
        self.timeout = timeout
        self.retries = retries

    def _read_cache(self) -> tuple[list[Reciter], float] | None:
        if not self.enabled:
            return None
        try:
            if self.cache_file.stat().st_size > MAX_RESPONSE_BYTES:
                return None
            envelope = json.loads(self.cache_file.read_text("utf-8"))
            timestamp = float(envelope["fetched_at"])
            age = time.time() - timestamp
            if not math.isfinite(timestamp) or age < -60 or age > MAX_STALE_SECONDS:
                return None
            return parse_catalog(envelope["payload"]), max(0.0, age)
        except (OSError, ValueError, KeyError, TypeError, QuranFlowError):
            return None

    def _write_cache(self, payload: Any) -> None:
        if not self.enabled:
            return
        temporary: str | None = None
        try:
            self.cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.cache_dir, 0o700)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.cache_dir, prefix=".catalog-", delete=False
            ) as handle:
                temporary = handle.name
                json.dump(
                    {"fetched_at": time.time(), "payload": payload}, handle, ensure_ascii=False
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.cache_file)
        except OSError as exc:
            LOGGER.warning("Metadata cache could not be written: %s", exc)
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def _fetch(self) -> Any:
        request = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": "QuranFlow/0.1 (+https://mp3quran.net/ar/api)",
                "Accept": "application/json",
            },
        )
        opener = urllib.request.build_opener(_TrustedRedirect())
        with opener.open(request, timeout=self.timeout) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise QuranFlowError("The provider metadata response exceeded the safety limit.")
        return json.loads(content)

    def catalog(self, refresh: bool = False) -> list[Reciter]:
        cached = self._read_cache()
        if cached is not None and not refresh and cached[1] < self.ttl_hours * 3600:
            return cached[0]
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                payload = self._fetch()
                result = parse_catalog(payload)
                self._write_cache(payload)
                return result
            except (OSError, urllib.error.URLError, ValueError, QuranFlowError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
        if cached is not None:
            LOGGER.warning(
                "Provider unavailable; using validated cached reciter metadata (%.1f hours old).",
                cached[1] / 3600,
            )
            return cached[0]
        raise QuranFlowError(
            "Cannot load the MP3Quran reciter catalog. Check your network/DNS connection and retry; no usable metadata cache is available."
        ) from last_error
