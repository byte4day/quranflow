"""One command surface for terminal, Codex and Cursor."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from typing import Any

from . import __version__
from .config import Config, Paths, Settings, validate
from .errors import QuranFlowError
from .playback import Player
from .provider import Provider
from .reciters import audio_url, prioritize_reciters, resolve_reciter
from .surahs import SURAH, resolve_surah
from .ui import plain, print_status, select

COMMANDS = {
    "play",
    "pause",
    "resume",
    "stop",
    "status",
    "volume",
    "replay",
    "change",
    "reciters",
    "surahs",
    "config",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="play-quran",
        description="Qur'an recitation in the background with mpv.",
        epilog="No selection? A searchable menu opens in a terminal. Agents should specify choices.",
    )
    result.add_argument(
        "action", nargs="?", default="", help="Surah name/number or control command"
    )
    result.add_argument("values", nargs="*", help="command arguments (e.g. config set volume 65)")
    result.add_argument("--surah", help="Surah number, English/Arabic name, or alias")
    result.add_argument("--reciter", help="Provider reciter ID, name, or known alias")
    result.add_argument("--edition", type=int, help="Provider recording edition (moshaf) ID")
    result.add_argument("--volume", type=int, help="Starting volume, 0–100")
    result.add_argument(
        "--autoplay",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Queue subsequent Surahs available in the selected edition",
    )
    result.add_argument(
        "--last", action="store_true", help="Reuse remembered Surah/reciter/edition"
    )
    result.add_argument("--refresh", action="store_true", help="Refresh provider metadata")
    result.add_argument("--json", action="store_true", help="Machine-readable output")
    result.add_argument("--debug", action="store_true", help="Enable diagnostic logging to stderr")
    result.add_argument("--version", action="version", version=f"QuranFlow {__version__}")
    return result


def emit(data: Any, json_mode: bool, *, status: bool = False) -> None:
    if json_mode:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif status:
        print_status(data)
    elif isinstance(data, list):
        for row in data:
            if "arabic" in row:
                print(plain(f"{row['id']:03d}  {row['name']} · {row['arabic']}"))
            else:
                editions = "; ".join(
                    f"{e['id']}: {e['name']} ({len(e['surahs'])} Surahs)" for e in row["editions"]
                )
                print(plain(f"{row['id']:3d}  {row['name']} — {editions}"))
    else:
        for key, value in data.items():
            print(plain(f"{key}: {value}"))


def catalog_json(catalog: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "name": r.name,
            "editions": [
                {"id": e.id, "name": e.name, "surahs": sorted(e.surahs)} for e in r.editions
            ],
        }
        for r in catalog
    ]


def _provider(paths: Paths, settings: Settings) -> Provider:
    return Provider(paths.cache, ttl_hours=settings.cache_ttl_hours, enabled=settings.cache_enabled)


def _config(args: argparse.Namespace, config: Config, paths: Paths) -> dict[str, Any]:
    if not args.values:
        return asdict(config.load())
    if len(args.values) != 3 or args.values[0] != "set":
        raise QuranFlowError("Usage: play-quran config [set KEY VALUE]")
    _, key, value = args.values
    validate(key, value)
    if key == "default_reciter" and value:
        # Resolve first so a typo never becomes a silently substituted reciter.
        value = str(resolve_reciter(value, _provider(paths, config.load()).catalog()).id)
    if key == "default_reciter" and value != config.load().default_reciter:
        return asdict(config.update(default_reciter=value, last_edition=0))
    return asdict(config.update(**{key: value}))


def _play(args: argparse.Namespace, config: Config, paths: Paths) -> dict[str, Any]:
    settings = config.load()
    volume = settings.volume if args.volume is None else int(validate("volume", args.volume))
    if args.edition is not None and args.edition < 1:
        raise QuranFlowError("--edition must be a positive provider recording ID.")
    positional = " ".join(
        ([args.action] if args.action not in COMMANDS and args.action else []) + args.values
    ).strip()
    if args.surah and positional:
        raise QuranFlowError("Select a Surah by positional name or --surah, not both.")
    previous = Player(paths.runtime).status() if args.action == "change" else {}
    current = previous.get("track") or {}
    surah_query = args.surah or positional
    if not surah_query and (args.last or args.action == "change"):
        surah_query = str(current.get("surah", settings.last_surah))
    if surah_query:
        surah = resolve_surah(surah_query)
    else:
        surah = select(
            "Choose a Surah",
            SURAH,
            lambda s: (
                f"{s.id:03d}  {s.arabic} · {s.name}"
                if settings.language == "ar"
                else f"{s.id:03d}  {s.name} · {s.arabic}"
            ),
            resolve_surah(str(settings.last_surah)),
        )
    catalog = prioritize_reciters(_provider(paths, settings).catalog(refresh=args.refresh))
    query = args.reciter
    if not query and (args.last or args.action == "change"):
        query = str(current.get("reciter_id") or settings.default_reciter)
    if query:
        reciter = resolve_reciter(query, catalog)
    else:
        preferred = next((r for r in catalog if str(r.id) == settings.default_reciter), None)
        # Only offer reciters that actually have this recording, with remembered choice first.
        available = [r for r in catalog if any(surah.id in e.surahs for e in r.editions)]
        reciter = select("Choose a reciter", available, lambda r: f"{r.id:3d}  {r.name}", preferred)
    editions = [e for e in reciter.editions if surah.id in e.surahs]
    if not editions:
        alternatives = [r.name for r in catalog if any(surah.id in e.surahs for e in r.editions)][
            :8
        ]
        raise QuranFlowError(
            f"{reciter.name} has no recording of {surah.name}. "
            f"Available alternatives: {', '.join(alternatives) or 'none'}. "
            "Choose another --reciter explicitly."
        )
    edition_id = args.edition
    if edition_id is None and not args.reciter and (args.last or args.action == "change"):
        edition_id = int(current.get("edition_id", settings.last_edition)) or None
    if edition_id is not None:
        edition = next((e for e in editions if e.id == edition_id), None)
        if edition is None:
            raise QuranFlowError(
                f"Edition {edition_id} is unavailable for this reciter/Surah. "
                f"Available edition IDs: {', '.join(str(e.id) for e in editions)}"
            )
    elif len(editions) == 1:
        edition = editions[0]
    else:
        edition = select(
            "Choose a recording edition",
            editions,
            lambda e: f"{e.id}  {e.name} ({len(e.surahs)} Surahs)",
            next((e for e in editions if e.id == settings.last_edition), None),
        )
    autoplay = settings.autoplay if args.autoplay is None else args.autoplay
    surah_ids = [surah.id]
    if autoplay:
        surah_ids += sorted(i for i in edition.surahs if i > surah.id)
    tracks = []
    for number in surah_ids:
        chapter = resolve_surah(str(number))
        tracks.append(
            {
                "surah": chapter.id,
                "name": chapter.name,
                "arabic": chapter.arabic,
                "reciter": reciter.name,
                "reciter_id": reciter.id,
                "edition": edition.name,
                "edition_id": edition.id,
                "url": audio_url(edition, number),
            }
        )
    result = Player(paths.runtime).play(tracks, volume=volume)
    config.update(last_surah=surah.id, default_reciter=str(reciter.id), last_edition=edition.id)
    return result


def run(args: argparse.Namespace) -> None:
    paths = Paths.discover()
    config = Config(paths.config)
    action = args.action
    if action in {
        "surahs",
        "reciters",
        "config",
        "pause",
        "resume",
        "stop",
        "status",
        "replay",
        "volume",
    }:
        if any(
            (
                args.volume is not None,
                args.autoplay is not None,
                args.last,
                args.edition is not None,
            )
        ):
            raise QuranFlowError(f"Playback options are not accepted by {action}.")
        if action not in {"reciters"} and any((args.surah, args.reciter)):
            raise QuranFlowError(f"Selection options are not accepted by {action}.")
        if action not in {"reciters"} and args.refresh:
            raise QuranFlowError(f"--refresh is not accepted by {action}.")
    if action == "surahs":
        if args.values:
            raise QuranFlowError("Usage: play-quran surahs [--json]")
        emit([{"id": s.id, "name": s.name, "arabic": s.arabic} for s in SURAH], args.json)
    elif action == "reciters":
        settings = config.load()
        catalog = _provider(paths, settings).catalog(refresh=args.refresh)
        if args.reciter:
            catalog = [resolve_reciter(args.reciter, catalog)]
        if args.surah:
            number = resolve_surah(args.surah).id
            catalog = [r for r in catalog if any(number in e.surahs for e in r.editions)]
        if args.values:
            raise QuranFlowError("Usage: play-quran reciters [--surah N] [--reciter NAME] [--json]")
        emit(catalog_json(catalog), args.json)
    elif action == "config":
        emit(_config(args, config, paths), args.json)
    elif action in {"pause", "resume", "stop", "status", "replay", "volume"}:
        player = Player(paths.runtime)
        if action == "volume":
            if len(args.values) != 1:
                raise QuranFlowError("Usage: play-quran volume 0–100")
            value = int(validate("volume", args.values[0]))
            data = player.set_volume(value)
            config.update(volume=value)
        else:
            if args.values or any((args.surah, args.reciter, args.edition, args.last)):
                raise QuranFlowError(f"Unexpected selection arguments for {action}.")
            data = getattr(player, action)()
        emit(data, args.json, status=True)
    else:
        emit(_play(args, config, paths), args.json, status=True)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        run(args)
    except (QuranFlowError, OSError, EOFError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
        else:
            print(f"QuranFlow: {plain(exc)}", file=sys.stderr)
        if args.debug:
            logging.exception("Command failed")
        return 1
    except KeyboardInterrupt:
        print("\nQuranFlow: Selection cancelled.", file=sys.stderr)
        return 130
    return 0
