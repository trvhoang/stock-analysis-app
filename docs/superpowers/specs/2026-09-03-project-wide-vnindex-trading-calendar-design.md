# Project-wide VN-Index Trading Calendar Design

**Status:** approved execution scope

## Goal

Use the presence of a usable weekday `VNINDEX` row as the sole trading-session
calendar for every production technical-indicator input. A ticker row outside
that calendar is excluded before any indicator is calculated. This makes
holidays data-defined without maintaining a separate holiday list.

## Scope and boundaries

Included production paths:

- Schema-5 Backtest collection, batch collection, replay, research, diagnostics,
  and position-risk indicator frames.
- Flexible Rulebook history, features, discovery, qualification, benchmark, and
  current BUY scan.
- Legacy Analyze/API technical snapshots, Suggestion consumers, historical
  technical context, and Technical Analysis Swing/Mid-term snapshots.
- Every Get data transaction performs the approved input-data cleanup and
  calendar-validity check described below before it commits.

Excluded:

- `app/commons/common_queries.py`, its delta CTE, and all statistical delta
  calculations. They are not technical indicator frames and remain protected.
- Price scaling, dependencies, Docker, and any automatic trading action. The
  approved ingestion cleanup below is the sole database-input exception.
- Pure indicator calculators invoked directly by unit tests. They remain
  frame-to-frame functions; every production source adapter supplies a
  calendar-filtered frame.

## Canonical calendar contract

`VNINDEX` is the authoritative calendar only when its rows are usable raw
OHLCV rows, dates are unique, and every row is a weekday. For a requested
inclusive interval, its usable weekday row dates form `sessions`.

- A weekday with no VN-Index row *inside the usable VN-Index interval* is an
  `assumed_non_session`. It may be a real holiday or an ingestion omission; no
  component claims to know which.
- A weekend VN-Index row, duplicate date, invalid OHLCV row, no VN-Index data,
  or no ticker/VN-Index session overlap is **unavailable**. There is no raw
  ticker fallback.
- A ticker weekday row absent from `sessions` is an `outside_calendar` source
  anomaly and is removed before calculations. It is retained only in
  diagnostics/evidence metadata.
- Ticker missing dates *within* `sessions` are not filled. Existing coverage
  and gap policies continue to measure them.
- Missing-session diagnostics retain every affected weekday date. User-facing
  unavailable errors show the complete ISO-date list in an expandable error
  detail, not a misleading claim that all dates are holidays.

The shared value object carries canonical sessions, assumed non-sessions,
source interval, and a deterministic VN-Index calendar fingerprint. Frame
filtering returns a new sorted frame plus excluded ticker dates; it never
mutates raw input.

## Ingestion cleanup and stored-session validity

The five user-acknowledged invalid calendar dates are `2023-08-26`,
`2025-05-04`, `2025-05-11`, `2026-02-07`, and `2026-03-08`. They are
Saturday/Sunday dates, not holidays. After a Get data run has staged and
finalized both downloaded sources, but before its only database commit,
ingestion deletes rows for exactly those five dates across the entire
`trading_data` table. The action is session-wide because a non-trading calendar
date cannot be valid for any ticker, not only `VNINDEX`.

Immediately after that cleanup, ingestion scans every persisted
`trading_data` row for Saturday/Sunday dates. If any invalid session remains,
it reports every date, row count, and ticker list and raises a transaction
error. The cleanup, staged rows, and final insert are then rolled back
together; no partial repair and no invalid refreshed input can commit.

The fixed acknowledged list is intentionally narrow. A future malformed
weekend date is not silently deleted: it stops the refresh and requires an
explicit acknowledgement/change. The UI progress path exposes both cleanup
and validity-check phases. No cleanup runs outside a user-triggered Get data
transaction.

## Calendar clocks and causal semantics

