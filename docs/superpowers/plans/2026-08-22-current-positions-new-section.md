# Current Positions New Position Section Plan

**Goal:** Move New Position into collapsed section above filters with requested
live field layout.

## Task 1: TDD UI move

- [ ] Add page test: `st.expander("New Position", expanded=False)` exists;
  no New Position popover; source field columns are `(1, 1, 2)`, `(1, 1, 1, 1, 1)`;
  labels omit `New`/`(k)`; expander appears before filter controls.
- [ ] Run RED: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [ ] Rename `_render_new_position_popover` to section renderer; use expander,
  requested field rows, existing widget keys/live candidate lookup, and move
  call before toolbar in `_render_positions`.

## Task 2: Ticker-driven saved-set refresh

- [x] Add a focused failing page test proving that committing a ticker invokes
  the injected validation replay, uppercases the ticker, and exposes only its
  BUY-eligible saved-set label.
- [x] Run RED: `docker exec stock_app python -m unittest
  tests.test_backtest_page.BacktestPageTests.test_new_position_refreshes_saved_sets_for_committed_ticker -v`.
- [x] Add a New-Position-only validation session-state key and a ticker-change
  callback. The callback uppercases the ticker, resets the saved-set control to
  `Manual P&L only`, and stores one injected `validate_saved_signals()` result
  for that ticker without altering Validate Signals batch state.
- [x] Pass the existing engine, signal directory, positions directory, and
  validation dependency through the Current Positions renderer; use the
  isolated result for candidate lookup. Display a concise explanation when
  saved artifacts replay but none are BUY-eligible, or when replay fails.
- [x] Run GREEN: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [x] Run compilation: `docker exec stock_app python -m compileall -q
  pages/backtest_lab.py tests/test_backtest_page.py`.
- [x] Run GREEN: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.

## Task 3: Verify

- [x] Run page suite and `docker exec stock_app python -m compileall -q pages/backtest_lab.py`.
- [x] Review no persistence/SQL/scaling change; update status/report. No Git.
