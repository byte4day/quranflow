"""Small searchable selector: curses, with a line-input fallback."""

from __future__ import annotations

import os
import shutil
import sys
import unicodedata
from collections.abc import Callable, Sequence
from typing import TypeVar

from .errors import QuranFlowError

T = TypeVar("T")


def plain(text: object) -> str:
    """Do not let provider names inject terminal control sequences."""
    return "".join(c for c in str(text) if not unicodedata.category(c).startswith("C"))


def filter_items(items: Sequence[T], query: str, label: Callable[[T], str]) -> list[T]:
    from .reciters import Reciter, resolve_reciter
    from .surahs import Surah, normalize, resolve_surah

    # Identity-aware aliases take precedence: An-Nas must not become An-Nasr.
    if query.strip() and items:
        try:
            candidate = None
            if isinstance(items[0], Surah):
                candidate = resolve_surah(query)
            elif isinstance(items[0], Reciter):
                candidate = resolve_reciter(query, list(items))
            if candidate in items:
                return [item for item in items if item == candidate]
        except QuranFlowError:
            pass
    terms = [normalize(term) for term in query.split() if normalize(term)]
    return [item for item in items if all(term in normalize(label(item)) for term in terms)]


def select(
    title: str, items: Sequence[T], label: Callable[[T], str], preferred: T | None = None
) -> T:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise QuranFlowError(
            f"{title} requires a terminal. Specify --surah and --reciter; "
            "use surahs or reciters --json to discover choices."
        )
    if not items:
        raise QuranFlowError(f"No choices available for {title}.")
    ordered = list(items)
    if preferred in ordered:
        ordered.remove(preferred)
        ordered.insert(0, preferred)
    try:
        import curses
    except ImportError:
        return _line_select(title, ordered, label)
    try:
        if os.environ.get("TERM", "dumb") == "dumb":
            return _line_select(title, ordered, label)
        return curses.wrapper(lambda screen: _curses_select(screen, title, ordered, label))
    except curses.error:
        return _line_select(title, ordered, label)


def _line_select(title: str, items: list[T], label: Callable[[T], str]) -> T:
    query = ""
    while True:
        matches = filter_items(items, query, label)
        print(f"\n{title} — {len(matches)} matches")
        for index, item in enumerate(matches[:15], 1):
            print(f"  {index:2}. {plain(label(item))}")
        reply = input("Search, choose a displayed row number, or q to cancel: ").strip()
        if reply.casefold() in {"q", "quit"}:
            raise QuranFlowError("Selection cancelled.")
        if reply.isascii() and reply.isdigit() and 1 <= int(reply) <= min(15, len(matches)):
            return matches[int(reply) - 1]
        query = reply


def _curses_select(screen: object, title: str, items: list[T], label: Callable[[T], str]) -> T:
    import curses

    # curses' screen type is only available after importing the optional module.
    curses.curs_set(0)
    screen.keypad(True)
    query, selected = "", 0
    while True:
        matches = filter_items(items, query, label)
        selected = max(0, min(selected, len(matches) - 1))
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 6 or width < 20:
            raise curses.error("Terminal too small")
        screen.addnstr(0, 0, "QURANFLOW", width - 1, curses.A_BOLD)
        screen.addnstr(2, 0, plain(f"{title}  / {query}"), width - 1)
        rows = height - 6
        start = max(0, selected - rows + 1)
        for row, item in enumerate(matches[start : start + rows], 4):
            index = row - 4 + start
            text = plain(label(item))
            screen.addnstr(
                row, 0, text, width - 1, curses.A_REVERSE if index == selected else curses.A_NORMAL
            )
        if not matches:
            screen.addnstr(4, 0, "No matches — edit the search", width - 1)
        screen.addnstr(height - 1, 0, "Type to search · Up/Down · Enter · Esc cancels", width - 1)
        screen.refresh()
        key = screen.get_wch()
        if key in ("\n", "\r", curses.KEY_ENTER) and matches:
            return matches[selected]
        if key in ("\x1b", "\x03"):
            raise QuranFlowError("Selection cancelled.")
        if key == curses.KEY_UP:
            selected -= 1
        elif key == curses.KEY_DOWN:
            selected += 1
        elif key == curses.KEY_NPAGE:
            selected += rows
        elif key == curses.KEY_PPAGE:
            selected -= rows
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            query, selected = query[:-1], 0
        elif key == "\x15":
            query, selected = "", 0
        elif isinstance(key, str) and key.isprintable():
            query, selected = query + key, 0


def print_status(data: dict[str, object]) -> None:
    width = shutil.get_terminal_size((80, 24)).columns
    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    title = "\033[1mQURANFLOW\033[0m" if color else "QURANFLOW"
    print(f"\n{title}\n")
    track = data.get("track")
    lines = []
    if isinstance(track, dict):
        lines += [
            f"Surah:   {int(track['surah']):03d} — {track['name']} · {track['arabic']}",
            f"Reciter: {track['reciter']}",
            f"Edition: {track['edition']}",
        ]
    lines.append(f"Status:  {data.get('status', 'stopped')}")
    if data.get("volume") is not None:
        lines.append(f"Volume:  {data['volume']}%")
    if data.get("error"):
        lines.append(f"Error:   {data['error']}")
    for line in lines:
        print(plain(line)[: max(10, width)])
    print("\nControls: pause · resume · stop · volume · replay · change\n")
