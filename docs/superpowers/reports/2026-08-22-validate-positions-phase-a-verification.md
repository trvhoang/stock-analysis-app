# Validate Positions Phase A Verification

## Status

Complete and verified on 2026-08-22. Phase B remains blocked pending its own
approved deterministic risk contract.

## Delivered

- Four Backtest Lab tabs: Collect Signals, Validate Signals, Current Positions,
  Validate Positions.
- Read-only `View Signals` popovers in Collect Signals and Validate Signals.
- Inert Validate Positions tab: no risk calculation, market/artifact read,
  action, or persistence write.
- Logical-position BUY/SELL groups with schema-4 saved-set identity, UI-only
  `k VND` formatting, local edits, selection, confirmed delete, and stale
  confirmation invalidation.

## Evidence

```text
docker exec stock_app python -m unittest \
  tests.test_backtest_position_overview \
  tests.test_backtest_position_store \
  tests.test_backtest_manual_position_store \
  tests.test_backtest_position_monitor \
  tests.test_backtest_page -v
```

Result: 41 passed.

`docker exec stock_app python -m compileall -q backtest_engine
pages/backtest_lab.py` passed. A trailing-whitespace scan passed. Git checks
were intentionally not run under the user's no-Git instruction.

Two Streamlit 1.32 dependency `SyntaxWarning`s (`invalid escape sequence`) were
observed; no project test failed.

## Boundary Review

No V2 artifact reader/fallback, risk formula, risk write, auto-SELL, real-time
path, SQL change, BIGINT storage change, dependency change, Docker change, or
Git action was added.
