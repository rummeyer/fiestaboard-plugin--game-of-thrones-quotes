"""Behaviour of the Game of Thrones Quotes plugin: the text, the layout, the choice and the data file."""

import json
import re

import pytest
from src.devices import BoardContext
from src.plugins.base import OptionsRequest, OptionsUnavailable

from plugins import game_of_thrones_quotes as got
from plugins.game_of_thrones_quotes import (
    BARE,
    FULL,
    OVERFLOW,
    Quote,
    QuotesError,
    align,
    choose,
    name_line,
    name_variants,
    parse_collection,
    parse_keys,
    place,
    to_board_text,
    truncate,
    wrap,
)

from .conftest import DOOR, DRINK, KING, LION, NIGHT, QUOTES, SPEECH, WINTER, collection

NOTE = BoardContext.from_device_type("note")
FLAGSHIP = BoardContext.from_device_type("flagship")


def quote(entry):
    """The parsed :class:`Quote` for one fixture entry."""
    return parse_collection(collection(entry))[0]


def render(plugin, board=FLAGSHIP):
    """One fresh render, past the base class's result cache."""
    plugin.clear_cache()
    return plugin.get_data(board)


class TestBoardText:
    def test_text_is_uppercased(self):
        assert to_board_text("Winter is coming!") == "WINTER IS COMING!"

    def test_curly_quotes_and_dashes_become_the_boards_own(self):
        assert to_board_text("I’m “fine” – really…") == 'I\'M "FINE" - REALLY...'

    def test_accents_are_dropped(self):
        assert to_board_text("Daenerys Stormborn, née Targaryen") == "DAENERYS STORMBORN, NEE TARGARYEN"

    def test_characters_without_a_tile_are_left_out(self):
        assert to_board_text("Fire * blood") == "FIRE BLOOD"

    def test_whitespace_collapses(self):
        assert to_board_text("  Hold \n the   door ") == "HOLD THE DOOR"


class TestWrap:
    def test_rows_break_between_words(self):
        assert wrap("WINTER IS COMING!", 15) == ["WINTER IS", "COMING!"]

    def test_a_word_longer_than_a_row_is_split(self):
        assert wrap("A KHALEESSSSSSSSSI", 8) == ["A", "KHALEESS", "SSSSSSSI"]

    def test_nothing_gives_no_rows(self):
        assert wrap("", 15) == []


class TestNames:
    def test_the_full_name_comes_first_then_the_short_ones(self):
        assert name_variants("Eddard Stark", ("Ned Stark", "Ned")) == ["Eddard Stark", "Ned Stark", "Ned"]

    def test_a_name_without_short_ones_stays_as_it_is(self):
        assert name_variants("Hodor") == ["Hodor"]

    def test_repeats_and_blanks_are_left_out(self):
        assert name_variants(" Bronn ", ("Bronn", "")) == ["Bronn"]

    def test_the_longest_name_that_fits_is_used(self):
        assert name_line("Tyrion Lannister", ("Tyrion",), 22) == "- TYRION LANNISTER"
        assert name_line("Tyrion Lannister", ("Tyrion",), 15) == "- TYRION"
        assert name_line("Sandor Clegane", ("The Hound",), 15) == "- THE HOUND"

    def test_a_name_that_never_fits_is_left_off(self):
        assert name_line("Melisandre", (), 8) == ""


class TestTruncate:
    def test_the_last_row_ends_in_an_ellipsis(self):
        assert truncate(["ONE", "TWO", "THREE"], 2, 15) == ["ONE", "TWO..."]

    def test_a_full_last_row_gives_up_its_last_word(self):
        assert truncate(["A LION DOES NOT", "CONCERN"], 1, 15) == ["A LION DOES..."]

    def test_a_row_without_spaces_is_cut_short(self):
        assert truncate(["ABCDEFGHIJKLMNO"], 1, 15) == ["ABCDEFGHIJKL..."]

    def test_trailing_punctuation_is_not_doubled(self):
        assert truncate(["WINTER,", "IS"], 1, 15) == ["WINTER..."]

    def test_no_rows_stay_no_rows(self):
        assert truncate([], 3, 15) == []


class TestAlign:
    @pytest.mark.parametrize(("alignment", "row"), [("center", " AB  "), ("left", "AB   "), ("right", "   AB")])
    def test_rows_are_padded_to_the_board(self, alignment, row):
        assert align("AB", 5, alignment) == row


