# Data Page Phase Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the approved Data Page controls on one row and replace the spinner with an accurate phase-based 0–100% ingestion progress bar.

**Architecture:** `run_full_ingestion()` will accept an optional UI-neutral progress callback and emit milestones only after each real phase reaches its boundary. The Streamlit page passes a small callback that updates one progress bar and renders existing log messages inside an expanded progress-details section. API/background callers pass no callback and retain console logging and return semantics.

**Tech Stack:** Python 3.12, Streamlit 1.32, SQLAlchemy, unittest with Streamlit AppTest.

## Global Constraints

- Data preparation only: do not alter ingestion URLs, reset semantics, schema, API route behavior, or database contents.
- Keep all price ingestion `* 1000` BIGINT scaling exactly unchanged.
- Milestones are phase-based, not invented byte/row percentages: Start `0`, reset `20`, schema `35`, stock `65`, index `90`, complete `100`.
- The Data Page first line is exactly Up-to date, Year gaps, Get data; Year
  gaps defaults to `15`.
- Progress details are expandable and initially expanded; no `st.spinner` remains in this flow.
- On failure, retain the last completed progress value, report the error through existing logging, and never show a false success state.
- No new dependency, SQL change, Docker change, credential change, or commit. The user manages commits.

---

### Task 1: Test the phase-progress callback contract

**Files:**
- Create: `tests/test_data_preparation.py`
- Modify: `app/pages/data_preparation.py:237-278`

**Interfaces:**
- Consumes: `run_full_ingestion(report_date, gaps_of_data, engine)`.
- Produces: `run_full_ingestion(report_date, gaps_of_data, engine, progress_callback: Callable[[int, str], None] | None = None) -> bool`.

- [x] **Step 1: Write the failing callback test**

  Add a test that patches `init_db()` and `download_and_process_data()`, runs
  `run_full_ingestion()` against an in-memory SQLite engine, and records the
  optional callback values:

  ```python
  progress = []
  result = run_full_ingestion(
      date(2026, 8, 13),
      15,
      create_engine("sqlite://"),
      progress_callback=lambda value, label: progress.append((value, label)),
  )

  self.assertTrue(result)
  self.assertEqual([value for value, _ in progress], [0, 20, 35, 65, 90, 100])
  self.assertEqual([label for _, label in progress], [
      "Starting data ingestion...",
      "Current data reset.",
      "Schema ready.",
      "Stock data complete.",
      "VN-Index data complete.",
      "Data ingestion complete.",
  ])
  ```

  Assert stock is requested before index and no price-processing function is
  called directly by the test.

- [x] **Step 2: Run the test to prove RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_data_preparation.DataPreparationTests.test_run_full_ingestion_reports_completed_phase_milestones -v
  ```

  Expected: FAIL because `run_full_ingestion()` has no `progress_callback`
  argument.

- [x] **Step 3: Add the minimal callback implementation**

  Import `Callable` from `typing`. Add a private notifier that is a no-op for
  `None`, then call it at these existing phase boundaries:

  ```python
  _report_phase(progress_callback, 0, "Starting data ingestion...")
  # reset transaction commits
  _report_phase(progress_callback, 20, "Current data reset.")
  # init_db returns
  _report_phase(progress_callback, 35, "Schema ready.")
  # stock download_and_process_data returns
  _report_phase(progress_callback, 65, "Stock data complete.")
  # index download_and_process_data returns
  _report_phase(progress_callback, 90, "VN-Index data complete.")
  # before successful return
  _report_phase(progress_callback, 100, "Data ingestion complete.")
  ```

  Keep the current lock, `log_progress()` calls, exception handling, and
  `False` return behavior unchanged. Never call the `100` milestone when an
  exception occurs.

- [x] **Step 4: Run the focused test to prove GREEN**

  Run the command from Step 2.

  Expected: PASS with the ordered completed-phase sequence above.

### Task 2: Render the approved Data Page controls and progress details

**Files:**
- Modify: `app/pages/data_preparation.py:270-278`
- Modify: `tests/test_data_preparation.py`

**Interfaces:**
- Consumes: `run_full_ingestion(..., progress_callback=...) -> bool`.
- Produces: `data_page(engine)` with a synchronous Streamlit progress bar and
  expanded progress-details container.

- [x] **Step 1: Write failing Data Page layout expectations**

  Add an AppTest that renders `data_page(None)` without clicking Get data and
  asserts the labels `Up-to date`, `Year gaps`, and `Get data`. Inspect
  `data_page` source to require `st.columns(3)`, `st.progress`, and an
  expanded `st.expander("Progress details", expanded=True)`, and to reject
  `st.spinner`.

- [x] **Step 2: Run the layout test to prove RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_data_preparation.DataPreparationTests.test_data_page_has_approved_control_row_and_progress_ui -v
  ```

  Expected: FAIL because current labels are `Select Report Date` and `Gaps of
  Data (Years)`, controls are vertical, and the flow uses `st.spinner`.

- [x] **Step 3: Implement the smallest Streamlit UI change**

  In `data_page()`, render the inputs and action in
  `up_to_date_column, year_gaps_column, action_column = st.columns(3)`. Keep
  the existing input values, ranges, lock guard, and `Get data` submission
  behavior. When a run starts, create one progress bar at `0` and wrap the
  execution in:

  ```python
  with st.expander("Progress details", expanded=True):
      completed = run_full_ingestion(
          report_date,
          gaps_of_data,
          engine,
          progress_callback=lambda value, label: progress_bar.progress(
              value, text=label
          ),
      )
  ```

  Do not add asynchronous execution, a fake timer, or an extra completion
  indicator. Existing `log_progress()` writes the detailed real ingestion
  messages into that expanded section.

- [x] **Step 4: Run focused Data Page tests**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_data_preparation -v
  ```

  Expected: PASS for milestone order and the rendered approved UI contract.

- [x] **Step 5: Verify documentation and boundaries**

  Run focused tests, the package-qualified app/backtest test gate, compilation
  of `pages/data_preparation.py`, `git diff --check`, and Streamlit health.
  Review that `process_csv_file()` and all `* 1000` price scaling lines are
  unchanged. Update `FOCUS.md`, `ai-context/current-status.md`, and a concise
  verification report; record that no commit was created.
