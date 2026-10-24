"""Guards that keep manifest, code, docs and changelog from drifting apart.

The manifest is not just metadata — FiestaBoard renders the plugin directory
from it and the template editor offers whatever variables it declares. A field
that no longer matches the code is a broken listing, not a cosmetic slip.
"""

import json
import pathlib
import re

import pytest
from src.devices import BoardContext
from src.plugins.base import OptionsRequest

from plugins.game_of_thrones_quotes import (
    ALIGNMENTS,
    CHARACTER_MAX,
    DEFAULT_ALIGNMENT,
    HOUSE_MAX,
    QUOTE_MAX,
    GameOfThronesQuotesPlugin,
)

from .conftest import PREVIEW_QUOTES, collection

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOARD_SHAPES = {"flagship": (6, 22), "note": (3, 15)}


def board_for(preview):
    """The board a manifest preview is drawn for."""
    if preview["device_type"] == "note_array":
        return BoardContext(device_type="note_array", rows=preview["notes_tall"] * 3, cols=preview["notes_wide"] * 15)
    return BoardContext.from_device_type(preview["device_type"])


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / "manifest.json").read_text())


class TestIdentity:
    def test_id_matches_the_plugin_class(self, manifest):
        assert manifest["id"] == GameOfThronesQuotesPlugin(manifest).plugin_id

    def test_version_is_semver(self, manifest):
        assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])

    def test_version_matches_the_changelog(self, manifest):
        """The changelog is the source of truth; a release without an entry is a lie."""
        changelog = (ROOT / "CHANGELOG.md").read_text()
        released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
        assert released, "CHANGELOG.md has no released versions"
        assert manifest["version"] == released[0]


class TestSettingsSchema:
    def test_enum_options_match_the_code(self, manifest):
        assert tuple(manifest["settings_schema"]["properties"]["alignment"]["enum"]) == ALIGNMENTS

    def test_schema_defaults_match_the_code_fallbacks(self, manifest, make_plugin, source):
        """A board configured purely from defaults must render what the form shows."""
        properties = manifest["settings_schema"]["properties"]
        assert properties["alignment"]["default"] == DEFAULT_ALIGNMENT
        assert properties["show_character"]["default"] is True
        assert properties["skip_crude"]["default"] is False
        assert properties["characters"]["default"] == []
        assert properties["houses"]["default"] == []

        defaults = {name: prop["default"] for name, prop in properties.items() if "default" in prop}
        for device_type in BOARD_SHAPES:
            source.body = collection(PREVIEW_QUOTES[device_type])
            board = BoardContext.from_device_type(device_type)
            assert (
                make_plugin(**defaults).get_data(board).formatted_lines == make_plugin().get_data(board).formatted_lines
            )

    def test_every_enum_has_a_label(self, manifest):
        for name, prop in manifest["settings_schema"]["properties"].items():
            if "enum" in prop:
                assert len(prop.get("enumNames", [])) == len(prop["enum"]), f"{name} labels do not line up"

    def test_every_enum_default_is_one_of_its_options(self, manifest):
        for name, prop in manifest["settings_schema"]["properties"].items():
            if "enum" in prop and "default" in prop:
                assert prop["default"] in prop["enum"], f"{name} default is not an option"

    def test_every_remote_options_field_is_answered_by_the_plugin(self, manifest, make_plugin):
        """A picker whose options_id the plugin does not serve renders as an error."""
        for name, prop in manifest["settings_schema"]["properties"].items():
            if prop.get("ui:widget") == "remote-options":
                options = make_plugin().get_options(OptionsRequest(prop["ui:options"]["options_id"])).options
                assert options, name
                assert prop["type"] == "array" and prop["items"]["type"] == "string", name
                assert all(isinstance(option.value, str) for option in options), name

    def test_the_refresh_floor_matches_the_schema(self, manifest):
        refresh = manifest["settings_schema"]["properties"]["refresh_seconds"]
        assert refresh["minimum"] == manifest["min_refresh_seconds"]
        assert refresh["minimum"] <= refresh["default"] <= refresh["maximum"]