class TestPlace:
    def test_a_short_quote_fits_a_note_with_its_name(self):
        placement = place(quote(WINTER), 15, 3, show_name=True, alignment="center")
        assert placement.fit == FULL
        assert placement.rows == ["   WINTER IS   ", "    COMING!    ", "- EDDARD STARK "]

    def test_a_quote_that_fills_the_board_is_shown_without_its_name(self):
        placement = place(quote(DRINK), 15, 3, show_name=True, alignment="center")
        assert placement.fit == BARE
        assert not any(row.strip().startswith("-") for row in placement.rows)

    def test_a_name_too_long_for_any_row_makes_the_fit_bare(self):
        assert place(quote(DOOR), 14, 3, show_name=True, alignment="center").fit == FULL
        assert place(quote(DOOR), 7, 3, show_name=True, alignment="center").fit == BARE

    def test_with_the_name_turned_off_every_quote_that_fits_is_full(self):
        assert place(quote(DRINK), 15, 3, show_name=False, alignment="center").fit == FULL

    def test_a_blank_row_separates_the_name_when_there_is_room(self):
        rows = place(quote(KING), 15, 3, show_name=True, alignment="center").rows
        assert rows == ["FUCK THE KING. ", "               ", "  - THE HOUND  "]

    def test_left_aligned_quotes_are_signed_flush_right(self):
        rows = place(quote(WINTER), 15, 3, show_name=True, alignment="left").rows
        assert rows == ["WINTER IS      ", "COMING!        ", " - EDDARD STARK"]

    def test_a_long_quote_only_fits_a_flagship(self):
        assert place(quote(LION), 15, 3, show_name=True, alignment="center").fit == OVERFLOW
        assert place(quote(LION), 22, 6, show_name=True, alignment="center").fit == FULL

    def test_a_quote_longer_than_the_board_is_cut_off(self):
        placement = place(quote(SPEECH), 22, 6, show_name=True, alignment="center")
        assert placement.fit == OVERFLOW
        assert placement.spill > 0
        assert placement.rows[-1].rstrip().endswith("...")

    def test_a_word_too_long_for_a_row_does_not_count_as_fitting(self):
        long_word = Quote(id=0, text="Dracarys!", character="Daenerys", character_id="daenerys")
        assert place(long_word, 5, 3, show_name=False, alignment="center").fit == OVERFLOW

    @pytest.mark.parametrize("entry", QUOTES)
    @pytest.mark.parametrize(("width", "height"), [(15, 3), (22, 6), (30, 6)])
    def test_every_row_is_exactly_as_wide_as_the_board(self, entry, width, height):
        rows = place(quote(entry), width, height, show_name=True, alignment="center").rows
        assert len(rows) == height
        assert all(len(row) == width for row in rows)


class TestChoose:
    def test_only_quotes_that_fit_are_chosen(self):
        quotes = parse_collection(collection(*QUOTES))
        chosen = {choose(quotes, 15, 3, show_name=True, alignment="center")[0].text for _ in range(200)}
        assert chosen == {WINTER["text"], NIGHT["text"], DRINK["text"], KING["text"], DOOR["text"]}

    def test_a_flagship_gets_the_long_ones_too(self):
        quotes = parse_collection(collection(*QUOTES))
        chosen = {choose(quotes, 22, 6, show_name=True, alignment="center")[0].text for _ in range(300)}
        assert LION["text"] in chosen
        assert SPEECH["text"] not in chosen

    def test_a_quote_shown_lately_is_passed_over(self):
        quotes = parse_collection(collection(WINTER, DOOR))
        got.remember_shown(quotes[0])
        assert all(choose(quotes, 15, 3, show_name=True, alignment="center")[0] == quotes[1] for _ in range(20))

    def test_when_all_were_shown_lately_the_oldest_comes_next(self):
        quotes = parse_collection(collection(WINTER, DOOR, KING))
        for index in (1, 0, 2):
            got.remember_shown(quotes[index])
        assert choose(quotes, 15, 3, show_name=True, alignment="center")[0] == quotes[1]

    def test_showing_a_quote_again_makes_it_the_most_recent(self):
        quotes = parse_collection(collection(WINTER, DOOR))
        got.remember_shown(quotes[0])
        got.remember_shown(quotes[1])
        got.remember_shown(quotes[0])
        assert choose(quotes, 15, 3, show_name=True, alignment="center")[0] == quotes[1]

    def test_signed_only_keeps_the_quotes_with_room_for_the_name(self):
        quotes = parse_collection(collection(WINTER, NIGHT, DRINK, DOOR))
        chosen = {
            choose(quotes, 15, 3, show_name=True, alignment="center", signed_only=True)[0].text for _ in range(100)
        }
        assert chosen == {WINTER["text"], DOOR["text"]}

    def test_signed_only_takes_any_that_fits_when_none_has_room_for_the_name(self):
        quotes = parse_collection(collection(NIGHT, DRINK, LION))
        chosen = {
            choose(quotes, 15, 3, show_name=True, alignment="center", signed_only=True)[0].text for _ in range(100)
        }
        assert chosen == {NIGHT["text"], DRINK["text"]}

    def test_when_nothing_fits_the_least_overflowing_quote_is_cut_off(self):
        quotes = parse_collection(collection(SPEECH, LION))
        chosen, placement = choose(quotes, 15, 3, show_name=True, alignment="center")
        assert chosen.text == LION["text"]
        assert placement.fit == OVERFLOW


