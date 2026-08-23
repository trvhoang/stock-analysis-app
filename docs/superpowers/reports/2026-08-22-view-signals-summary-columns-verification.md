# View Signals Summary Columns Verification

**Date:** 2026-08-22

- View Signals shows only Ticker, Horizon, Theme, Train-test, n, Win rate %,
  Profit %, and Sharpe. Metric cells use stored `train - test` values.
- Terminal schema-4/V3 JSON remains untouched and is not rendered.
- `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v`: 25 passed.
- Compilation passed. Static terminal-render search returned no matches.
- Review: logic/UI projection pass; SQL and artifact behavior unchanged.
- No Git action.
