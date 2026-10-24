"""Game of Thrones Quotes plugin for FiestaBoard.

Puts a quote from the Game of Thrones TV show on the board, word-wrapped and
centered, with the character who said it underneath. A new one on every
refresh, optionally only from the characters or houses you choose.

The quotes ship with the plugin in data.json: 196 of them from 48 characters,
each character with their house and the shorter names they go by. Only quotes
that fit the board are picked: a Note gets the short ones, a Flagship the long
ones too.
"""

import functools
import json
import logging
import pathlib
import random
import re
import threading
import unicodedata
from collections import deque
from dataclasses import dataclass
from typing import Any

from src.plugins.base import (
    Option,
    OptionsRequest,
    OptionsResult,
    OptionsUnavailable,
    PluginBase,
    PluginResult,
)

logger = logging.getLogger(__name__)

DATA_FILE = pathlib.Path(__file__).resolve().with_name("data.json")

# Quotes shown lately, across every board this process renders. When every
# quote that fits has been shown lately — a Note fits only a few dozen — the
# one shown longest ago comes next.
RECENT_SIZE = 50

# Board geometry assumed outside a board-scoped render (unit tests, the
# /plugins/{id}/data endpoint).
FALLBACK_WIDTH = 22
FALLBACK_HEIGHT = 6

ALIGNMENTS = ("center", "left")
DEFAULT_ALIGNMENT = "center"

# Characters the board can flap. Anything else is dropped rather than sent as a
# wrong tile. Reference: src/board_chars.py in FiestaBoard.
BOARD_CHARSET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !@#$()-+&=;:'\"%,./?")

# Typography the board has no tile for, mapped to the plain ASCII it does have.
TYPOGRAPHY = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "´": "'",
    "`": "'",
    "–": "-",
    "—": "-",
    "…": "...",
}

# Words that make a quote crude, for "Skip crude language". Matched anywhere
# in a word, so "fucker" and "horseshit" are caught too. "Bastard" is not on
# the list: in Westeros it is a station in life.
CRUDE = re.compile(r"fuck|shit|cunt|whore", re.IGNORECASE)

ELLIPSIS = "..."

# Upper bounds for the text variables, so a template line never receives an
# unbounded string.
QUOTE_MAX = 500
CHARACTER_MAX = 60
HOUSE_MAX = 60

# How well a quote fits a board, best last so ``max`` picks it.
OVERFLOW = 0  # longer than the board, shown cut off
BARE = 1  # fits, but the character's name does not fit with it
FULL = 2  # fits, name included (or the name is turned off)


class QuotesError(Exception):
    """data.json could not be read, or holds no usable quote."""


@dataclass(frozen=True)
class Quote:
    """One quote of the collection, in its original spelling."""

    id: int
    text: str
    character: str
    character_id: str
    # Shorter names the character goes by, longest first: "Ned Stark", "Ned".
    short_names: tuple[str, ...] = ()
    house: str = ""
    house_id: str = ""


@dataclass(frozen=True)
class Placement:
    """A quote laid out for one board, and how well it fit."""

    rows: list[str]
    fit: int
    # Rows of quote that did not make it onto the board; 0 unless OVERFLOW.
    spill: int = 0


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


def _choice(value: Any, choices: tuple[str, ...], default: str) -> str:
    """*value* if it is one of *choices*, otherwise *default*."""
    return value if value in choices else default


def parse_keys(value: Any) -> list[str] | None:
    """Character or house keys from the settings, ``None`` when unreadable.

    Missing or empty means "any".
    """
    if value is None or value == "":
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item.strip() for item in value if item.strip()]


# --------------------------------------------------------------------------
# The collection
# --------------------------------------------------------------------------


def _name(entry: Any) -> str:
    name = entry.get("name") if isinstance(entry, dict) else None
    return name.strip() if isinstance(name, str) else ""