class TestSettings:
    @pytest.mark.parametrize(
        ("value", "keys"), [(None, []), ("", []), ([], []), (["ned", " arya "], ["ned", "arya"]), (["", "x"], ["x"])]
    )
    def test_keys_are_read_from_the_picker(self, value, keys):
        assert parse_keys(value) == keys

    @pytest.mark.parametrize("value", ["ned", [1], [None], {"ned": True}])
    def test_anything_else_is_unreadable(self, value):
        assert parse_keys(value) is None

    def test_unreadable_keys_are_reported(self, make_plugin):
        errors = make_plugin().validate_config({"characters": "ned", "houses": [3]})
        assert any("Characters" in error for error in errors)
        assert any("Houses" in error for error in errors)

    def test_a_valid_config_has_no_errors(self, make_plugin):
        assert make_plugin().validate_config({"characters": ["ned"], "houses": [], "refresh_seconds": 3600}) == []


class TestCollection:
    def test_each_quote_gets_its_characters_and_houses_names(self):
        parsed = quote(WINTER)
        assert parsed.character == "Eddard Stark"
        assert parsed.short_names == ("Ned Stark", "Ned")
        assert (parsed.character_id, parsed.house, parsed.house_id) == ("ned", "House Stark of Winterfell", "stark")

    def test_a_character_without_a_house_has_none(self):
        assert (quote(DOOR).house, quote(DOOR).house_id) == ("", "")

    def test_a_house_the_file_does_not_list_is_no_house(self):
        body = collection(WINTER, characters={"ned": {"name": "Ned", "house": "dayne"}})
        assert parse_collection(body)[0].house_id == ""

    def test_unusable_quotes_are_left_out(self):
        body = collection(
            WINTER,
            "not a quote",
            {"character": "ned", "text": "  "},
            {"character": "nobody", "text": "Who?"},
            {"character": "ned"},
        )
        assert [parsed.text for parsed in parse_collection(body)] == [WINTER["text"]]

    def test_quotes_are_numbered_by_their_place_in_the_file(self):
        assert [parsed.id for parsed in parse_collection(collection(WINTER, DOOR))] == [0, 1]

    @pytest.mark.parametrize("body", [{}, {"quotes": "x", "characters": [], "houses": None}, collection()])
    def test_a_file_without_usable_quotes_is_an_error(self, body):
        with pytest.raises(QuotesError):
            parse_collection(body)

    def test_crude_quotes_are_recognised(self):
        assert got.is_crude(quote(KING))
        assert not got.is_crude(quote(WINTER))


