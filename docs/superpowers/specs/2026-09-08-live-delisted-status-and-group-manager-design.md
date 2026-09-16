# Live Delisted Status and Group Manager Design

## Goal

Prevent stale ticker data from being used by Backtest or new positions, while
making existing ticker groups visible and safely manageable.

## Live ticker status

`Listed` and `Delisted` are derived on demand, never persisted. A ticker is
`Listed` exactly when its latest stored trading session equals the latest
stored VN-Index trading session. A missing ticker session or any unequal date
is `Delisted`. When later ingestion brings the ticker up to the current
VN-Index session, it automatically becomes `Listed` again.

The comparison uses one bounded, parameterized aggregate query for every
requested ticker set. VN-Index absence is an explicit availability error: no
ticker is guessed to be Listed or Delisted and the affected operation stops
safely. Existing calendar cleanup remains responsible for removing known
invalid VN-Index sessions before they can become the latest session.

## Backtest and position behavior

Collect performs listing preflight before resolving Lifetime bounds or the
batch common-as-of. Delisted tickers receive a terminal job result of
`skipped`, including their and VN-Index latest dates, and are excluded from
the active ticker set. No artifact is overwritten or removed. Therefore a
stale ticker cannot pull another ticker's shared cutoff backwards.

Validate Signals and Flexible Rulebook preflight the same status and return a
friendly unavailable result for a Delisted ticker. They do not write a
`requires_regeneration` marker: a stale data feed is not proof that the
historical artifact changed. View Signals retains historical artifacts as
read-only evidence.

New Position checks the live status immediately before writing either a
manual P&L-only position or a saved-signal-backed position. A Delisted ticker
is rejected with its two dates. Existing positions remain immutable history.
Validate Positions returns an unavailable row for a Delisted selected position
and continues assessing the remaining Listed positions in the same request.

## Group Manager

Backtest gains a final `Group Manager` tab. It projects one row for each group
member and one explicit empty row for an empty named group. Each member row
shows Group, Ticker, Status, Ticker latest session, and VN-Index latest
session. Filters are group name, ticker text, and Listed/Delisted status; they
only filter the projection and never mutate it.

Group CRUD preserves the existing sidecar JSON ownership:

- Create accepts a valid unique name and zero or more normalized ticker codes.
- Update can rename a group and atomically replace its members; group UUID and
  metadata survive a rename.
- Delete requires a native confirmation dialog and removes only that group's
  JSON metadata.
- Empty named groups remain valid and selectable. Artifacts, positions, and
  other groups are never changed by CRUD.

The existing group-move journal becomes a general atomic directory mutation:
after writing its `after` files, recovery removes `before` paths that are no
longer present. This supports retry-safe create, rename, member replacement,
and delete without a half-renamed or duplicate group.

## Boundaries and errors

No price rows, BIGINT scaling, indicator calculations, rulebook metrics,
artifact schema, or `common_queries.py` are changed. A missing/invalid
VN-Index latest session is shown as an availability error and blocks the
operation; it is not relabelled as delisting.

## Verification

Tests cover exact-date Listed detection, stale/missing ticker Delisted
detection, VN-Index availability failure, batch exclusion before Lifetime
bounds, friendly validation results without artifact mutation, manual and
saved new-position blocking, mixed position-risk validation, Group journal
rename/delete recovery, and Group Manager filtering/CRUD UI behavior.
