# Validate Signals Date-Only Display and Date-Range Filter Design

Date: 2026-08-14
Status: user-approved

## Goal

Show dates, never timestamps, throughout Validate Signals. Let the user narrow
already-stored validation results by one selected date field and optional
inclusive bounds.

## Display Contract

Within Validate Signals, render every datetime-like display as `YYYY-MM-DD`:

- Signal date;
- Projected exit — date only, without price or exit reason;
- Backtest date-range endpoints;
- Market as-of date;
- open-position BUY date in metric details;
- Certified at in Validate's View Signals popover.

The shared Collect Signals View Signals popover retains its present Certified at
display. Raw artifacts and position data remain unchanged.

## Filter Contract

- Controls share one row with Match classification: Date type, From date, and
  To date.
- Date type options are Signal date and Projected exit date. Signal date is the
  default.
- From/To are blank by default. A supplied From includes equal/later dates; a
  supplied To includes equal/earlier dates.
- A row with no selected date-field value is excluded only when at least one
  date bound is supplied.
- Date and classification predicates combine with AND.
- From later than To displays an error and hides successful result rows. It
  does not rerun validation or alter saved state.

## Boundaries

- All comparison operates on parsed raw values, never formatted display text.
- No database, SQL, artifact, replay, position, trading, price-scale,
  dependency, Docker, credential, or commit change.
- Each new Streamlit widget uses a distinct key.

## Validation

AppTests cover date-only output, Signal date vs Projected exit filtering,
inclusive bounds, empty bounds, and reversed ranges. Existing page/gate tests
protect all other Backtest behavior.
