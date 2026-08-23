# Backtest Batch Input and Saved-Signal Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clarify Backtest labels, accept fifteen sequential Collect tickers,
and save only nonempty certified signal results.

**Architecture:** Reuse existing local metric label maps and Streamlit
renderers. Keep `BacktestBatchConfig` as the single worker-side cap; pass its
limit to the shared ticker parser only from Collect. Guard the current
per-ticker/theme atomic artifact writer at `_run_variant()` when no certified
set exists.

**Tech Stack:** Python 3.12, Streamlit, unittest, Docker.

## Global Constraints

- Do not alter canonical metric IDs, artifact schema, strategy logic, replay,
  positions, SQL, BIGINT price behavior, dependencies, Docker, credentials, or
  commit history.
- Preserve existing sequential execution, retry behavior, and separate
  no-theme/VN-Index AND files.
- No commit: the user manages commit history.

---

### Task 1: Render the approved Backtest labels and default summary order

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `tests/test_backtest_signal_catalog.py`
- Modify: `app/pages/backtest_lab.py:68-124,597-607,2252-2267`
- Modify: `app/backtest_engine/signal_catalog.py:26-29`

**Interfaces:**
- Consumes: `METRIC_TITLES`, `_SUMMARY_DEFAULT_COLUMNS`,
  `_render_signal_summary()`, and `_render_current_signal_catalog()`.
- Produces: plain metric labels, ordered visible summary fields, and visible
  View Signals labels without changing filter values.

- [x] **Step 1: Write failing UI and catalog tests**

  Assert the rendered Validate editor begins with this visible sequence and
  uses plain metric values:

  ```python
  ["Select", "Identity: Ticker", "Identity: Metric",
   "Match: Level %", "Match: Classification"]
  ```

  Update the two popover expectations to `Ticker` and `Ticker Groups`, and
  expect `No theme — Win Rate / %Profit` from saved-signal options.

- [x] **Step 2: Run the RED UI/catalog gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog
  ```

  Expected: current source fails for renderer order and View Signals labels.

- [x] **Step 3: Implement the narrow renderer changes**

  Order checkbox-driven selected fields by
  `_SUMMARY_DEFAULT_COLUMNS` before optional fields. Remove the collapsed
  ticker-label override and rename only the Group selectbox label. Keep the
  existing two-column layout, placeholders, keys, and callbacks.

- [x] **Step 4: Run the GREEN UI/catalog gate**

  Run the Step 2 command. Expected: all tests pass.

### Task 2: Accept fifteen Collect tickers without widening Validate input

**Files:**
- Modify: `tests/test_backtest_contracts.py`
- Modify: `tests/test_backtest_page.py`
- Modify: `app/backtest_engine/config.py:38-39,150-194`
- Modify: `app/pages/backtest_lab.py:16-23,161-168,2298-2316`

**Interfaces:**
- Consumes: `BacktestBatchConfig.tickers` and `parse_batch_tickers(value,
  maximum=5)`.
- Produces: `MAX_BACKTEST_BATCH_TICKERS = 15` and Collect-only parser use of
  that limit.

- [x] **Step 1: Write failing boundary tests**

  Prove a 15-symbol Collect parse/config preserves uppercase entered order;
  prove a 16th ticker raises `between 1 and 15`; prove
  `parse_batch_tickers(value)` without an explicit maximum still rejects a
  sixth ticker for manual Validate Signals.

- [x] **Step 2: Run the RED boundary gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_page
  ```

  Expected: 15-item inputs fail against the old five-item cap.

- [x] **Step 3: Implement the shared-limit boundary**

  Define `MAX_BACKTEST_BATCH_TICKERS = 15` beside existing Backtest constants.
  Validate `BacktestBatchConfig` against it. Give `parse_batch_tickers()` a
  `maximum=5` argument with positive-integer validation, then pass the new
  constant only from Collect Signals.

- [x] **Step 4: Run the GREEN boundary gate**

  Run the Step 2 command. Expected: all tests pass; no concurrent worker path
  is introduced.

### Task 3: Preserve current artifacts when certification is empty

**Files:**
- Modify: `tests/test_backtest_pipeline.py`
- Modify: `app/backtest_engine/pipeline.py:70-113,174-216`

**Interfaces:**
- Consumes: `_run_variant(...) -> tuple[str | None, bool]`.
- Produces: a saved path only for a nonempty certified signal set; batch
  output paths exclude variants without one.

- [x] **Step 1: Write failing persistence-boundary tests**

  Seed a current artifact, mock certification as `[]`, and prove
  `save_certified_signals()` is not called, `_run_variant()` returns
  `(None, False)`, and seeded bytes are unchanged. Add a themed batch fixture
  where no-theme is empty and VN-Index AND is nonempty; assert only the
  themed output path is recorded.

- [x] **Step 2: Run the RED pipeline gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_pipeline tests.test_backtest_persistence
  ```

  Expected: existing code calls the writer for empty results and reports an
  empty-variant path.

- [x] **Step 3: Implement the nonempty writer guard**

  In `_run_variant()`, return `(None, False)` before calling the writer when
  certification yields no set. Update single and batch callers to append only
  non-`None` paths while preserving existing progress, status, retry, and
  group-assignment logic.

- [x] **Step 4: Run the GREEN pipeline gate**

  Run the Step 2 command. Expected: all tests pass and prior bytes survive an
  empty rerun.

### Task 4: Verify and record completion

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-14-backtest-batch-and-signal-persistence-verification.md`

**Interfaces:**
- Consumes: Docker results and repository source audit.
- Produces: evidence-backed complete status.

- [x] **Step 1: Run the full focused Backtest gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_signal_catalog tests.test_backtest_page
  docker exec stock_app python -m compileall backtest_engine pages
  ```

  Expected: every focused test and compilation pass.

- [x] **Step 2: Audit scope**

  Run:

  ```powershell
  rg -n "Best by" app/pages/backtest_lab.py app/backtest_engine/signal_catalog.py
  git diff --check
  ```

  Expected: no Backtest `Best by` text and no whitespace errors.

- [x] **Step 3: Record verified completion**

  Mark every completed checkbox, replace the active WIP record with a
  completed archive, and record exact test counts. Do not create a commit.