def parse_collection(body: dict[str, Any]) -> list[Quote]:
    """The quotes of a data file, each with its character's names and house.

    A quote without text, or by a character the file does not list, is left
    out; a file with no usable quote at all is an error.
    """
    characters = body.get("characters") if isinstance(body.get("characters"), dict) else {}
    houses = body.get("houses") if isinstance(body.get("houses"), dict) else {}
    entries = body.get("quotes") if isinstance(body.get("quotes"), list) else []

    quotes = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        text = entry.get("text")
        character_id = entry.get("character")
        character = characters.get(character_id) if isinstance(character_id, str) else None
        if not isinstance(text, str) or not text.strip() or not _name(character):
            continue
        short_names = character.get("short_names")
        short_names = short_names if isinstance(short_names, list) else []
        house_id = character.get("house")
        house_id = house_id if isinstance(house_id, str) and _name(houses.get(house_id)) else ""
        quotes.append(
            Quote(
                id=index,
                text=text.strip(),
                character=_name(character),
                character_id=character_id,
                short_names=tuple(name.strip() for name in short_names if isinstance(name, str) and name.strip()),
                house=_name(houses.get(house_id)) if house_id else "",
                house_id=house_id,
            )
        )
    if not quotes:
        raise QuotesError("data.json holds no quotes")
    return quotes


@functools.cache
def load_quotes() -> list[Quote]:
    """The quotes in data.json, read once and shared by every board."""
    try:
        body = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise QuotesError(f"data.json could not be read: {error}") from error
    if not isinstance(body, dict):
        raise QuotesError("data.json is not a JSON object")
    return parse_collection(body)


def is_crude(quote: Quote) -> bool:
    return CRUDE.search(quote.text) is not None


_recent_lock = threading.Lock()
_recent: deque[int] = deque(maxlen=RECENT_SIZE)


def last_shown(quote: Quote) -> int:
    """How recently *quote* was shown: -1 for not lately, else larger is more recent."""
    with _recent_lock:
        return _recent.index(quote.id) if quote.id in _recent else -1


def remember_shown(quote: Quote) -> None:
    with _recent_lock:
        if quote.id in _recent:
            _recent.remove(quote.id)
        _recent.append(quote.id)


def clear_recent() -> None:
    """Forget which quotes were shown — for tests."""
    with _recent_lock:
        _recent.clear()


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def to_board_text(text: str) -> str:
    """Uppercase *text* and reduce it to characters the board can display.

    Accents are dropped (É → E), curly quotation marks and dashes turned into
    the board's own, and runs of whitespace collapsed to one space.
    """
    text = str(text)
    for source, replacement in TYPOGRAPHY.items():
        text = text.replace(source, replacement)
    text = "".join(char for char in unicodedata.normalize("NFKD", text.upper()) if not unicodedata.combining(char))
    text = "".join(char if char in BOARD_CHARSET else (" " if char.isspace() else "") for char in text)
    return " ".join(text.split())


