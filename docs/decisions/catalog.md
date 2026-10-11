# Catalog and attribution evidence

Checked 2026-10-11 against official documentation and live metadata:

- [MP3Quran API v3 documentation](https://www.mp3quran.net/ar/api):
  `reciters?language=eng` returns reciter IDs/names and `moshaf` editions with
  `id`, `name`, `server`, and `surah_list`. The availability list determines
  which chapters can be requested. URLs use the supplied HTTPS recording
  server followed by a three-digit chapter filename, for example `036.mp3`.
- [MP3Quran's English reciter index](https://www.mp3quran.net/eng/reciters)
  supplies the exact display names used to anchor alternative spellings.
  [Yasser Al-Dosari's official page](https://www.mp3quran.net/eng/yasser)
  independently confirms his identity and chapter catalog. No numeric reciter
  ID or recording server is guessed: playback always requires API metadata.
- [AlQuran Cloud v1 chapter metadata](https://api.alquran.cloud/v1/surah)
  supplied all 114 chapter numbers, English transliterations, Arabic names,
  and verse counts in `src/quranflow/data/surahs.json`. These factual index
  fields were retrieved through the web documentation tool. Runtime chapter
  selection requires no network access.
- [AlQuran Cloud API](https://alquran.cloud/api) was investigated as a second
  audio source. This release deliberately provides no automatic audio fallback:
  its edition/ayah audio model does not establish identity equivalence with every
  MP3Quran chapter recording. A failure never switches the requested voice.

The runtime API integration uses Python 3.11+ `urllib.request`, an eight-second
connection/socket timeout, one bounded retry, and a 5 MiB metadata limit.
Validated cached metadata expires after 24 hours by default; on provider failure
it can be used for up to 30 days with a warning. Recording hosts must be HTTPS
under `mp3quran.net`, with no credentials, query, fragment, or alternate port.
API redirects are restricted to the root and `www` provider hosts.

Local network access was unavailable in the development sandbox (DNS resolution
failed), and the web tool could not retrieve the live MP3Quran catalog endpoint.
The parser/network paths therefore use offline fixtures and mocks; those tests
are not represented as a live audio or API integration check. The factual
AlQuran Cloud index and MP3Quran documentation/reciter pages were accessible.

No audio is bundled or downloaded by this module. The repository's MIT license
applies to original source code, not third-party recordings. MP3Quran supplies
the recordings and reciter attribution; consult the provider for reuse rights.
