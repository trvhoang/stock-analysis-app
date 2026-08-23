# Collect Signals Control Row Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put Collect Signals inputs on one row with the approved defaults and preserve request behavior.

**Architecture:** `_render_controls()` remains the sole UI-to-configuration boundary. Four Streamlit columns render ticker, time range, horizon, and theme in that order. The Custom dates and Run backtest button remain below the row, and the existing `build_backtest_configs()` validation remains authoritative.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest with Streamlit AppTest.

## Global Constraints

- Collect Signals only: Validate Signals and Current Positions UI stay unchanged.
- Time range choices remain `5y`, `15y`, `Custom`; default is `15y`.
- Horizon is a dropdown with default `-`, converted to `None` before existing required-horizon validation.
- Collect Signals label is exactly `VN-Index theme`; Validate Signals retains its existing label.
- Preserve job-lock disabled behavior, Custom Start/End fields, config generation, SQL, BIGINT scaling, dependencies, Docker, and commit history.
- No commit: user manages commits separately.

---

### Task 1: Render approved control row

**Files:**
- Modify: `app/pages/backtest_lab.py:2039-2089`
- Modify: `tests/test_backtest_page.py:1277-1304`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Interfaces:**
- Consumes: `_render_controls(disabled: bool) -> tuple[tuple[BacktestConfig, ...] | None, bool]`.
- Produces: the unchanged configuration tuple and Run backtest click state.

- [x] **Step 1: Write failing AppTest expectations**

  Update `test_standalone_page_renders_controls_without_running_engine` to
  require Collect Signals selectboxes in this order:

  ```python
  ["Time range", "Horizon", "Sort by", "Direction", "Saved signal set"]
  ```

  Require `app.selectbox[0].value == "15y"`, no radio widgets, and Collect
  Signals first checkbox label `"VN-Index theme"`. Assert source order in
  `_render_controls()` is ticker, time range, horizon, theme, and contains
  `st.columns(4)`.

- [x] **Step 2: Run focused test to verify failure**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_standalone_page_renders_controls_without_running_engine `
    tests.test_backtest_page.BacktestPageTests.test_running_jobs_disable_request_controls `
    tests.test_backtest_page.BacktestPageTests.test_terminal_failure_renders_error_before_controls_unlock -v
  ```

  Expected: failure because time range defaults to `5y` and Horizon is a radio
  outside a four-column row.

- [x] **Step 3: Implement the smallest UI change**

  In `_render_controls()`, use:

  ```python
  ticker_column, range_column, horizon_column, theme_column = st.columns(4)
  ```

  Render each approved input in its matching column. Use
  `index=TIME_RANGE_OPTIONS.index("15y")` for Time range. Use Horizon options
  `("-", *HORIZON_OPTIONS)`, render human labels, and map `"-"` to `None`
  before existing validation. Render `st.checkbox("VN-Index theme", ...)` in
  the fourth column. Leave Custom dates and Run backtest below the row.

- [x] **Step 4: Run focused and full page tests**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page -v
  ```

  Expected: all page tests pass, including default `15y`, blank Horizon,
  `VN-Index theme`, Custom-date visibility, and disabled controls while jobs
  run.

- [x] **Step 5: Verify and synchronize records**

  Run the complete Backtest package gate, compilation, `git diff --check`, and
  Streamlit health. Review that no persistence, query, or price-conversion path
  changed. Update `FOCUS.md`, `ai-context/current-status.md`, and a verification
  report with test evidence and no-commit confirmation.
