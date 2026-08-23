# Backtest Page Run Variants Verification

Date: 2026-08-04

## Scope

`app/pages/backtest_lab.py` now presents one required Horizon radio, an
unchecked VN-Index checkbox, and page-only orchestration for one no-theme job
or two sibling jobs (no-theme then VN-Index `AND`). While any persisted status
is queued, running, or unreadable, all request-defining controls and Run are
disabled. Terminal errors/results render before a later explicit request can
replace the stored job list.

No engine, job-runner, persistence, SQL, BIGINT, Docker, dependency, or
credential behavior changed.

## TDD Evidence

1. RED: the new tuple-builder and multi-submit tests failed as expected because
   `build_backtest_configs` and `submit_run_requests` did not exist (2 failures).
2. GREEN: the helper contract passed 4/4 focused tests: exact no-theme tuple,
   no-theme then fixed-AND tuple, required Horizon, and submit-only fan-out.
3. RED: page AppTests failed as expected because Horizon remained a selectbox,
   stored jobs were ignored, and terminal errors were not rendered (3 failures).
4. GREEN: `tests.test_backtest_page` passed 9/9 after the radio, checkbox,
   multi-job state, active lock, and terminal unlock changes.

## Final Validation

Command:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_signal_combos tests.test_backtest_rolling_window tests.test_backtest_trade_execution tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence tests.test_backtest_early_warning tests.test_backtest_vnindex_theme tests.test_technical_analysis_indicators tests.test_technical_dimension_grouping tests.test_technical_dimension_scoring tests.test_technical_snapshot tests.test_technical_visualization_ui
```

Result: PASS — 124 tests in 3.211 seconds. Streamlit emitted its existing
direct-`unittest` session-state/browser-use warnings; no test failed.

Additional checks:

- Temporary-output `py_compile` of `app/pages/backtest_lab.py`: PASS. The
  normal host `compileall` cannot write Docker-created
  `app/pages/__pycache__`; this is a host cache-permission issue, not a syntax
  failure.
- `git diff --check`: PASS apart from existing CRLF conversion warnings.
- Protected boundary diff (`common_queries.py`, data preparation, credentials,
  Docker, and `IMPLEMENTED.md`): empty.
- Legacy-selector/source scan: no `THEME_MODE_OPTIONS`, singular config helper,
  singular submit helper, or old `backtest_job_id` remains in the Backtest page
  or its tests.
- Independent read-only review: no issues.
- Commit head remains `ebf2a4b add unit test, export ticker price history (#10)`;
  no commit was created.

## Known Existing Limitation

Full Docker discovery is not rerun for this page-only enhancement. The prior
documented result remains 194/195 due to the pre-existing top-level `scripts`
package import/mount issue in `tests/test_trend_classification_probe.py`.