- Daily lookbacks, signal age, ATR, RSI, ADX, volume, Stochastic, OBV,
  Bollinger, moving averages, Alligator, and technical exits advance one row
  per canonical session.
- A Swing `as_of` is the last available canonical ticker session, not wall-clock
  today. Existing latest-common-bar policy remains responsible for multi-source
  Backtest common-as-of selection.
- Completed `W-FRI` Mid-term aggregation first filters daily rows. A holiday
  Friday has no synthetic bar. A weekly label is complete only when the final
  real canonical session that belongs to it has occurred; date labels remain
  `W-FRI` for compatibility.
- Incomplete post-filter warm-up produces existing unknown/insufficient-history
  output. It is not a fabricated signal and not a calendar exception.

## Source identity and persistence

Backtest source fingerprints are calculated from the already calendar-filtered
ticker history and the canonical VN-Index source through common-as-of. Thus a
ticker row on a non-session date, a VN-Index correction, or a calendar change
invalidates changed evidence on fresh replay. Existing schema-5 documents are
not migrated: if fresh evidence differs, replay atomically replaces the
document with the existing `requires_regeneration` marker. If a pre-existing
document has identical filtered source evidence, it remains semantically
valid.

Flexible Rulebook has no current runtime evidence after the approved reset.
Its `HistorySnapshot` fingerprint and quality revision will include the
calendar-filtered source and calendar fingerprint. New primitive cache,
campaign, benchmark, qualification, and activation evidence are therefore
unambiguously calendar-bound. No old Flexible cache or policy is reused.

## Error and UI behavior

Calendar-unavailable technical sources raise a typed, safe error carrying:

- ticker and requested range;
- reason (`missing_vnindex_history`, `invalid_vnindex_weekend_row`,
  `invalid_vnindex_source`, or `no_usable_overlap`); and
- full `assumed_non_sessions` ISO dates for the bounded diagnostic interval.

Backtest persists its normal failed or requires-regeneration terminal document
with that reason. Flexible records a safe ineligible source snapshot. Analyze,
Suggestion, and Technical pages render the safe message and full missing-date
detail rather than calculate a raw fallback.

## Architecture

`commons.trading_calendar` owns the reusable calendar loading, validation,
fingerprinting, filtering, and user-safe error formatting. It uses the existing
`get_engine_with_retry()` supplied engine, `sqlalchemy.text()`, a raw DBAPI
connection, and `%(param)s` bindings. It does not alter protected delta SQL.

Backtest `evidence` exposes compatibility wrappers for its evidence tests and
composes the central calendar into coverage/fingerprinting. Each source adapter
loads ticker and VN-Index raw history once for its required date range, builds
one calendar, filters ticker data, then passes the filtered frame to its
existing indicator pipeline. VN-Index theme calculations use the same validated
calendar source.

## Acceptance criteria

1. No production technical indicator is calculated from a ticker row whose date
   is not a canonical VN-Index session.
2. A missing weekday VN-Index row removes a same-date ticker row and is exposed
   as an assumed non-session; it is never silently counted as a trading bar.
3. Invalid VN-Index calendar/no usable overlap safely blocks output and shows
   all bounded missing weekday dates to the user.
4. Weekend or duplicate VN-Index rows fail closed.
5. Backtest fresh replay regenerates stale evidence; no stale Flexible evidence
   can survive the reset or new quality revision.
6. Daily/weekly calendar behavior, filtering before calculation, no-raw-
   fallback, error detail, persistence invalidation, and every affected
   production adapter have automated coverage.

## Self-critique

The approach deliberately treats a missing weekday VN-Index row as a
non-session, even though it may be an ingestion gap. This follows the approved
definition but is named `assumed_non_session` everywhere so it cannot be
mistaken for verified holiday data. It does not repair missing ticker rows or
pretend a new listing has 15 years of history. It makes output unavailable only
when calendar evidence itself is unusable, avoiding a hidden raw-data fallback
that would violate the rule.
