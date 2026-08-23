# Backtest Engine Verification Report

Updated: 2026-08-03
Branch: `feature/revamp-indicator-add-backtest-engine`
Commit log: unchanged; no commit was created.

## Profile evidence

The first full 15-year profile used ticker `SSI`, Swing horizon, and the
no-background theme on the Docker/PostgreSQL dataset:

| Measure | Result |
| --- | ---: |
| Historical range | 2011-08-04 to 2026-07-31 |
| OHLCV rows | 3,740 |
| Data-quality errors | 0 |
| Data-quality warnings | 17 |
| Indicator-subset/threshold/ADX combos | 270 |
| Six-month rolling windows / one-month stride | 175 |
| Configured workers | 6 |
| Wall time | 234.175 seconds |
| Peak RSS | 262,764 KB (~256.6 MB) |
| Output | `/tmp/backtest-profile/SSI/SSI_signals_no-background-theme.json` |

This is baseline evidence, not a performance target. The current pipeline
executes the combo/window loop serially inside the spawned job worker; future
optimization must preserve the phase contracts and be measured against this
baseline.

## Test evidence

The cumulative focused Docker gate passed 69/69:

- Backtest contracts: 8
- Data quality and indicators: 11
- Combo generation: 4
- Rolling/trade execution: 7
- VN-Index theme: 5
- Validation/certification/persistence: 9
- Early warning replay: 7
- Job runner: 3
- Standalone page/AppTest: 5
- Pipeline composition: 1
- Existing Technical regressions: 9

Full Docker unittest discovery ran 195 tests: 194 passed and 1 errored before
test execution because `tests/test_trend_classification_probe.py` imports
`scripts.validate_trend_classification` while `scripts` is not a package.
This pre-existing issue is outside the backtest changes and remains documented
in `ai-context/current-status.md`.

## Boundary and safety checks

- `compileall` passed for the backtest package and standalone page.
- `git diff --check` passed with existing LF/CRLF normalization warnings only.
- Protected boundary diff was empty for `IMPLEMENTED.md`, common delta-query
  definitions, data-preparation scaling/connection logic, Docker files, and
  credentials. `app/main.py` changed only for the approved Backtest navigation;
  its credential loading pattern is unchanged.
- Backtest package scan found no Streamlit import, UI price scaling, SQL
  duplication, or `iterrows()` use.
- Prices remain raw BIGINT values through the engine; UI rendering is separate
  from persisted/export artifacts.

## Remaining work

The implementation plan is complete through Phase 8. The measured serial
combo/window baseline should guide a later optimization pass; the known full
discovery import error remains outside this feature.
