# Game of Thrones Quotes Plugin

A Game of Thrones quote on the board, a new one on every refresh: word-wrapped, centered, and signed with the character who said it — only quotes that fit the board it is shown on.

```
   WINTER IS
    COMING!
- EDDARD STARK
```

## Overview

196 quotes from 48 characters of the TV show ship with the plugin in [`data.json`](data.json): nothing is downloaded, no account or API key. Each character comes with their house and the shorter names they go by, which the **Characters** and **Houses** pickers and the signature are built from.

Only quotes that fit the board are picked, all of them equally likely:

- A **Note** (15×3) gets the short ones, 54 of the 196. Most leave no row for the name, so it is left off rather than the quote cut.
- A **Flagship** (22×6) gets the long ones too, 169 of them, nearly all signed.

Quotes shown in the last 50 refreshes are passed over; once every quote that fits has been shown, the one shown longest ago comes next.

### On a Note (15×3)

```
   WINTER IS
    COMING!
- EDDARD STARK
```

### On a Flagship (22×6)

```
   A LION DOES NOT
 CONCERN HIMSELF WITH
THE OPINION OF SHEEP.

  - TYWIN LANNISTER
```

The layout is computed from the board's size, so any other shape — a note array, a wide composite — gets the quotes that fit its own width and height. A name too long for its row is shortened to the name the character goes by: `- TYRION LANNISTER` becomes `- TYRION` and `- SANDOR CLEGANE` becomes `- THE HOUND` on a Note.

## Setup

1. Install the plugin from its repository URL in FiestaBoard.
2. Open **Integrations → Game of Thrones Quotes** and enable it. Nothing else is required.
3. Put `{{game_of_thrones_quotes.block}}` on the first line of a page, with the line set to left alignment and no wrap — the plugin pads and centers the rows itself.

To narrow the quotes down, pick **Characters** or **Houses**; each option says how many quotes it brings. With several chosen, each quote is by one of the chosen characters or from one of the chosen houses — *House Stark* and *Hodor* gives every Stark and Hodor. A Note with only a few characters chosen may find nothing short enough; it then shows the shortest quote cut off with `...`.

## Settings

| Setting | Default | |
|---------|---------|---|
| Characters | any | Only quotes by these characters. |
| Houses | any | Only quotes by members of these houses. |
| Show character | on | Sign the quote. Shortened to the first name, or left off when there is no row for it. |
| Skip crude language | off | Leave out the handful of quotes with swearing in them, most of them the Hound's. |
| Alignment | Centered | Centered, with the name centered below; or left-aligned, with the name flush right. |
| Refresh interval | 3600 s | How long a quote stays up. Minimum 60 s: everything happens locally. |

## Template Variables

### Quote

| Variable | Description | Example |
|----------|-------------|---------|
| `{{game_of_thrones_quotes.quote}}` | The quote as board text, not wrapped | `WINTER IS COMING!` |
| `{{game_of_thrones_quotes.character}}` | The full name of the character | `EDDARD STARK` |
| `{{game_of_thrones_quotes.house}}` | The character's house, empty for those without one | `HOUSE STARK OF WINTERFELL` |

### Board Lines

| Variable | Description |
|----------|-------------|
| `{{game_of_thrones_quotes.block}}` | The whole layout, rows separated by newlines — put it on the first template line |
| `{{game_of_thrones_quotes.line1}}` … `{{game_of_thrones_quotes.line6}}` | The same rows one by one, full board width; empty past the board's height |

## The quotes

[`data.json`](data.json) holds three lists:

```json
{
  "houses":     { "stark": { "name": "House Stark of Winterfell" } },
  "characters": { "ned":   { "name": "Eddard Stark", "short_names": ["Ned Stark", "Ned"], "house": "stark" } },
  "quotes":     [ { "character": "ned", "text": "Winter is coming!" } ]
}
```

`short_names` are the names a character goes by, longest first; the signature takes the longest of the full name and these that fits the row. `house` is `null` for characters without one. Tests check the file: every quote readable on the board as written, no quote twice, every character and house quoted, and every name fitting a Note in one of its forms.

## Development

The plugin imports `src.plugins.base` from the FiestaBoard core, so tests need the core repo checked out next to this one:

```bash
git clone https://github.com/Fiestaboard/FiestaBoard.git ../FiestaBoard

# Import paths matching how FiestaBoard loads the plugin
mkdir -p plugins && touch plugins/__init__.py
ln -sfn .. plugins/game_of_thrones_quotes

python -m venv .venv && .venv/bin/pip install pytest pytest-cov requests
PYTHONPATH=".:../FiestaBoard" .venv/bin/pytest tests/ --cov=. --cov-report=term-missing
```

The plugin tests run on a small fixture collection, so a change to the quotes never breaks a test of the layout; `data.json` has tests of its own. The board previews in `manifest.json` are rendered from the fixture, and a test fails if they drift from what the code produces.

## License

MIT, for the code. The quotes are from the TV series *Game of Thrones* (HBO), after the novels by George R. R. Martin.
