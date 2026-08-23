# Validate Signals Date-Only Display and Date-Range Filter — Verification

**Date:** 2026-08-14  
**Status:** Verified

## Delivered

- Validate Signals displays all in-scope datetime values as `YYYY-MM-DD`:
  summary Signal date, Projected exit date, Backtest date range, Market As-of
  date, and metric-detail position BUY date.
- Projected exit no longer includes price or reason.
- Validate's View Signals popover displays Certified at as date-only; Collect
  retains its existing Certified at timestamp display.
- Local controls provide Match classification, Date type, From date, and To
  date. Date type defaults to Signal date. Bounds are optional, inclusive, and
  combine with classification using AND.
- Missing selected-date values remain visible only with empty bounds. A
  reversed range shows `From date must be on or before To date.` and hides
  successful result rows.
- Filtering does not submit validation, alter request identity, or modify
  artifacts, positions, replay data, SQL, prices, or persistence.

## TDD Evidence

Four page tests were added:

1. `test_validate_summary_normalizes_timestamp_values_to_dates`
2. `test_validate_filter_narrows_by_selected_date_type_and_range`
3. `test_validate_filter_rejects_reversed_date_range`
4. `test_validate_view_signals_formats_certified_at_as_date_only`

RED produced the expected four failures: Projected exit contained timestamp,
price, and reason; date controls did not exist; Validate catalog retained a
timestamp. The targeted tests passed after implementation.

## Final Verification

Executed in running `stock_app` container:

```text
python -m unittest tests.test_backtest_page
Ran 54 tests in 8.862s
OK

python -m unittest tests.test_backtest_persistence \
  tests.test_backtest_signal_catalog tests.test_backtest_pipeline \
  tests.test_backtest_job_runner tests.test_backtest_worker \
  tests.test_backtest_page
Ran 104 tests in 9.374s
OK

python -m compileall backtest_engine pages
exit 0

GET http://127.0.0.1:3501/_stcore/health
200 ok
```

The focused gate emits its expected synthetic job-runner traceback during test
execution and existing third-party Streamlit `SyntaxWarning` messages; both
are non-failing test output.

## Implementation Review

| Area | Result |
| --- | --- |
| Display/data separation | Pass — raw values are parsed only for local filter comparison. |
| Filter behavior | Pass — bounds are inclusive, classification/date use AND, and invalid range blocks result rows. |
| Persistence and SQL | Not touched. |
| Scope and dependencies | Pass — Validate-only presentation/filter changes; no dependency added. |
