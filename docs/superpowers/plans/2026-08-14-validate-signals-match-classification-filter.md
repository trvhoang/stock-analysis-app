# Validate Signals Match-Classification Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement task-by-task. Steps use checkbox
> syntax for tracking.

**Goal:** Filter stored Validate Signals summaries and details by selected match
classification without triggering another validation run.

**Architecture:** Keep classification state in one Streamlit multi-select in
`_render_validate_tab`. Pass its selected stored values into
`_render_validation_result`, which supplies only matching available metric
results to the existing summary and detail renderers. Empty selection stops
only successful result rendering and displays the approved message.

**Tech Stack:** Python 3.12, Streamlit AppTest, pandas.

## Global Constraints

- Stored values are exactly `observe`, `nearly_match`, and `closely_match`;
  UI labels are Observe, Nearly match, and Closely match.
- Default selects all classifications; empty selection displays `Select
  classification` and no result rows/detail panels.
- The filter does not enter validation request identity and never calls the
  validator itself.
- Preserve SQL, artifacts, positions, replay, BIGINT scaling, dependencies,
  Docker, credentials, and commit history.
- User manages commits; do not create one.

---

### Task 1: Local filter and filtered result rendering

**Files:**

- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Interfaces:**

- Consumes: existing `match_classification` strings inside available validation
  metric results.
- Produces: `_render_validation_result(..., selected_classifications)` renders
  only selected available metrics.

- [x] **Step 1: Write failing AppTests**

  Add an AppTest using `_validation_payload()` that validates saved signals,
  checks the default `Match classification` options, selects only `Observe`,
  and asserts the summary/detail output retains only Sharpe. Add a second
  AppTest that clears the selection and asserts `Select classification` with no
  signal-summary expander or metric-detail expander.

- [x] **Step 2: Run RED tests**

  Run:

  ```text
  docker exec stock_app python -m unittest \
    tests.test_backtest_page.BacktestPageTests.test_validate_filter_limits_results_to_selected_classification \
    tests.test_backtest_page.BacktestPageTests.test_validate_filter_empty_selection_hides_results
  ```

  Expected: fail because `Match classification` does not exist.

- [x] **Step 3: Implement minimal filter**

  Add ordered classification labels, local multi-select state, one empty-state
  message, and a selected-classification argument to the validation result
  renderer. Build a mapping containing only available metrics whose stored
  classification appears in that selected tuple; render the existing summary
  and detail UI from that mapping.

- [x] **Step 4: Run GREEN tests**

  Re-run Step 2. Expected: both tests pass.

- [x] **Step 5: Verify and document**

  Run the complete `tests.test_backtest_page` module, the focused Backtest
  module gate, and `python -m compileall backtest_engine pages` in `stock_app`.
  Run the implementation review: logic/UI state pass; SQL and data integrity
  not applicable; no added query or repeated validation work. Record exact
  evidence in a verification report, mark this task complete in FOCUS, and
  move the WIP item to Recently Completed in current-status.
