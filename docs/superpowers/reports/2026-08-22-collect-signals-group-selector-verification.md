# Collect Signals Group Selector Verification

**Date:** 2026-08-22

## Result

Collect Signals now defaults Group to `N/A`. `New group…` accepts manual
tickers and passes the normalized name to the unchanged batch pipeline, which
remains the only group writer at Run Backtest. Existing groups disable Tickers
and run exactly their resolved members. A duplicate new name is rejected.

## Evidence

- RED: both selector-route AppTests failed before implementation because no
  `Group` selector existed.
- GREEN: existing-member locking and new-group submission AppTests passed.
- Docker: `python -m unittest tests.test_backtest_page -v` passed **29/29**.
- Docker: `python -m compileall -q pages/backtest_lab.py
  tests/test_backtest_page.py` passed.

No SQL, persistence, raw-BIGINT scaling, artifact, dependency, Docker, or Git
state changed. Existing group persistence is unchanged.
