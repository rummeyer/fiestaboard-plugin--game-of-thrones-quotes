# Changelog

All notable changes to this plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version here is the source of truth for `manifest.json` — a test fails if
the two drift apart.

## [Unreleased]

## [1.2.0] — 2026-10-24

### Added

- **Only quotes with room for the name**, off by default: skips quotes that
  leave no row for the character's name. Mostly for a Note, where it leaves 21
  of the 54 quotes that fit. When none of the chosen characters' or houses'
  quotes has room for the name, any quote that fits is shown instead.

## [1.1.0] — 2026-10-24

### Added

- Ready for the FiestaBoard plugin registry: a setup guide in
  `docs/SETUP.md` and board screenshots of a Note, a Flagship and a 2x2 note
  array, listed in the manifest.
- A preview on a 2x2 note array, and the board-shape conformance test of
  FiestaBoard core across every supported board.
- The demo page for a Flagship as well as a Note.

### Fixed

- `{{game_of_thrones_quotes.block}}` and `line1` … `line6` declare the lengths
  they reach on the largest boards: a row is up to 128 tiles on the widest
  FiestaPanel grid, and `block` up to 12383. The template editor sizes its fit
  warnings from these numbers.

## [1.0.0] — 2026-10-24

### Added

- A random Game of Thrones quote on every refresh, word-wrapped and centered,
  signed with the character who said it.
- Only quotes that fit the board: a Note gets the short ones, a Flagship the
  long ones too. A name too long for its row is shortened to the name the
  character goes by (`- TYRION`, `- THE HOUND`).
- 196 quotes from 48 characters in `data.json`, shipped with the plugin:
  nothing to download. Each character has a house and the shorter names they
  go by.
- **Characters** and **Houses** pickers, with how many quotes each brings.
- **Skip crude language**, left alignment, and no repeat of the last 50 quotes
  where it can be avoided.
- `{{game_of_thrones_quotes.quote}}`, `.character`, `.house`, `.block` and
  `.line1` … `.line6`.
