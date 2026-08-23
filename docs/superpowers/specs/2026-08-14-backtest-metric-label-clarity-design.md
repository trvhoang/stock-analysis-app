# Backtest Metric Label Clarity

## Goal

Remove the misleading `Best by` wording from every Backtest metric label and
put the Validate Signals summary's identity and current-match fields first.

## Scope

- Display `Win Rate`, `%Profit`, and `Sharpe` in Collect Signals result
  headings/download text, Validate Signals summary/detail labels, and saved
  signal-set choices used by Current Positions.
- Keep canonical metric IDs (`win_rate`, `profit`, `sharpe`), artifact
  structure, grouping, validation, and persistence unchanged.
- Set Validate Signals default summary order to: Identity: Ticker, Identity:
  Metric, Match: Level %, Match: Classification. Preserve the order of every
  remaining default column.

## Design

The existing page and saved-signal catalog each own a small metric-ID-to-label
map. Replace only their display strings. This is deliberately not a shared
abstraction: the existing maps are private to separate modules, and moving
them would widen a presentation-only change without reducing duplication.

The Validate Signals table derives its displayed order from
`_SUMMARY_DEFAULT_COLUMNS`. Move the two existing Match fields directly after
the two existing Identity fields. The column names and visibility behavior stay
unchanged; only their default order changes.

## Validation

Add regressions that assert the plain multi-metric labels in page rendering and
saved-signal choices, assert absence of `Best by` in Backtest production
modules, and assert the first four default summary columns. Run the focused
Backtest page/catalog Docker test gate afterward.

## Constraints

- Presentation-only: no database, SQL, artifact, pricing, signal, position,
  dependency, Docker, credential, or commit changes.
- Preserve the user's existing dirty worktree outside these files.
