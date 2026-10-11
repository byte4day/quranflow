"""Provider-backed reciter identity and recording edition selection."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from .errors import QuranFlowError
from .surahs import normalize


@dataclass(frozen=True, slots=True)
class Edition:
    id: int
    name: str
    server: str
    surahs: frozenset[int]


@dataclass(frozen=True, slots=True)
class Reciter:
    id: int
    name: str
    editions: tuple[Edition, ...]


# Exact provider display names anchor aliases: never guess an ID or substitute another voice.
_ALIASES: dict[str, tuple[str, ...]] = {
    "Yasser Al-Dosari": (
        "dosari",
        "dossary",
        "al-dosari",
        "al-dossary",
        "yasir",
        "yasser",
        "yassir",
        "yasir al dosari",
        "yasser al dossary",
        "yasser al dossari",
    ),
    "Mishary Alafasi": (
        "alafasy",
        "mishary",
        "mishari",
        "mishary rashid alafasy",
        "mishari rashid al afasy",
    ),
    "Abdulrahman Alsudaes": (
        "sudais",
        "alsudais",
        "abdul rahman al sudais",
        "abdurrahman as sudais",
    ),
    "Maher Al Meaqli": ("maher", "muaiqly", "maher al muaiqly", "maher al muaikli"),
    "Abdulbasit Abdulsamad": (
        "abdul basit",
        "abdulbasit",
        "abdul basit abdul samad",
        "abdul basit abdus samad",
    ),
    "Saad Al-Ghamdi": ("ghamdi", "saad", "saad al ghamidi"),
    "Mohammed Siddiq Al-Minshawi": (
        "minshawi",
        "muhammad siddiq al minshawi",
        "mohamed siddiq al minshawi",
    ),
    "Mahmoud Khalil Al-Hussary": ("husary", "hussary", "hosary", "mahmoud khalil al husary"),
    "Shaik Abu Bakr Al Shatri": ("shatri", "abu bakr al shatri", "abubakr shatri"),
    "Nasser Alqatami": ("qatami", "nasser al qatami", "nasir al qatami"),
    "Idrees Abkr": ("idris", "abkar", "idris abkar", "idrees abkar"),
}


def resolve_reciter(query: str | int, catalog: list[Reciter]) -> Reciter:
    text = str(query).strip()
    key = normalize(text)
    if not key:
        raise QuranFlowError("Specify a reciter name or provider ID.")
    exact = [r for r in catalog if str(r.id) == text or normalize(r.name) == key]
    aliases = {
        normalize(name): {normalize(alias) for alias in variants}
        for name, variants in _ALIASES.items()
    }
    if not exact:
        exact = [r for r in catalog if key in aliases.get(normalize(r.name), set())]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise QuranFlowError(
            f"Ambiguous reciter '{text}'; select a provider ID: "
            + ", ".join(f"{r.id} ({r.name})" for r in exact)
        )
    if any(key in variants for variants in aliases.values()):
        raise QuranFlowError(
            f"The requested reciter '{text}' is unavailable in the provider catalog. "
            "Run play-quran reciters to choose an available voice. No different voice was selected."
        )
    # Substring matching is safe only when a complete token sequence identifies one voice.
    words = text.casefold().replace("-", " ").split()
    matches = [
        r
        for r in catalog
        if len(key) >= 4
        and words
        and all(word in r.name.casefold().replace("-", " ").split() for word in words)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise QuranFlowError(
            f"Ambiguous reciter '{text}': " + ", ".join(f"{r.name} (ID {r.id})" for r in matches)
        )
    suggestions = sorted(
        catalog,
        key=lambda r: difflib.SequenceMatcher(None, key, normalize(r.name)).ratio(),
        reverse=True,
    )[:3]
    hint = "; closest names: " + ", ".join(r.name for r in suggestions) if suggestions else ""
    raise QuranFlowError(
        f"Reciter '{text}' is unavailable or unrecognized{hint}. Run play-quran reciters. No different voice was selected."
    )


def validate_server(server: str) -> str:
    if not isinstance(server, str):
        raise QuranFlowError("Recording server must be an HTTPS URL.")
    try:
        parts = urlsplit(server)
        trusted = parts.hostname == "mp3quran.net" or (parts.hostname or "").endswith(
            ".mp3quran.net"
        )
        decoded = unquote(parts.path)
        safe = (
            parts.scheme == "https"
            and trusted
            and parts.port in (None, 443)
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
            and "\\" not in decoded
            and ".." not in decoded.split("/")
            and not any(ord(c) < 32 or ord(c) == 127 for c in server)
        )
    except ValueError as exc:
        raise QuranFlowError("Invalid recording server URL.") from exc
    if not safe:
        raise QuranFlowError(
            "Recording server must use HTTPS on mp3quran.net or a trusted mp3quran.net subdomain."
        )
    return server.rstrip("/") + "/"


def audio_url(edition: Edition, surah_id: int) -> str:
    if isinstance(surah_id, bool) or not isinstance(surah_id, int) or not 1 <= surah_id <= 114:
        raise QuranFlowError("Surah number must be between 1 and 114.")
    if surah_id not in edition.surahs:
        raise QuranFlowError(
            f"Surah {surah_id} is unavailable in edition '{edition.name}'. Choose another available edition or reciter."
        )
    return validate_server(edition.server) + f"{surah_id:03d}.mp3"


def available_reciters(catalog: list[Reciter], surah_id: int) -> list[Reciter]:
    return [
        reciter
        for reciter in catalog
        if any(surah_id in edition.surahs for edition in reciter.editions)
    ]


def prioritize_reciters(catalog: list[Reciter]) -> list[Reciter]:
    """Put the requested common voices first while preserving provider display names."""
    priorities = {normalize(name): index for index, name in enumerate(_ALIASES)}
    return sorted(
        catalog,
        key=lambda reciter: (
            priorities.get(normalize(reciter.name), len(priorities)),
            reciter.name.casefold(),
        ),
    )
