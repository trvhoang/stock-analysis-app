# Validate Signals Match-Classification Filter — Verification

Date: 2026-08-14

## Delivered Behavior

Validate Signals now provides local `Match classification` filtering for stored
results:

- Observe, Nearly match, and Closely match are all selected by default.
- Filtering narrows available signal-summary rows and metric detail panels.
- Clearing every option hides result rows and displays `Select classification`.
- Changing the filter never submits validation; it is excluded from request
  identity and reads the already-stored result only.

The UI stores display labels in the Streamlit widget and converts them through
one fixed mapping to existing stored values: `observe`, `nearly_match`, and
`closely_match`. The new widget key avoids applying an earlier temporary raw
widget state to the display-label control.

Unavailable metric feedback remains a warning rather than becoming a false
classification option. Variant/artifact errors do not become filter options.

## Test-First Evidence

New AppTests:

- `test_validate_filter_limits_results_to_selected_classification`
- `test_validate_filter_empty_selection_hides_results`

Initial RED command:

```text
docker exec stock_app python -m unittest \
  tests.test_backtest_page.BacktestPageTests.test_validate_filter_limits_results_to_selected_classification \
  tests.test_backtest_page.BacktestPageTests.test_validate_filter_empty_selection_hides_results
```

Result: both failed because no `Match classification` control or empty-state
message existed.

The first implementation used a Streamlit `format_func` over raw option
values. Full-page AppTests exposed a Streamlit 1.32 widget-state incompatibility
on later reruns (`ValueError: 'observe' is not in list`). The test was corrected
to select displayed labels, then made RED again against the raw option list.
The final implementation uses display labels as options plus a raw-value map;
the focused AppTests passed 2/2 and the complete page suite passed 50/50.

## Final Verification

```text
docker exec stock_app python -m unittest \
  tests.test_backtest_persistence tests.test_backtest_signal_catalog \
  tests.test_backtest_pipeline tests.test_backtest_job_runner \
  tests.test_backtest_worker tests.test_backtest_page
Ran 100 tests ... OK

docker exec stock_app python -m compileall backtest_engine pages
Exit 0

docker exec stock_app python -c "... http://127.0.0.1:3501/_stcore/health ..."
200 ok
```

The focused gate emits the expected synthetic failure traceback from the
job-runner fixture but exits successfully. Streamlit dependency `SyntaxWarning`
messages are pre-existing third-party warnings.

## Implementation Review

| Area | Result |
| --- | --- |
| Logic | Pass — labels map only to known stored classifications; filter does not modify request identity. |
| SQL/data integrity | Not applicable — no SQL, persistence, replay, or price conversion changed. |
| Performance | Pass — no query or validator call occurs when the filter changes. |

No dependency or commit was created.
