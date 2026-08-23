# Backtest Metric Label Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `Best by` from every Backtest metric display and bring the
Validate Signals table's current-match columns beside its identity columns.

**Architecture:** Change the two existing module-private display-label maps,
not canonical metric IDs or persisted artifacts. Reorder only the existing
`_SUMMARY_DEFAULT_COLUMNS` tuple; the summary renderer already consumes that
tuple unchanged.

**Tech Stack:** Python 3.12, Streamlit, unittest, Docker.

## Global Constraints

- Presentation-only: do not alter metric IDs, JSON artifacts, replay,
  positions, SQL, BIGINT price behavior, dependencies, Docker, credentials, or
  commit history.
- Preserve all currently dirty user changes outside this task.
- No commit: the user manages commit history.

---

### Task 1: Lock the visible-label and table-order contract

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `tests/test_backtest_signal_catalog.py`

**Interfaces:**
- Consumes: `METRIC_TITLES`, `_SUMMARY_DEFAULT_COLUMNS`,
  `_group_summary_rows()`, `render_result_artifact()`, and
  `list_saved_signal_options()`.
- Produces: regression coverage for plain metric labels and first-four-column
  default ordering.

- [ ] **Step 1: Write the failing tests**

  Add expectations for `Win Rate, %Profit`, `Win Rate / %Profit`, and the
  four-element prefix:

  ```python
  self.assertEqual(
      _SUMMARY_DEFAULT_COLUMNS[:4],
      (
          "Identity: Ticker",
          "Identity: Metric",
          "Match: Level %",
          "Match: Classification",
      ),
  )
  ```

- [ ] **Step 2: Run the focused tests to verify RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog
  ```

  Expected: failures show the old `Best by` labels and old column ordering.

### Task 2: Apply the smallest presentation-only implementation

**Files:**
- Modify: `app/pages/backtest_lab.py:68-71,99-124`
- Modify: `app/backtest_engine/signal_catalog.py:26-29`

**Interfaces:**
- Consumes: existing private metric label dictionaries and the summary-order
  tuple.
- Produces: unchanged renderer/catalog APIs with plain metric labels and
  reordered default summary fields.

- [ ] **Step 1: Change page labels and summary order**

  Set page labels to `Win Rate`, `%Profit`, and `Sharpe`; move Match Level and
  Match Classification to slots three and four of
  `_SUMMARY_DEFAULT_COLUMNS`.

- [ ] **Step 2: Change saved-signal option labels**

  Set catalog labels to the same three plain labels so Current Positions and
  every Backtest tab use consistent wording.

- [ ] **Step 3: Run the focused tests to verify GREEN**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog
  ```

  Expected: all tests pass with no `Best by` assertion remaining.

### Task 3: Verify scope and document the result

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-14-backtest-metric-label-clarity-verification.md`

**Interfaces:**
- Consumes: focused test result and repository search.
- Produces: evidence that the Backtest UI wording/order change is complete.

- [ ] **Step 1: Audit production Backtest modules**

  Run:

  ```powershell
  rg -n "Best by" app/pages/backtest_lab.py app/backtest_engine/signal_catalog.py
  ```

  Expected: no output.

- [ ] **Step 2: Run a wider Backtest verification gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_signal_catalog tests.test_backtest_page
  docker exec stock_app python -m compileall backtest_engine pages
  ```

  Expected: tests and compilation pass.

- [ ] **Step 3: Record evidenced completion**

  Update the tracker and verification report only after both commands pass.