class TestVariables:
    def test_declared_variables_are_the_ones_the_plugin_produces(self, manifest, make_plugin):
        """A declared variable that never materialises renders as blank on the board."""
        produced = set(make_plugin().get_data(BoardContext.from_device_type("flagship")).data)
        assert produced == set(manifest["variables"]["simple"])

    def test_every_variable_names_a_group_that_exists(self, manifest):
        groups = set(manifest["variables"]["groups"])
        for name, spec in manifest["variables"]["simple"].items():
            assert spec["group"] in groups, f"{name} points at an unknown group"

    def test_every_simple_variable_has_a_max_length(self, manifest):
        simple = manifest["variables"]["simple"]
        assert set(manifest["max_lengths"]) == set(simple)
        for name, declared in manifest["max_lengths"].items():
            assert simple[name]["max_length"] == declared

    def test_the_text_limits_in_code_match_the_manifest(self, manifest):
        limits = manifest["max_lengths"]
        assert (limits["quote"], limits["character"], limits["house"]) == (QUOTE_MAX, CHARACTER_MAX, HOUSE_MAX)

    def test_produced_values_stay_within_their_max_length(self, manifest, make_plugin):
        for device_type in BOARD_SHAPES:
            plugin = make_plugin()
            for _ in range(20):
                plugin.clear_cache()
                data = plugin.get_data(BoardContext.from_device_type(device_type)).data
                for name, limit in manifest["max_lengths"].items():
                    assert len(data[name]) <= limit, f"{name} on a {device_type} is {len(data[name])} long"

    def test_each_demo_fills_its_board_from_the_block(self, manifest):
        assert set(manifest["demo"]) == set(BOARD_SHAPES)
        for device_type, demo in manifest["demo"].items():
            rows, _ = BOARD_SHAPES[device_type]
            assert demo["template"][0] == f"{{{{{manifest['id']}.block}}}}"
            assert demo["template"][1:] == [""] * (rows - 1)
            assert len(demo["line_metadata"]) == rows
            assert all(line == {"alignment": "left", "wrap": False} for line in demo["line_metadata"])


class TestBoardPreviews:
    def test_teaser_fits_the_narrowest_board(self, manifest):
        assert len(manifest["teaser"]) <= 15

    def test_preview_rows_fill_their_board(self, manifest):
        for preview in manifest["previews"]:
            board = board_for(preview)
            assert len(preview["rows"]) == board.rows
            assert all(len(row) == board.cols for row in preview["rows"]), preview["device_type"]

    def test_both_board_shapes_and_a_note_array_are_covered(self, manifest):
        assert {p["device_type"] for p in manifest["previews"]} == {*BOARD_SHAPES, "note_array"}

    @pytest.mark.parametrize("device_type", [*sorted(BOARD_SHAPES), "note_array"])
    def test_previews_match_what_the_plugin_actually_renders(self, manifest, device_type, make_plugin, source):
        """A hand-edited preview that no longer matches the code misleads the directory."""
        source.body = collection(PREVIEW_QUOTES[device_type])
        preview = next(p for p in manifest["previews"] if p["device_type"] == device_type)
        assert preview["rows"] == make_plugin().get_data(board_for(preview)).formatted_lines

    def test_every_screenshot_exists_and_one_is_primary(self, manifest):
        screenshots = manifest["screenshots"]
        assert sum(1 for shot in screenshots if shot.get("primary")) == 1
        for shot in screenshots:
            assert (ROOT / shot["src"]).is_file(), shot["src"]
            assert shot["alt"] and shot["caption"]

    def test_the_long_preview_quote_is_flagship_only(self, make_plugin, source):
        """The Flagship preview shows what a Note never gets."""
        source.body = collection(PREVIEW_QUOTES["flagship"])
        result = make_plugin().get_data(BoardContext.from_device_type("note"))
        assert result.formatted_lines[-1].rstrip().endswith("...")

    def test_the_teaser_is_the_note_previews_first_row(self, manifest):
        note = next(p["rows"] for p in manifest["previews"] if p["device_type"] == "note")
        assert manifest["teaser"] == note[0].strip()

    def test_the_variable_examples_match_the_note_preview(self, manifest):
        note = next(p["rows"] for p in manifest["previews"] if p["device_type"] == "note")
        simple = manifest["variables"]["simple"]
        for index, row in enumerate(note):
            assert simple[f"line{index + 1}"]["example"] == row
        assert simple["block"]["example"] == "\\n".join(note)
