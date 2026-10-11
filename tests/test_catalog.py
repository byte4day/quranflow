"""Independent chapter facts and attribution-preserving reciter resolution."""

import pytest

from quranflow.errors import QuranFlowError
from quranflow.reciters import (
    Edition,
    Reciter,
    audio_url,
    available_reciters,
    resolve_reciter,
    validate_server,
)
from quranflow.surahs import SURAH, normalize, resolve_surah

EXPECTED_NAMES = """Al-Faatiha Al-Baqara Aal-i-Imraan An-Nisaa Al-Maaida Al-An'aam Al-A'raaf
Al-Anfaal At-Tawba Yunus Hud Yusuf Ar-Ra'd Ibrahim Al-Hijr An-Nahl Al-Israa Al-Kahf
Maryam Taa-Haa Al-Anbiyaa Al-Hajj Al-Muminoon An-Noor Al-Furqaan Ash-Shu'araa An-Naml
Al-Qasas Al-Ankaboot Ar-Room Luqman As-Sajda Al-Ahzaab Saba Faatir Yaseen As-Saaffaat
Saad Az-Zumar Ghafir Fussilat Ash-Shura Az-Zukhruf Ad-Dukhaan Al-Jaathiya Al-Ahqaf
Muhammad Al-Fath Al-Hujuraat Qaaf Adh-Dhaariyat At-Tur An-Najm Al-Qamar Ar-Rahmaan
Al-Waaqia Al-Hadid Al-Mujaadila Al-Hashr Al-Mumtahana As-Saff Al-Jumu'a Al-Munaafiqoon
At-Taghaabun At-Talaaq At-Tahrim Al-Mulk Al-Qalam Al-Haaqqa Al-Ma'aarij Nooh Al-Jinn
Al-Muzzammil Al-Muddaththir Al-Qiyaama Al-Insaan Al-Mursalaat An-Naba An-Naazi'aat Abasa
At-Takwir Al-Infitaar Al-Mutaffifin Al-Inshiqaaq Al-Burooj At-Taariq Al-A'laa Al-Ghaashiya
Al-Fajr Al-Balad Ash-Shams Al-Lail Ad-Dhuhaa Ash-Sharh At-Tin Al-Alaq Al-Qadr Al-Bayyina
Az-Zalzala Al-Aadiyaat Al-Qaari'a At-Takaathur Al-Asr Al-Humaza Al-Fil Quraish Al-Maa'un
Al-Kawthar Al-Kaafiroon An-Nasr Al-Masad Al-Ikhlaas Al-Falaq An-Naas""".split()

EXPECTED_ARABIC = """الفاتحة البقرة آل-عمران النساء المائدة الأنعام الأعراف الأنفال التوبة يونس هود يوسف
الرعد إبراهيم الحجر النحل الإسراء الكهف مريم طه الأنبياء الحج المؤمنون النور الفرقان الشعراء النمل القصص
العنكبوت الروم لقمان السجدة الأحزاب سبأ فاطر يس الصافات ص الزمر غافر فصلت الشورى الزخرف الدخان
الجاثية الأحقاف محمد الفتح الحجرات ق الذاريات الطور النجم القمر الرحمن الواقعة الحديد المجادلة الحشر
الممتحنة الصف الجمعة المنافقون التغابن الطلاق التحريم الملك القلم الحاقة المعارج نوح الجن المزمل المدثر
القيامة الإنسان المرسلات النبأ النازعات عبس التكوير الانفطار المطففين الانشقاق البروج الطارق الأعلى
الغاشية الفجر البلد الشمس الليل الضحى الشرح التين العلق القدر البينة الزلزلة العاديات القارعة التكاثر
العصر الهمزة الفيل قريش الماعون الكوثر الكافرون النصر المسد الإخلاص الفلق الناس""".split()

EXPECTED_AYAHS = [
    7,
    286,
    200,
    176,
    120,
    165,
    206,
    75,
    129,
    109,
    123,
    111,
    43,
    52,
    99,
    128,
    111,
    110,
    98,
    135,
    112,
    78,
    118,
    64,
    77,
    227,
    93,
    88,
    69,
    60,
    34,
    30,
    73,
    54,
    45,
    83,
    182,
    88,
    75,
    85,
    54,
    53,
    89,
    59,
    37,
    35,
    38,
    29,
    18,
    45,
    60,
    49,
    62,
    55,
    78,
    96,
    29,
    22,
    24,
    13,
    14,
    11,
    11,
    18,
    12,
    12,
    30,
    52,
    52,
    44,
    28,
    28,
    20,
    56,
    40,
    31,
    50,
    40,
    46,
    42,
    29,
    19,
    36,
    25,
    22,
    17,
    19,
    26,
    30,
    20,
    15,
    21,
    11,
    8,
    8,
    19,
    5,
    8,
    8,
    11,
    11,
    8,
    3,
    9,
    5,
    4,
    7,
    3,
    6,
    3,
    5,
    4,
    5,
    6,
]


def test_complete_independent_chapter_index():
    assert [s.id for s in SURAH] == list(range(1, 115))
    assert [s.name for s in SURAH] == EXPECTED_NAMES
    assert [normalize(s.arabic) for s in SURAH] == [normalize(s) for s in EXPECTED_ARABIC]
    assert [s.ayahs for s in SURAH] == EXPECTED_AYAHS
    assert sum(s.ayahs for s in SURAH) == 6236
    assert len({s.name for s in SURAH}) == 114


