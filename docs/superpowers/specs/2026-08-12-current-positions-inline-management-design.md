# Current Positions Inline Management Design

**Date:** 2026-08-12

## Goal

Make Current Positions compact and safe to manage: filter, sort, refresh,
create, edit, close, reopen, and permanently delete a single position without
leaving the table context.

## Scope

- `app/pages/backtest_lab.py` Current Positions tab only.
- Atomic position changes through both existing legacy tuple histories and
  generic manual histories.
- Focused `unittest`/Streamlit AppTest coverage.

Out of scope: database schema/queries, signal creation or validation logic,
automatic trading, multi-BUY/SELL fills, history archive/undo, new packages,
and protected files.

## Platform Decision

The deployed Streamlit version is `1.32.0`. It has `st.popover`, but no
`st.dialog`; therefore, New Position uses a native popover rather than a
modal dialog or a dependency upgrade.

## Controls

The first control row contains:

1. A free-text ticker filter limited to three characters. Its session-state
   callback uppercases the value as it is entered; a non-empty value matches
   the three-character ticker exactly.
2. A multi-select State filter with `OPEN` and `CLOSED`, defaulting to `OPEN`.
3. A `New position` popover trigger.

The second control row contains:

1. A refresh-icon button with accessible text/help. It discards the cached
   overview and reloads position records, latest prices, P&L, hold sessions,
   and status data only after an explicit click.
2. `Sort by`: Open date, Profit, Profit %, or Hold time.
3. Direction: `ASC` or `DESC`.

Default ordering is Open date ascending (oldest first). Empty P&L/hold values
sort after valid values regardless of direction.

## New Position Popover

The popover uses normal widgets, not `st.form`, so a changed ticker reruns the
page and refreshes the optional saved-signal-set choices before Add position.

| Row | Fields |
| --- | --- |
| 1 | Ticker (required, three-character uppercase), Saved signal set (optional) |
| 2 | BUY price (required, `k`), BUY date (required), Volume (optional; minimum 100, step 100) |
| 3 | SELL price (optional, `k`), SELL date (optional) |

The action button is `Add position`. SELL price and date must be both supplied
or both blank. A selected saved signal set still performs the existing
read-only replay and freezes the same ATR/risk and max-hold basis before the
atomic write. A no-signal position remains P&L-only.

All Current Positions volume inputs, including a pending Validate Signals BUY
draft and table editor, use the same minimum 100/step 100 presentation rule.

## Inline Table Editing

`st.data_editor` replaces per-position edit forms. A checkbox selects exactly
one row for a save or delete operation. The editor permits changes only to:

- State (`OPEN` or `CLOSED`)
- BUY price and BUY date
- SELL price and SELL date
- Volume

Ticker and Saved signal set are immutable. Current price, profit, profit %, and
hold time are derived values and remain read-only. Audit Open time and Closed
time remain read-only, display `DD/MM/YYYY`, and are not trade-date fields.

State transitions are validated atomically per selected record:

- `OPEN` to `CLOSED` requires both SELL price and SELL date, sets the current
  Ho Chi Minh close audit timestamp, and retains the BUY audit timestamp.
- `CLOSED` to `OPEN` clears SELL price, SELL date, close audit timestamp, and
  SELL reason. It first enforces the existing one-OPEN-position rule for a
  saved signal set across legacy and manual histories.
- Editing a BUY price recalculates frozen SL/TP from the same frozen ATR.
- Editing BUY/SELL dates recalculates hold sessions on the next reload.

Every successful add, save, close, reopen, or delete clears the cached overview
and reruns so the displayed P&L, profit %, hold time, and State are refreshed.

## Permanent Delete

`Delete position` applies only to the exactly selected row. The first click
opens an in-page warning containing ticker, saved-set label, state, BUY/SELL
prices, trade dates, and quantity. No file is changed at this step.

Only `Confirm permanent delete` removes the precise ID from its current manual
or legacy JSON history, using the existing atomic-write pattern. The UI shows a
spinner while the deletion runs, then refreshes. There is no archive or undo.

## Persistence Changes

Add small, source-specific atomic update/delete functions to
`manual_position_store.py` and `position_store.py`; route them by the existing
`position_locator`. They validate the complete final record before using the
existing `_write_history` atomic replace. No position changes its ticker or
saved-signal association.

## Validation

Tests must prove:

1. Ticker uppercasing, three-character filtering, default Open-date ascending
   sort, all requested sort keys/directions, and refresh cache invalidation.
2. New Position required/optional fields, volume minimum/step, reactive
   saved-set choices, and incomplete SELL rejection.
3. Exact one-row inline save with date-only audit display and fresh derived
   values after write.
4. OPEN-to-CLOSED and CLOSED-to-OPEN transitions, including SELL-field rules,
   risk recalculation, and cross-history saved-set OPEN protection.
5. Permanent delete confirmation: no removal before confirmation, exact
   legacy/manual record removal after confirmation, and no unrelated mutation.

## Constraints

- Keep raw BIGINT prices in storage; use existing `k` UI conversion helpers.
- Use HCM timezone for lifecycle audit timestamps.
- Do not modify `app/common_queries.py`, ingestion scaling, credentials,
  Docker files, or dependencies.
- Do not create a commit; the user manages commit history.
