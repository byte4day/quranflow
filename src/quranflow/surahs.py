"""The complete chapter index, with conservative Unicode and spelling resolution."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from importlib.resources import files

from .errors import QuranFlowError


@dataclass(frozen=True, slots=True)
class Surah:
    id: int
    name: str
    arabic: str
    ayahs: int = 0


SURAH: tuple[Surah, ...] = tuple(
    Surah(**entry)
    for entry in json.loads(files("quranflow").joinpath("data/surahs.json").read_text("utf-8"))
)
SURAHS = SURAH


def normalize(text: str) -> str:
    """Ignore transliteration punctuation and Arabic vowel marks, not word identity."""
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = value.translate(
        str.maketrans({"ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ـ": ""})
    )
    value = re.sub(r"^(?:surah|sura|سورة)\s*", "", value)
    return "".join(c for c in value if c.isalnum())


# These transliterations are intentionally explicit. Provider spelling remains in data.
_EXTRA: dict[int, tuple[str, ...]] = {
    1: ("Al-Fatihah", "Fatiha", "Fatihah", "Al-Fatiha"),
    2: ("Al-Baqarah", "Baqara", "Baqarah"),
    3: ("Al-Imran", "Aal Imran", "Ali Imran"),
    4: ("An-Nisa", "Nisaa"),
    5: ("Al-Maidah", "Maida"),
    6: ("Al-Anam",),
    7: ("Al-Araf",),
    9: ("At-Taubah", "At-Tawbah", "Tawba", "Baraah"),
    11: ("Hood",),
    17: ("Al-Isra", "Bani Israil"),
    20: ("Ta Ha", "Taha"),
    21: ("Al-Anbiya",),
    23: ("Al-Muminun", "Al-Muminoon"),
    24: ("An-Nur",),
    26: ("Ash-Shuara",),
    29: ("Al-Ankabut",),
    30: ("Ar-Rum",),
    32: ("As-Sajdah",),
    35: ("Fatir",),
    36: ("Yasin", "Ya-Sin", "Ya Seen", "Yaseen"),
    37: ("As-Saffat",),
    38: ("Sad",),
    40: ("Al-Mumin",),
    44: ("Ad-Dukhan",),
    45: ("Al-Jathiyah",),
    50: ("Qaf",),
    51: ("Adh-Dhariyat", "Az-Zariyat"),
    55: ("Ar-Rahman", "Rahman"),
    56: ("Al-Waqiah", "Al-Waqia", "Waqiah"),
    58: ("Al-Mujadilah",),
    60: ("Al-Mumtahinah",),
    62: ("Al-Jumuah",),
    63: ("Al-Munafiqun",),
    69: ("Al-Haqqah",),
    70: ("Al-Maarij",),
    71: ("Nuh",),
    74: ("Al-Muddassir", "Al-Muddathir"),
    75: ("Al-Qiyamah",),
    76: ("Al-Insan", "Ad-Dahr"),
    79: ("An-Naziat",),
    85: ("Al-Buruj",),
    87: ("Al-Ala",),
    88: ("Al-Ghashiyah",),
    92: ("Al-Layl",),
    93: ("Ad-Duha",),
    94: ("Al-Inshirah",),
    98: ("Al-Bayyinah",),
    99: ("Az-Zalzalah",),
    100: ("Al-Adiyat",),
    101: ("Al-Qariah",),
    104: ("Al-Humazah",),
    106: ("Quraysh",),
    108: ("Al-Kauthar",),
    109: ("Al-Kafirun",),
    111: ("Al-Lahab",),
    112: ("Al-Ikhlas", "Ikhlas"),
    114: ("An-Nas", "Nas"),
}


def _index() -> dict[str, Surah]:
    result: dict[str, Surah] = {}
    for surah in SURAH:
        aliases = (surah.name, surah.arabic, *_EXTRA.get(surah.id, ()))
        for alias in aliases:
            key = normalize(alias)
            result[key] = surah
            # English articles may be omitted; retain Arabic articles for clarity.
            for prefix in ("al", "an", "ar", "as", "ash", "at", "adh", "ad", "az"):
                if alias.casefold().startswith(prefix + "-"):
                    result[normalize(alias[len(prefix) + 1 :])] = surah
    return result


_NAMES = _index()


def resolve_surah(query: str | int) -> Surah:
    text = str(query).strip()
    if not text:
        raise QuranFlowError("Specify a Surah number (1–114) or name.")
    if text.isdecimal():
        number = int(text)
        if 1 <= number <= 114:
            return SURAH[number - 1]
        raise QuranFlowError("Surah number must be between 1 and 114.")
    key = normalize(text)
    if key in _NAMES:
        return _NAMES[key]
    # Resolve only a clear close match, never empty/short or ambiguous fragments.
    if len(key) >= 4:
        ranked: dict[int, float] = {}
        for alias, surah in _NAMES.items():
            score = difflib.SequenceMatcher(None, key, alias).ratio()
            ranked[surah.id] = max(score, ranked.get(surah.id, 0))
        scores = sorted(ranked.items(), key=lambda item: item[1], reverse=True)
        if scores[0][1] >= 0.78 and scores[0][1] - scores[1][1] >= 0.08:
            return SURAH[scores[0][0] - 1]
    raise QuranFlowError(
        f"Unknown or ambiguous Surah '{text}'. Run play-quran surahs for the complete index."
    )