@pytest.mark.parametrize("number", range(1, 115))
def test_every_chapter_resolves_by_number_and_both_names(number):
    surah = SURAH[number - 1]
    assert resolve_surah(str(number)) == surah
    assert resolve_surah(f"{number:03d}") == surah
    assert resolve_surah(surah.name) == surah
    assert resolve_surah(surah.arabic) == surah


@pytest.mark.parametrize(
    "query,number",
    [
        ("yasin", 36),
        ("Ya-Sin", 36),
        ("Yaseen", 36),
        ("سورة يس", 36),
        ("Al-Fatihah", 1),
        ("Al-Baqarah", 2),
        ("Ar-Rahman", 55),
        ("al-kahf", 18),
        ("Al-Mulk", 67),
        ("Al-Waqiah", 56),
        ("Al-Ikhlas", 112),
        ("An-Nas", 114),
        ("الكهف", 18),
        ("الإخلاص", 112),
        ("kahff", 18),
        ("rahmaan", 55),
        ("surah baqarah", 2),
        ("Aal Imran", 3),
        ("Al-Lahab", 111),
    ],
)
def test_chapter_aliases_and_fuzzy_resolution(query, number):
    assert resolve_surah(query).id == number


@pytest.mark.parametrize("query", ["", " ", "0", "115", "-1", "this-is-not-a-surah", "a", "18.mp3"])
def test_invalid_surah(query):
    with pytest.raises(QuranFlowError):
        resolve_surah(query)


def reciter(name, identifier=9001, chapters=frozenset({1, 18, 36})):
    # IDs here are synthetic; only production API data establishes actual provider IDs.
    return Reciter(
        identifier,
        name,
        (
            Edition(
                9002,
                "Rewayat Hafs A'n Assem - Murattal",
                "https://server6.mp3quran.net/example/",
                chapters,
            ),
        ),
    )


@pytest.mark.parametrize(
    "alias",
    ["Yasir", "Yasser", "Dosari", "Dossary", "Al-Dosari", "Yasir Al Dosari", "Yasser Al Dossary"],
)
def test_dosari_aliases_never_select_other_dosaris(alias):
    requested = reciter("Yasser Al-Dosari")
    catalog = [reciter("Sami Al-Dosari", 9003), reciter("Ibrahim Aldosari", 9004), requested]
    assert resolve_reciter(alias, catalog) is requested


@pytest.mark.parametrize(
    "name,alias",
    [
        ("Mishary Alafasi", "Mishary Rashid Alafasy"),
        ("Abdulrahman Alsudaes", "Abdul Rahman Al Sudais"),
        ("Maher Al Meaqli", "Maher Al Muaiqly"),
        ("Abdulbasit Abdulsamad", "Abdul Basit Abdul Samad"),
        ("Saad Al-Ghamdi", "ghamdi"),
        ("Mohammed Siddiq Al-Minshawi", "Muhammad Siddiq Al-Minshawi"),
        ("Mahmoud Khalil Al-Hussary", "Mahmoud Khalil Al Husary"),
        ("Shaik Abu Bakr Al Shatri", "Abu Bakr Al-Shatri"),
        ("Nasser Alqatami", "Nasser Al-Qatami"),
        ("Idrees Abkr", "Idris Abkar"),
    ],
)
def test_prioritized_reciter_aliases(name, alias):
    requested = reciter(name)
    assert resolve_reciter(alias, [requested]) is requested


def test_missing_voice_and_typo_do_not_silently_substitute():
    with pytest.raises(QuranFlowError, match="No different voice"):
        resolve_reciter("dosari", [reciter("Sami Al-Dosari")])
    with pytest.raises(QuranFlowError, match="No different voice"):
        resolve_reciter("Yaserr Al-Dosari", [reciter("Yasser Al-Dosari")])


def test_reciter_ambiguous_partial_name_requires_identity():
    catalog = [reciter("Khalid Al-Jileel", 9001), reciter("Khalid Al-Wehabi", 9003)]
    with pytest.raises(QuranFlowError, match="Ambiguous"):
        resolve_reciter("Khalid", catalog)
    assert resolve_reciter("9003", catalog).name == "Khalid Al-Wehabi"


def test_recording_availability_and_zero_padding():
    requested = reciter("Yasser Al-Dosari")
    assert audio_url(requested.editions[0], 36) == "https://server6.mp3quran.net/example/036.mp3"
    with pytest.raises(QuranFlowError, match="unavailable"):
        audio_url(requested.editions[0], 2)
    assert available_reciters([requested, reciter("Other", 9003, frozenset({2}))], 36) == [
        requested
    ]


@pytest.mark.parametrize(
    "server",
    [
        "http://server6.mp3quran.net/voice/",
        "https://mp3quran.net.evil.test/voice/",
        "https://evilmp3quran.net/voice/",
        "https://user:password@server6.mp3quran.net/voice/",
        "https://server6.mp3quran.net:8443/voice/",
        "https://server6.mp3quran.net/voice/?q=1",
        "https://server6.mp3quran.net/voice/#a",
        "https://server6.mp3quran.net/../voice/",
        "https://server6.mp3quran.net/%2e%2e/voice/",
        "https://server6.mp3quran.net/voice/\n",
    ],
)
def test_untrusted_recording_servers_rejected(server):
    with pytest.raises(QuranFlowError):
        validate_server(server)


@pytest.mark.parametrize("number", [0, 115, -1, True, "36", 36.0])
def test_audio_url_invalid_chapter(number):
    with pytest.raises(QuranFlowError):
        audio_url(reciter("Example").editions[0], number)
