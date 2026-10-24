"""Board-geometry conformance for the Game of Thrones Quotes plugin.

Runs the shared FiestaBoard conformance suite (``src/plugins/
geometry_conformance.py`` in core -- importable here because core is on
``PYTHONPATH`` in plugin CI) across every board shape the platform supports,
including note arrays up to 120x24 and FiestaPanel grids. The quotes are the
real quotes.json; nothing touches the network.

``strict_growth`` is intentionally omitted: the layout shows one quote, not a
list, so a taller board is not expected to carry more of it.
"""

import pytest
from src.plugins.geometry_conformance import assert_board_conformance

from plugins.game_of_thrones_quotes import GameOfThronesQuotesPlugin

from .conftest import MANIFEST


@pytest.mark.parametrize("config", [{}, {"alignment": "left", "character_name": "never"}, {"character_name": "always"}])
def test_renders_on_every_board_shape(config):
    def make_plugin() -> GameOfThronesQuotesPlugin:
        plugin = GameOfThronesQuotesPlugin(MANIFEST)
        plugin.config = dict(config)
        return plugin

    assert_board_conformance(make_plugin, manifest=MANIFEST, require_note_array_preview=True)
