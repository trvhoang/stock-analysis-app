# Validate Signals Position-Action Filter Verification

- Layout: Tickers and Ticker group are the first row; Monitoring
  classifications, Position actions, and Validate are the second.
- Position actions options: `ALL`, `can BUY`, `expired BUY`, `can SELL`,
  `HOLD`; `ALL` is default.
- Action and classification filters intersect against the latest cached
  validation result only. No filter change replays validation; no cache renders
  no results.
- Final Docker page suite passed 37 tests; `pages/backtest_lab.py` compilation
  passed.
- No SQL, artifact, job, position, action-rule, price, dependency, Docker,
  credential, or Git change.
