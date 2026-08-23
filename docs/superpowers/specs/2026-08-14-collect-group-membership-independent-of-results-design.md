# Collect Group Membership Independent of Backtest Results — Design

**Date:** 2026-08-14  
**Status:** Verified

## Goal

A named Collect Signals Group owns every requested ticker regardless of its
backtest outcome. Validate Signals continues to skip a named-Group ticker that
has no readable, nonempty saved signal artifact and continues validating the
remaining eligible tickers.

## Current Behavior

`run_backtest_batch_pipeline()` adds a ticker to its Group only after a final
attempt writes one or more certified signal sets. An empty result is therefore
not a Group member. Validate already calls `tickers_with_no_saved_signal()`
before its sequential validation loop, then displays its skipped ticker list.

## Approved Behavior

### Collect Signals

1. A selected named Group adds every ticker in the validated batch input before
   the VN-Index preflight or any ticker backtest starts.
2. Membership is independent of no-signal results, ticker-run failures,
   deferred-retry failures, and VN-Index preflight failures.
3. Blank or `N/A` Group remains no membership operation.
4. The Group update is one atomic JSON update for the whole requested ticker
   list. A Group-write error leaves the previous Group JSON recoverable and
   aborts the entire batch before a backtest begins; it must not expose a
   partial list of the requested tickers.
5. Membership remains add-only. Existing named Group memberships, metadata,
   Group IDs, slugs, and empty Group JSON files are preserved.
6. Group JSON ticker order is not semantic: readers accept an unordered,
   uppercase, unique ticker list and return a sorted deterministic tuple.
   Writers continue emitting sorted members; duplicate or non-uppercase stored
   tickers remain invalid.

### Validate Signals

1. Resolving a named Group uses its Group JSON ticker list, including tickers
   that have no signal artifact.
2. Before validation, absent, empty, malformed, or otherwise unreadable saved
   signal artifacts are skipped. Validation continues sequentially for every
   remaining eligible ticker.
3. The existing final skipped-ticker display remains the user feedback. There
   is no validation job submission, artifact write, or position change for a
   skipped ticker.

## Architecture

`backtest_engine.result_store` gains one small batch Group writer that reuses
the existing Group journal and atomic replacement protocol to update one Group
JSON with the full requested ticker set. The existing single-ticker writer
becomes a compatibility wrapper over that behavior. `run_backtest_batch_pipeline`
calls the batch writer once at pipeline entry, then removes all result-gated
and retry-gated Group writes. `backtest_lab` and `signal_catalog` retain their
existing validation skip path; regression tests document it.

## Constraints

- JSON Group storage only; no database or SQL changes.
- No new dependency, UI control, artifact schema, position, replay, or signal
  logic change.
- Preserve uppercase ticker and Group-name normalization.
- Preserve append-only multi-Group membership and `N/A` as derived no-group.
- No change to BIGINT price storage/display scaling, Docker files,
  credentials, or commit history.

## Test Matrix

| Case | Expected result |
| --- | --- |
| Named Group + empty signal result | Every requested ticker is a Group member; ticker result remains done/empty. |
| Named Group + ticker or theme failure | Every requested ticker remains a Group member; backtest result records its failure. |
| Named Group + Group write failure | Batch aborts before theme preflight/ticker execution; old Group JSON remains recoverable. |
| Blank or `N/A` Group | No Group JSON membership is created or changed. |
| Named Group with a ticker without saved signals | Validate skips that ticker, validates eligible siblings, and reports the skipped ticker. |
| Unordered valid Group JSON | Validate reads the Group without rewriting it and resolves sorted members. |

## Non-Goals

- Removing ticker membership, editing Group metadata, or changing Group UI.
- Creating empty signal artifacts for no-signal backtests.
- Changing how theme/no-theme variants are certified or replayed.
