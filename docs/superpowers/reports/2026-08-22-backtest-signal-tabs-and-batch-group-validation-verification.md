# Backtest Signal Tabs and Batch Group Validation Verification

**Date:** 2026-08-22

## Delivered

- Five native tabs, ordered Collect Signals, View Signals, Validate Signals,
  Current Positions, Validate Positions.
- One shared read-only View Signals tab; no View Signals button or popover.
- Collect ticker row above Horizon, Range, Group, and Run Backtest row.
- Validate manual input accepts 1–15 comma/space-separated tickers.
- Validate Ticker group defaults to `-`; `N/A` and named groups show a locked
  space-separated ticker list, run every member in serial chunks of 15, and
  continue after individual ticker failures.
- Batch validation state remains keyed by ticker so Current Positions can use
  matching saved-set candidates.

## Verification

| Command | Result |
|---|---|
| `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_validation_advice tests.test_backtest_result_store -v` | 24 passed |
| `docker exec stock_app python -m compileall -q pages/backtest_lab.py backtest_engine/result_store.py backtest_engine/validation_advice.py` | passed; no output |
| View Signals popover and trailing-whitespace searches | no matches |

Streamlit emitted existing third-party invalid-escape `SyntaxWarning` messages;
all project tests passed.

## Implementation review

| Category | Findings | Severity |
|---|---|---|
| Logic | Exact tab order, group locking, serial chunking, failure isolation, and per-ticker saved-set lookup covered. | Pass |
| SQL | No SQL added or changed. | Pass |
| Performance | One existing single-ticker replay per ticker is intentional to preserve requested serial execution; groups resolve once. | Pass |

Known limit: Streamlit 1.32 native tabs are selected directly by the user; no
unsupported programmatic tab activation is used.

No Git action.
