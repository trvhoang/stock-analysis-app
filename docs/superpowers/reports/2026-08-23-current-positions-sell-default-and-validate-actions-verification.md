# Current Positions SELL Default and Validate Actions Verification

## Completed behavior

- A new OPEN Position renders `SELL date` empty (`None`); an OPEN submission
  still persists no SELL date or price.
- Validate Signals reports `can BUY`, `expired BUY`, `can SELL`, or `HOLD` for
  each available rulebook result.
- A matching OPEN position becomes `can SELL` when its frozen stop-loss or
  take-profit is reached, or when current literal entry fails; otherwise it is
  `HOLD`.
- Validate progress starts at zero and updates after each attempted ticker,
  including failures.
- Monitoring is the first expander line, diagnostics are collapsed by default.

## Test-first evidence

- RED: action tests failed because `_position_action` was absent.
- RED: page tests failed because SELL date defaulted to today, no progress
  callback existed, and the action/collapsed diagnostics UI was absent.
- RED: top-summary order test failed before moving Monitoring above evidence.

## Verification

- `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_validation_advice -v` — final fresh run passed, 40 tests.
- `docker exec stock_app python -m py_compile pages/backtest_lab.py backtest_engine/validation_advice.py` — passed.

The Docker test runner emits two pre-existing `SyntaxWarning` messages from
installed Streamlit package source; project tests passed.

## Implementation review

| Category | Finding | Severity |
| --- | --- | --- |
| Logic | Action labels are read-only, use current replay plus frozen SL/TP, and preserve SELL-over-HOLD precedence. | Pass |
| SQL | No query or database path changed. | N/A |
| Performance | The existing sequential loop has one constant-time progress callback per ticker; no new data fetch or N+1 query. | Pass |
| Comments | New code uses short docstrings; no non-trivial undocumented algorithm remains. | Pass |

No Git action, commit, commit-tree change, SQL, price scaling, artifact/job or
position schema, risk formula, dependency, Docker, credential, or runtime data
change was made.
