"""Shared fixtures for the Game of Thrones Quotes plugin tests.

The plugin tests run on a small hand-built collection in quotes.json's shape,
not on the real file, so a change to the quotes never breaks a test of the
layout. The real file has tests of its own.
"""

import json
import pathlib

import pytest

from plugins import game_of_thrones_quotes as got
from plugins.game_of_thrones_quotes import GameOfThronesQuotesPlugin

MANIFEST = json.loads((pathlib.Path(__file__).resolve().parent.parent / "manifest.json").read_text())

HOUSES = {
    "stark": {"name": "House Stark of Winterfell"},
    "lannister": {"name": "House Lannister of Casterly Rock"},
    "clegane": {"name": "House Clegane of Clegane's Keep"},
}

CHARACTERS = {
    "ned": {"name": "Eddard Stark", "short_names": ["Ned Stark", "Ned"], "house": "stark"},
    "arya": {"name": "Arya Stark", "short_names": ["Arya"], "house": "stark"},
    "tyrion": {"name": "Tyrion Lannister", "short_names": ["Tyrion"], "house": "lannister"},
    "sandor": {"name": "Sandor Clegane", "short_names": ["The Hound"], "house": "clegane"},
    "tywin": {"name": "Tywin Lannister", "short_names": ["Tywin"], "house": "lannister"},
    "melisandre": {"name": "Melisandre", "short_names": [], "house": None},
    "hodor": {"name": "Hodor", "short_names": [], "house": None},
}

# Fits a Note with its name: two rows of quote and one of name.
WINTER = {"character": "ned", "text": "Winter is coming!"}
# Too long for a Note; fits a Flagship with its name.
LION = {"character": "tywin", "text": "A lion does not concern himself with the opinion of sheep."}
# Fits a Note only without a name, by a character without a house.
NIGHT = {"character": "melisandre", "text": "The night is dark and full of terrors."}
# Fits a Note only without a name: three rows of quote.
DRINK = {"character": "tyrion", "text": "That's what I do: I drink and I know things."}
# Fits a Note with its name, and is crude.
KING = {"character": "sandor", "text": "Fuck the king."}
# Fits a Note with its name.
DOOR = {"character": "hodor", "text": "Hold the door."}
# Longer than any board.
SPEECH = {
    "character": "arya",
    "text": (
        "Leave one wolf alive and the sheep are never safe. When people ask you what happened here, tell them "
        "the North remembers. Tell them winter came for House Frey."
    ),
}

QUOTES = [WINTER, LION, NIGHT, DRINK, KING, DOOR, SPEECH]

# The quotes the committed previews were rendered from, one per board.
PREVIEW_QUOTES = {"note": WINTER, "flagship": LION, "note_array": NIGHT}


def collection(*quotes, houses=None, characters=None):
    """A data file holding *quotes*, shaped like the real ``datas.json``."""
    return {
        "houses": HOUSES if houses is None else houses,
        "characters": CHARACTERS if characters is None else characters,
        "quotes": list(quotes),
    }


class FakeData:
    """Stands in for quotes.json: *body* is what the file holds, or the error reading it raises."""

    def __init__(self):
        self.body = collection(*QUOTES)

    def __call__(self):
        if isinstance(self.body, Exception):
            raise self.body
        return got.parse_collection(self.body)


@pytest.fixture(autouse=True)
def fresh_memory():
    """Each test starts with no quotes remembered as recently shown."""
    got.clear_recent()
    yield
    got.clear_recent()


@pytest.fixture
def manifest():
    return MANIFEST


@pytest.fixture
def source(monkeypatch):
    fake = FakeData()
    monkeypatch.setattr(got, "load_quotes", fake)
    return fake


@pytest.fixture
def make_plugin(source):
    """Build a configured plugin instance whose quotes come from the fake collection."""

    def _make(**config):
        plugin = GameOfThronesQuotesPlugin(MANIFEST)
        plugin.config = dict(config)
        return plugin

    return _make
