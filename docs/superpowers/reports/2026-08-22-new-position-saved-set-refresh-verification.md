# New Position Saved-Set Refresh Verification

**Date:** 2026-08-22

## Result

Committing a New Position ticker uppercases it, resets the selected saved set,
and runs one isolated current validation replay. Only replayed `buy_eligible`
schema-4 sets appear in the dropdown. Validate Signals batch state is not
changed.

FPT has six saved schema-4 sets. A read-only live replay found all six blocked
as `audit_ineligible`; the dropdown therefore correctly retains `Manual P&L
only` and explains the block.

## Evidence

- RED: `test_new_position_refreshes_saved_sets_for_committed_ticker` failed
  before implementation with `[] != ['FPT']`.
- GREEN: the focused regression passed.
- Docker: `python -m unittest tests.test_backtest_page -v` passed **27/27**.
- Docker: `python -m compileall -q pages/backtest_lab.py
  tests/test_backtest_page.py` passed.

No SQL, persistence, raw-BIGINT scaling, artifacts, dependencies, Docker
configuration, or Git state changed.
