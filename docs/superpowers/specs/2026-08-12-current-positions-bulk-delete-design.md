# Current Positions Bulk Delete UI Design

**Date:** 2026-08-12

## Goal

Make multi-position deletion safe and explicit while rearranging the Current
Positions controls into the requested three-line layout.

## Scope

- `app/pages/backtest_lab.py` Current Positions presentation and routing only.
- Existing manual and legacy atomic JSON delete functions only; no schema,
  SQL, signal, price-scaling, or dependency change.
- Focused `unittest` and Streamlit AppTest coverage.

## Layout

1. Line 1: Ticker filter, Position state, Sort by, Direction.
2. Line 2: native `New position` popover trigger and refresh icon.
3. Line 3: `Delete position` button, disabled until at least one currently
   visible table row is selected.

The existing Save changes action remains with the table and still requires
exactly one selected row. Multi-selection is therefore delete-only.

## Selection

- Retain the table's `Select` checkbox column for individual rows.
- Add a `Select all visible` checkbox immediately above the table. It applies
  only to rows after the current ticker/state filters and sort order.
- Page-owned session state records selected IDs. The displayed editor frame is
  rebuilt from that state, so the select-all checkbox and individual row
  changes stay synchronized across reruns.
- A filter change discards selections that are no longer visible. Refresh,
  add, successful save, and any delete result clear all selection state.
- The delete button is disabled when the visible selected-ID set is empty.

## Batch Delete

1. The user clicks enabled `Delete position`.
2. The page resolves every selected overview row and prevalidates every
   immutable locator before any record is deleted.
3. One confirmation view lists all selected positions, including ticker,
   state, BUY/SELL price and date, volume, and saved signal set.
4. `Confirm permanent delete` deletes the selected IDs in their stable table
   order. Each record remains an exact, source-specific atomic delete.
5. On the first failure, stop immediately. Do not attempt remaining selected
   records and do not roll back records already deleted in other history files.
   Clear cached overview/selection and show the exact deleted count and failed
   record/error after reload.
6. If every delete succeeds, clear cached overview/selection, reload, and show
   `N positions permanently deleted.` for two seconds, then remove the message
   with a rerun.

There is intentionally no cross-file transaction: existing histories are
atomic per file. Prevalidation minimizes, but cannot eliminate, a later I/O
failure between records.

## Safety Rules

- A changed filter, refresh, or changed selection cancels any pending batch
  confirmation.
- Ticker and saved signal set remain immutable. The change does not expand
  Save changes beyond its existing exactly-one-selected lifecycle behavior.
- Direct Current Positions actions remain ungated by Validate Signals advice.
- Raw prices remain BIGINT at rest and use the existing `k` conversion helpers
  at UI boundaries.

## Validation

Tests must prove:

1. The requested three-line control order and disabled default delete button.
2. Individual and all-visible selection synchronisation; filtered-out rows are
   never retained for a delete.
3. Batch locator prevalidation happens before the first writer call.
4. A successful mixed manual/legacy batch deletes each requested exact ID and
   no unrelated record.
5. A failure stops the batch, leaves later records untouched, refreshes the
   display, and reports the partial result without a success banner.
6. A success message is visible for two seconds before cleanup.

## Constraints

- No commit: the user manages commit history.
- No new dependencies or Streamlit upgrade.
- Do not modify protected SQL, BIGINT scaling, credentials, Docker, or
  dependency files.
