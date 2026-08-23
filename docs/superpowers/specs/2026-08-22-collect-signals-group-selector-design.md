# Collect Signals Group Selector Design

**Date:** 2026-08-22
**Status:** Implemented and verified

## UI

Collect Signals has a native `Group` selector, defaulting to `N/A`. Its choices
are `N/A`, `New group…`, then the current named groups in lexical order.

- `N/A`: Tickers remains editable; no group is assigned.
- `New group…`: Tickers remains editable and a required `New group name` input
  appears. The name must not duplicate an existing group, ignoring case.
- Existing group: Tickers is disabled and displays that group's complete
  current membership. A run uses exactly those members.

## Persistence and boundaries

No new group is written while fields change. On Run Backtest, the existing
batch pipeline atomically creates or extends the named group before work
begins. Existing-group selection must not change membership. No signal,
artifact, SQL, raw-BIGINT, position, dependency, or Docker change is allowed.
