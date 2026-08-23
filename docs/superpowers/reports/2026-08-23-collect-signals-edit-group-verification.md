# Collect Signals Edit Group Verification

- Named Groups now expose Edit Group only in Collect Signals.
- Draft Add/Remove changes persist only through Save Group.
- Save atomically replaces Group members via the existing recovery journal;
  empty named Groups remain selectable.
- Collect layout is Tickers, Group, Edit Group; then Horizon, Range, Run
  Backtest. No edit starts a backtest.
- Docker result-store and page suites passed 39 tests; compilation passed.
- No SQL, price, artifact/job, position, rulebook, dependency, Docker,
  credential, or Git change.
