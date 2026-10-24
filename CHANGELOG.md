# Changelog

All notable changes to this plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version here is the source of truth for `manifest.json` — a test fails if
the two drift apart.

## [Unreleased]

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
