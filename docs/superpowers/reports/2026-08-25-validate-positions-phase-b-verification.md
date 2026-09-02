# Validate Positions Risk — Phase B Verification

**Date:** 2026-08-25  
**Status:** Complete and verified.

## Focused regression evidence

```text
docker exec stock_app python -m unittest \
  tests.test_backtest_position_risk \
  tests.test_backtest_manual_position_store \
  tests.test_backtest_position_overview \
  tests.test_backtest_position_monitor \
  tests.test_backtest_early_warning \
  tests.test_backtest_page -v
```

Result: **68 tests passed** in 1.607 seconds.

```text
docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py
```

Result: pass.

Read-only boundary checks also found no legacy artifact-reader references in
`app/backtest_engine/position_risk.py`, and no `sell_reason`,
`close_manual_position`, or `create_manual_position` reference in that risk
module. The inspected Phase B Python/test files have no trailing whitespace.

## Confirmed contract coverage

- Raw BIGINT risk math, clamping, labels, T+3 activation, and one-decimal
  suggestion display.
- Schema-4 frozen-reference routing, no-signal Swing plus Mid-term routing,
  shared completed-bar handling, and no legacy selection.
- `Updated`, `Unavailable — risk score missing/invalid.`,
  `Failed — assess failed.`, and `T+3 required` presentation paths.
- Current Positions risk invalidation/preservation and CLOSED strike-through.
- Existing SELL monitor remains separate; Phase B does not create SELL actions.

## Boundaries retained

No V3 rulebook, legacy artifact, database-schema, SQL shared-CTE, BIGINT
storage, dependency, Docker, credential, Git, or automatic-trading change was
made by Phase B completion documentation.
