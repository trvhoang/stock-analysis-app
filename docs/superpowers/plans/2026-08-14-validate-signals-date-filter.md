# Validate Signals Date-Only Display and Date-Range Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement task-by-task. Steps use checkbox
> syntax for tracking.

**Goal:** Render date-only Validate Signals values and filter stored result rows
by Signal date or Projected exit date plus optional inclusive bounds.

**Architecture:** Use one date parser/display helper in `backtest_lab.py`. Keep
raw values in validation results; pass a selected raw date field and date bounds
from `_render_validate_tab` to `_render_validation_result`, then filter metric
results before summary/detail rendering. Give the shared catalog renderer an
explicit date-only flag for Validate only.

**Tech Stack:** Python 3.12, pandas, Streamlit AppTest.

## Global Constraints

- Date display is exactly `YYYY-MM-DD`; Projected exit has no price/reason.
- Date type defaults Signal date. Bounds default blank, are inclusive, and
  combine with Match classification using AND.
- From later than To shows an error and hides successful result rows.
- Filter changes never submit validation or alter request identity.
- Do not change Collect View Signals Certified at formatting.
- Preserve SQL, artifacts, positions, replay, BIGINT scaling, dependencies,
  Docker, credentials, and commit history. User manages commits.

---

### Task 1: Date-only display and local filtering

**Files:**

- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Interfaces:**

- Consumes: `current.signal_date`, `current.exit_date`, and existing summary
  maps containing available metrics.
- Produces: `_render_validation_result` accepts date field/bounds and renders
  only metrics matching both active filter categories.

- [x] **Step 1: Write failing tests**

  Add a unit assertion that `_summary_row()` renders ISO timestamps as date-only
  values and Projected exit as its date alone. Add AppTests that select Signal
  date or Projected exit date, apply inclusive From/To bounds, and assert only
  matching metric summary/detail results render. Add a reversed-range AppTest
  asserting the error and no summary expander.

- [x] **Step 2: Run RED tests**

  Run the targeted new `BacktestPageTests` methods in `stock_app`.
  Expected: fail because Projected exit includes extra values and date controls
  do not exist.

- [x] **Step 3: Implement minimum change**

  Add date parser/display helpers; normalize Validate-only display values;
  add local controls and inclusive/reversed bound behavior; filter available
  metrics by the selected raw date field before existing summaries/details.
  Pass the date-only flag only from Validate's View Signals popover.

- [x] **Step 4: Run GREEN tests**

  Re-run the targeted new tests. Expected: pass.

- [x] **Step 5: Verify and document**

  Run `tests.test_backtest_page`, the focused Backtest module gate, and
  `python -m compileall backtest_engine pages` in `stock_app`; check the live
  Streamlit health endpoint. Run implementation review, create a verification
  report, mark FOCUS complete, and move WIP to Recently Completed.
