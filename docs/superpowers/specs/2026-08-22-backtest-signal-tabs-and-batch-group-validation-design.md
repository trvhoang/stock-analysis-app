# Backtest Signal Tabs and Batch Group Validation Design

**Date:** 2026-08-22
**Status:** Approved design — implementation plan pending review

## Scope

Replace the two Backtest `View Signals` popovers with one shared, read-only
tab. Reorganize Collect and Validate inputs. Add group-driven batch validation
without changing rulebook calculation, signal artifacts, position persistence,
or Phase B risk behavior.

## Tab navigation

Backtest has five tabs in this exact order:

1. Collect Signals
2. View Signals
3. Validate Signals
4. Current Positions
5. Validate Positions

There are no `View Signals` buttons or popovers. The shared View Signals tab
keeps current read-only catalog tables, terminal-result display, warnings, and
artifact downloads. Native Streamlit 1.32 tabs remain unchanged; users select
the tab directly.

## Collect Signals layout

Row one has `Tickers`. `Tickers` accepts one through 15 unique symbols
separated by spaces or commas. Row two has `Horizon`, `Range`, `Group`, and
`Run Backtest`. Existing range behavior, batch submission,
no-theme/VN-Index treatment behavior, and job progress remain unchanged.

## Validate Signals layout and group selection

Row one has `Tickers`. Row two has `Monitoring classifications`, `Ticker
group`, and `Validate`.

`Ticker group` choices are `-`, `N/A`, then defined groups. It defaults to
`-`.

- With `-`, `Tickers` remains editable and accepts one through 15 unique
  comma/space-separated symbols.
- With `N/A` or a defined group, the existing group resolver supplies all
  current member symbols as space-separated text. `Tickers` is disabled.
- `N/A` keeps its established meaning: artifact tickers not assigned to any
  defined group.

Manual input and resolved groups use the same symbol normalization. An empty
resolved group reports a user-safe error and performs no validation.

## Batch validation behavior

Manual input validates one through 15 symbols serially. A selected group
validates every resolved member serially in deterministic group order, divided
into consecutive chunks of at most 15 symbols. Chunking bounds one UI batch;
it does not drop members or create a background job.

Each ticker calls the existing validation service independently. A failure for
one ticker produces its own user-visible failure and does not prevent later
tickers from running. Results render in input/resolved order, grouped by
ticker. The persisted session result retains validated candidates by ticker so
Current Positions can create a position from the matching ticker's saved set.

## Boundaries

No change to SQL, raw-BIGINT price handling, V3 rulebooks, artifact schemas,
group storage semantics, position schemas, SELL advice, or risk formulas. No
new dependency, background worker, polling loop, or fifth/sixth workflow
beyond the requested tab reordering.

## Required verification

Tests cover exact tab order, removed buttons/popovers, two-row control layouts,
manual 15-symbol limit, group textbox locking and text,
`N/A` resolution, deterministic 15-symbol chunking, continuation after a
ticker failure, result ordering, and per-ticker saved-set selection.