@pytest.fixture(scope="module")
def body():
    """The real quotes.json."""
    return json.loads(got.QUOTES_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def quotes(body):
    return parse_collection(body)


class TestDataFile:
    """The quotes that ship with the plugin."""

    def test_every_quote_is_usable(self, body, quotes):
        assert len(quotes) == len(body["quotes"]) == 196

    def test_no_quote_is_there_twice(self, quotes):
        texts = [re.sub(r"[^A-Z ]", "", to_board_text(quote.text)) for quote in quotes]
        assert len(set(texts)) == len(texts)

    def test_every_quote_reads_on_the_board_as_written(self, quotes):
        """Nothing is dropped for want of a tile, like a censored "c*nt"."""
        for quote in quotes:
            assert len(to_board_text(quote.text)) == len(quote.text), quote.text

    def test_every_quote_ends_like_a_sentence(self, quotes):
        for quote in quotes:
            assert quote.text[-1] in '.!?"', quote.text

    def test_every_character_and_house_is_quoted(self, body, quotes):
        assert {quote.character_id for quote in quotes} == set(body["characters"])
        assert {quote.house_id for quote in quotes} - {""} == set(body["houses"])

    def test_short_names_are_shorter_and_longest_first(self, body):
        for key, character in body["characters"].items():
            lengths = [len(character["name"])] + [len(name) for name in character["short_names"]]
            assert lengths == sorted(lengths, reverse=True), key
            assert len(set(lengths)) == len(lengths), key

    def test_every_name_fits_a_note_in_some_form(self, quotes):
        for quote in quotes:
            assert name_line(quote.character, quote.short_names, 15), quote.character

    def test_a_note_and_a_flagship_have_plenty_to_choose_from(self, quotes):
        def fitting(width, height):
            return sum(
                place(quote, width, height, show_name=True, alignment="center").fit > OVERFLOW for quote in quotes
            )

        assert fitting(15, 3) >= 50
        assert fitting(22, 6) >= 150

    def test_a_note_has_enough_quotes_with_room_for_the_name(self, quotes):
        signed = sum(place(quote, 15, 3, show_name=True, alignment="center").fit == FULL for quote in quotes)
        assert signed >= 20

    def test_the_file_is_read_once(self, monkeypatch, tmp_path):
        path = tmp_path / "quotes.json"
        path.write_text(json.dumps(collection(DOOR)))
        monkeypatch.setattr(got, "QUOTES_FILE", path)
        got.load_quotes.cache_clear()
        try:
            assert [quote.text for quote in got.load_quotes()] == [DOOR["text"]]
            path.write_text(json.dumps(collection(WINTER)))
            assert [quote.text for quote in got.load_quotes()] == [DOOR["text"]]
        finally:
            got.load_quotes.cache_clear()

    @pytest.mark.parametrize(
        ("content", "message"), [(None, "could not be read"), ("{", "could not be read"), ("[]", "not a JSON object")]
    )
    def test_an_unreadable_file_is_an_error(self, monkeypatch, tmp_path, content, message):
        path = tmp_path / "quotes.json"
        if content is not None:
            path.write_text(content)
        monkeypatch.setattr(got, "QUOTES_FILE", path)
        got.load_quotes.cache_clear()
        try:
            with pytest.raises(QuotesError, match=message):
                got.load_quotes()
        finally:
            got.load_quotes.cache_clear()


class TestRendering:
    def test_a_note_shows_a_quote_that_fits_it(self, make_plugin):
        result = render(make_plugin(), NOTE)
        assert result.available
        assert len(result.formatted_lines) == 3
        assert to_board_text(LION["text"]) != result.data["quote"]

    def test_the_variables_are_board_text(self, make_plugin, source):
        source.body = collection(WINTER)
        data = render(make_plugin()).data
        assert data["quote"] == "WINTER IS COMING!"
        assert data["character"] == "EDDARD STARK"
        assert data["house"] == "HOUSE STARK OF WINTERFELL"

    def test_the_block_is_the_board_and_the_lines_its_rows(self, make_plugin):
        result = render(make_plugin(), NOTE)
        assert result.data["block"] == "\n".join(result.formatted_lines)
        assert [result.data[f"line{index}"] for index in range(1, 4)] == result.formatted_lines
        assert result.data["line4"] == result.data["line5"] == result.data["line6"] == ""

    def test_without_a_board_the_flagship_shape_is_used(self, make_plugin):
        result = make_plugin().get_data()
        assert len(result.formatted_lines) == 6
        assert all(len(row) == 22 for row in result.formatted_lines)

    def test_the_name_can_be_turned_off(self, make_plugin, source):
        source.body = collection(WINTER)
        assert render(make_plugin(character_name="never"), NOTE).formatted_lines == [
            "   WINTER IS   ",
            "    COMING!    ",
            "               ",
        ]

    def test_the_alignment_follows_the_setting_and_ignores_an_unknown_one(self, make_plugin, source):
        source.body = collection(WINTER)
        assert render(make_plugin(alignment="left"), NOTE).formatted_lines[0] == "WINTER IS      "
        assert render(make_plugin(alignment="justify"), NOTE).formatted_lines[0] == "   WINTER IS   "

    def test_only_the_chosen_characters_and_houses_are_quoted(self, make_plugin):
        plugin = make_plugin(characters=["hodor"], houses=["clegane"])
        seen = {render(plugin, NOTE).data["character"] for _ in range(60)}
        assert seen == {"HODOR", "SANDOR CLEGANE"}

    def test_always_signed_picks_only_quotes_with_room_for_the_name(self, make_plugin):
        plugin = make_plugin(character_name="always")
        rows = [render(plugin, NOTE).formatted_lines for _ in range(40)]
        assert all(lines[-1].strip().startswith("- ") for lines in rows)

    def test_when_it_fits_also_picks_quotes_without_room_for_the_name(self, make_plugin):
        plugin = make_plugin(character_name="fits")
        seen = {render(plugin, NOTE).data["quote"] for _ in range(100)}
        assert to_board_text(DRINK["text"]) in seen

    @pytest.mark.parametrize(
        ("config", "mode"),
        [
            ({}, "fits"),
            ({"character_name": "always"}, "always"),
            ({"character_name": "loud"}, "fits"),
            ({"show_character": False}, "never"),
            ({"signed_only": True}, "always"),
            ({"show_character": False, "signed_only": True}, "never"),
            ({"character_name": "fits", "show_character": False}, "fits"),
        ],
    )
    def test_the_name_setting_reads_configs_saved_before_it(self, config, mode):
        assert got.name_mode(config) == mode

    def test_crude_quotes_can_be_skipped(self, make_plugin, source):
        source.body = collection(KING, DOOR)
        plugin = make_plugin(skip_crude=True)
        assert {render(plugin, NOTE).data["quote"] for _ in range(30)} == {"HOLD THE DOOR."}

    def test_crude_quotes_are_kept_by_default(self, make_plugin, source):
        source.body = collection(KING)
        assert render(make_plugin(), NOTE).data["quote"] == "FUCK THE KING."

    def test_a_selection_without_quotes_leaves_the_plugin_unavailable(self, make_plugin):
        result = render(make_plugin(characters=["jon"]))
        assert not result.available
        assert "chosen characters" in result.error

    def test_an_unreachable_collection_leaves_the_plugin_unavailable(self, make_plugin, source):
        source.body = QuotesError("the quote collection is unreachable: offline")
        result = render(make_plugin())
        assert not result.available
        assert "unreachable" in result.error

    def test_a_malformed_file_does_not_break_the_render_loop(self, make_plugin, source):
        source.body = {"quotes": [{"character": "ned", "text": "Hi"}], "characters": {"ned": "Ned"}}
        result = render(make_plugin())
        assert not result.available

    def test_an_unexpected_failure_does_not_break_the_render_loop(self, make_plugin, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(got, "load_quotes", broken)
        result = render(make_plugin())
        assert not result.available
        assert result.error == "boom"


class TestOptions:
    def test_characters_are_listed_by_name_with_their_house_and_count(self, make_plugin, source):
        source.body = collection(WINTER, DRINK, DOOR, DOOR)
        options = make_plugin().get_options(OptionsRequest("characters")).options
        assert [(option.value, option.label, option.description) for option in options] == [
            ("ned", "Eddard Stark", "House Stark of Winterfell · 1 quote"),
            ("hodor", "Hodor", "2 quotes"),
            ("tyrion", "Tyrion Lannister", "House Lannister of Casterly Rock · 1 quote"),
        ]

    def test_houses_are_listed_without_the_houseless(self, make_plugin, source):
        source.body = collection(WINTER, LION, DRINK, DOOR)
        options = make_plugin().get_options(OptionsRequest("houses")).options
        assert [(option.value, option.description) for option in options] == [
            ("lannister", "2 quotes"),
            ("stark", "1 quote"),
        ]

    def test_typing_filters_by_any_part_of_the_name(self, make_plugin):
        options = make_plugin().get_options(OptionsRequest("characters", query=" LANN ")).options
        assert [option.value for option in options] == ["tyrion", "tywin"]

    def test_the_list_is_cut_to_the_limit_but_counts_all(self, make_plugin):
        result = make_plugin().get_options(OptionsRequest("characters", limit=2))
        assert len(result.options) == 2
        assert result.total == 7

    def test_an_unreachable_collection_is_a_hint_not_a_crash(self, make_plugin, source):
        source.body = QuotesError("down")
        with pytest.raises(OptionsUnavailable):
            make_plugin().get_options(OptionsRequest("houses"))

    def test_other_pickers_are_left_to_the_base_class(self, make_plugin):
        with pytest.raises(NotImplementedError):
            make_plugin().get_options(OptionsRequest("seasons"))
