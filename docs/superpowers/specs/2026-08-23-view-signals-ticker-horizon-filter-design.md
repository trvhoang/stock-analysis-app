# View Signals Ticker and Horizon Filters Design

## Goal

Allow a reader to narrow the shared read-only View Signals table by ticker and
horizon without changing catalog data, artifacts, jobs, or saved positions.

## UI contract

- Render filters directly below the `View Signals` heading and above the
  existing table.
- `Ticker` is an optional text input. It normalizes committed input to
  uppercase and performs a case-insensitive partial match against the projected
  `Ticker` column.
- `Horizon` is a select box with `Both`, `Swing`, and `Mid-term`; `Both` is the
  default. `Swing` and `Mid-term` require the matching projected Horizon value.
- Both filters intersect. Empty filters retain every valid catalog row.
- Warnings remain visible. Terminal and invalid rows remain suppressed exactly
  as before.

## Boundaries

The filters are an in-memory View Signals projection only. They do not mutate
schema-4/V3 JSON, the catalog, jobs, validation results, positions, SQL,
prices, dependencies, Docker, or credentials.
