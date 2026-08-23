# Backtest Batch Input and Saved-Signal Persistence

## Goal

Complete the pending Backtest display clarity work, accept up to fifteen
sequential Collect Signals tickers, and preserve saved signals unless a new
run produces at least one valid certified signal set.

## User-visible behavior

- Every Backtest metric label is plain: `Win Rate`, `%Profit`, or `Sharpe`.
- Validate Signals summary defaults to Ticker, Metric, Match Level, and Match
  Classification first. All following default columns retain their existing
  order.
- In both View Signals popovers, the ticker filter visibly reads `Ticker` and
  the Group filter reads `Ticker Groups`; both filters retain their existing
  behavior and side-by-side layout.
- Collect Signals accepts one through fifteen comma/space-separated tickers,
  uppercases them, removes duplicates while retaining first-entered order, and
  runs them one at a time. Manual Validate Signals ticker input remains one
  through five values.
- A result with one or more certified signal sets atomically creates or
  overwrites that ticker/theme's current saved artifact. A zero-set result does
  not create an artifact and does not overwrite a prior artifact.

## Architecture

`BacktestBatchConfig` owns the maximum Collect batch size because it is the
worker request boundary. `parse_batch_tickers()` receives an explicit maximum;
Collect passes the batch maximum and Validate retains its existing default.
The existing runner already visits tickers sequentially, so no concurrency,
job-status, or retry redesign is required.

The existing artifact catalog is the saved-signal list. There is no separate
list to append: `save_certified_signals()` atomically replaces the current
per-ticker/per-theme file. `_run_variant()` will call it only when certification
returns a nonempty set, so current valid artifacts remain untouched by an empty
rerun. No-theme and VN-Index AND artifacts remain independent.

## Failure and data rules

- Existing batch failures, deferred per-ticker retry, and shared VN-Index
  preflight remain unchanged.
- If one theme variant is nonempty and its sibling has no certified set, only
  the nonempty variant is saved; the sibling's prior artifact remains intact.
- A new ticker with no valid set gains no artifact.
- Group assignment remains based on whether at least one variant produced a
  nonempty set, as it is today.

## Verification

Tests prove rendered summary ordering/labels, visible popover labels, 15-item
Collect parsing, unchanged five-item manual Validate cap, sequential batch
ordering, and byte-preservation of a prior artifact when certification is
empty. Docker Backtest tests, compilation, and a final source audit validate
the result.

## Constraints

- Do not modify canonical metric IDs, strategy logic, signal math, replay,
  positions, SQL, BIGINT price handling, dependencies, Docker, credentials, or
  commit history.
- Preserve all existing dirty worktree changes outside this task.
