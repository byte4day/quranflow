import pytest

from quranflow.reciters import Reciter
from quranflow.surahs import SURAH
from quranflow.ui import filter_items, plain


def test_menu_search_arabic_and_latin():
    def label(s):
        return f"{s.id:03d} {s.name} {s.arabic}"

    assert [s.id for s in filter_items(SURAH, "kahf", label)] == [18]
    assert [s.id for s in filter_items(SURAH, "الكهف", label)] == [18]
    assert [s.id for s in filter_items(SURAH, "036", label)] == [36]


def test_terminal_controls_removed():
    assert "\x1b" not in plain("provider\x1b[31mname")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("yasin", 36),
        ("Ya-Sin", 36),
        ("Al-Fatihah", 1),
        ("Al-Ikhlas", 112),
        ("Al-Waqiah", 56),
        ("An-Nas", 114),
        ("kahf 18", 18),
        ("18 kahf", 18),
    ],
)
def test_search_aliases_identity_and_tokens(query, expected):
    assert [
        s.id for s in filter_items(SURAH, query, lambda s: f"{s.id:03d} {s.name} {s.arabic}")
    ] == [expected]


@pytest.mark.parametrize(
    ("query", "name"),
    [
        ("alafasy", "Mishary Alafasi"),
        ("sudais", "Abdulrahman Alsudaes"),
        ("muaiqly", "Maher Al Meaqli"),
        ("idris abkar", "Idrees Abkr"),
    ],
)
def test_reciter_menu_aliases(query, name):
    reciter = Reciter(1, name, ())
    assert filter_items([reciter], query, lambda r: r.name) == [reciter]