def wrap(text: str, width: int) -> list[str]:
    """Break *text* into rows of at most *width* tiles, between words.

    A single word longer than a row is split where the row ends.
    """
    rows: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > width:
            if current:
                rows.append(current)
                current = ""
            rows.append(word[:width])
            word = word[width:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            rows.append(current)
            current = word
    if current:
        rows.append(current)
    return rows


def name_variants(name: str, short_names: tuple[str, ...] = ()) -> list[str]:
    """The character's name, then the shorter names they go by, longest first.

    The short names come from data.json, because no rule gets them right:
    Tyrion Lannister is "Tyrion", not "Lannister", which would not tell him
    from Cersei; Eddard Stark is "Ned Stark", then "Ned"; Sandor Clegane is
    "The Hound".
    """
    return list(dict.fromkeys(name for name in (name.strip(), *short_names) if name))


def name_line(name: str, short_names: tuple[str, ...], width: int) -> str:
    """``- TYRION LANNISTER``: the longest name that fits *width*, or ""."""
    for variant in name_variants(name, short_names):
        line = f"- {to_board_text(variant)}"
        if len(line) <= width:
            return line
    return ""


def truncate(rows: list[str], height: int, width: int) -> list[str]:
    """The first *height* rows, the last one ending in "..." to show there is more."""
    rows = rows[:height]
    if not rows:
        return rows
    last = rows[-1]
    if len(last) + len(ELLIPSIS) > width:
        cut = last[: width - len(ELLIPSIS)]
        # Prefer to end on a whole word.
        last = cut.rsplit(" ", 1)[0] if " " in cut else cut
    rows[-1] = last.rstrip(" ,;:-") + ELLIPSIS
    return rows


def align(text: str, width: int, alignment: str) -> str:
    """Pad *text* to exactly *width* tiles."""
    text = text[:width]
    if alignment == "center":
        padding = width - len(text)
        return " " * (padding // 2) + text + " " * (padding - padding // 2)
    if alignment == "right":
        return text.rjust(width)
    return text.ljust(width)


def place(quote: Quote, width: int, height: int, *, show_name: bool, alignment: str) -> Placement:
    """Lay *quote* out on a board of *width* x *height*.

    The quote is wrapped between words and the block centered vertically. The
    name goes on the row below, after a blank row when the board has one to
    spare — centered under a centered quote, flush right under a left one.
    """
    words = to_board_text(quote.text)
    text = wrap(words, width)
    if any(len(word) > width for word in words.split()) or len(text) > height:
        rows = _frame(truncate(text, height, width), [], width, height, alignment)
        return Placement(rows, OVERFLOW, spill=max(len(text) - height, 0))

    if not show_name:
        return Placement(_frame(text, [], width, height, alignment), FULL)
    signature = name_line(quote.character, quote.short_names, width)
    if not signature or len(text) + 1 > height:
        return Placement(_frame(text, [], width, height, alignment), BARE)
    return Placement(_frame(text, [signature], width, height, alignment), FULL)


def _frame(text: list[str], name: list[str], width: int, height: int, alignment: str) -> list[str]:
    """Quote rows and name rows as a full board, centered top to bottom."""
    rows = [align(row, width, alignment) for row in text]
    if name:
        if len(text) + 1 + len(name) <= height:
            rows.append(" " * width)
        name_alignment = "center" if alignment == "center" else "right"
        rows += [align(row, width, name_alignment) for row in name]
    top = (height - len(rows)) // 2
    blank = " " * width
    return [blank] * top + rows + [blank] * (height - top - len(rows))


def choose(
    quotes: list[Quote], width: int, height: int, *, show_name: bool, alignment: str, signed_only: bool = False
) -> tuple[Quote, Placement]:
    """A random quote that fits the board, not one shown lately.

    Every quote that fits is as likely as any other, whether or not its name
    fits with it — on a Note most leave no row for the name, and keeping only
    those that do would leave a few dozen. With *signed_only* that is what is
    kept, unless none of them has room for the name; then any that fits. When
    all of them were shown lately, the one shown longest ago comes next. When
    none fits at all, the one that overflows least is cut off with "...".
    """
    placed = [(quote, place(quote, width, height, show_name=show_name, alignment=alignment)) for quote in quotes]
    fitting = [pair for pair in placed if pair[1].fit > OVERFLOW]
    if signed_only:
        fitting = [pair for pair in fitting if pair[1].fit == FULL] or fitting
    if not fitting:
        return min(placed, key=lambda pair: (pair[1].spill, len(pair[0].text)))

    shown = {pair[0].id: last_shown(pair[0]) for pair in fitting}
    fresh = [pair for pair in fitting if shown[pair[0].id] < 0]
    if fresh:
        return random.choice(fresh)
    return min(fitting, key=lambda pair: shown[pair[0].id])


# --------------------------------------------------------------------------
# Plugin
# --------------------------------------------------------------------------


class GameOfThronesQuotesPlugin(PluginBase):
    """A random Game of Thrones quote, sized to fit the board."""

    @property
    def plugin_id(self) -> str:
        return "game_of_thrones_quotes"

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = self._validate_refresh_seconds(config)
        for key, label in (("characters", "Characters"), ("houses", "Houses")):
            if parse_keys(config.get(key)) is None:
                errors.append(f"{label} must be a list of names from the picker")
        return errors

    def _selection(self, quotes: list[Quote]) -> list[Quote]:
        """The quotes the settings allow: by the chosen characters or houses, crude ones left out if asked."""
        characters = set(parse_keys(self.config.get("characters")) or [])
        houses = set(parse_keys(self.config.get("houses")) or [])
        if characters or houses:
            quotes = [quote for quote in quotes if quote.character_id in characters or quote.house_id in houses]
        if self.config.get("skip_crude", False) is True:
            quotes = [quote for quote in quotes if not is_crude(quote)]
        return quotes

    def fetch_data(self) -> PluginResult:
        """Pick a quote that fits this board, and lay it out."""
        board = self.board
        width = board.width if board else FALLBACK_WIDTH
        height = board.height if board else FALLBACK_HEIGHT
        show_name = self.config.get("show_character", True) is not False
        alignment = _choice(self.config.get("alignment"), ALIGNMENTS, DEFAULT_ALIGNMENT)

        try:
            quotes = self._selection(load_quotes())
        except QuotesError as error:
            logger.warning("Game of Thrones quotes unavailable: %s", error)
            return PluginResult(available=False, error=str(error))
        except Exception as error:  # noqa: BLE001 — a bad payload must not break the render loop
            logger.exception("Unexpected error reading the Game of Thrones quotes")
            return PluginResult(available=False, error=str(error))
        if not quotes:
            return PluginResult(available=False, error="No quotes by the chosen characters or houses")

        signed_only = self.config.get("signed_only", False) is True
        quote, placement = choose(
            quotes, width, height, show_name=show_name, alignment=alignment, signed_only=signed_only
        )
        remember_shown(quote)
        lines = placement.rows

        data: dict[str, Any] = {
            "quote": to_board_text(quote.text)[:QUOTE_MAX],
            "character": to_board_text(quote.character)[:CHARACTER_MAX],
            "house": to_board_text(quote.house)[:HOUSE_MAX],
            # One variable that fills the whole board. FiestaBoard's template
            # engine splits a value on "\n" across board rows, so
            # `{{game_of_thrones_quotes.block}}` on the first template line
            # reproduces the layout without needing |wrap.
            "block": "\n".join(lines),
        }
        # line1..line6 mirror the same rows individually, at full board width:
        # the engine pads *around* what it is given, so a stripped row would be
        # indented twice on a centered line.
        for index in range(FALLBACK_HEIGHT):
            data[f"line{index + 1}"] = lines[index] if index < len(lines) else ""

        return PluginResult(available=True, data=data, formatted_lines=lines)

    def get_options(self, request: OptionsRequest) -> OptionsResult | list[Option]:
        """The character and house pickers, from data.json.

        Each option says how many quotes it brings; typing filters by any part
        of the name.
        """
        if request.options_id not in ("characters", "houses"):
            return super().get_options(request)
        try:
            quotes = load_quotes()
        except QuotesError as error:
            raise OptionsUnavailable(str(error)) from error

        counts: dict[str, list[Any]] = {}
        for quote in quotes:
            if request.options_id == "characters":
                key, label, description = quote.character_id, quote.character, quote.house
            elif quote.house_id:
                key, label, description = quote.house_id, quote.house, None
            else:
                continue
            counts.setdefault(key, [label, description, 0])[2] += 1

        query = request.query.strip().casefold()
        options = []
        for key, (label, description, count) in sorted(counts.items(), key=lambda item: item[1][0]):
            if query and query not in label.casefold():
                continue
            quotes_said = f"{count} quote" + ("" if count == 1 else "s")
            options.append(
                Option(
                    value=key,
                    label=label,
                    description=f"{description} · {quotes_said}" if description else quotes_said,
                )
            )
        return OptionsResult(options=options[: max(1, request.limit)], total=len(options))


# Export the plugin class
Plugin = GameOfThronesQuotesPlugin
