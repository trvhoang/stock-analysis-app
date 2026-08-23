# Collect Group Membership Independent of Backtest Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add every requested ticker to a selected named Collect Signals Group
atomically before the batch backtest begins, regardless of its eventual result,
while retaining Validate Signals' no-saved-signal skip behavior.

**Architecture:** Add one batch Group writer in `result_store` that reuses the
existing Group journal and JSON replacement path to write one complete member
set. The existing single-ticker public writer delegates to it. The batch
pipeline calls that writer once before theme preparation and removes all
result-gated/retry-gated membership writes. Validate's existing pre-loop
eligibility filter is unchanged and covered by a regression test.

**Tech Stack:** Python 3.12, Streamlit, existing JSON Group store, `unittest`,
Docker.

## Global Constraints

- Named Group means a normalized Group other than blank or `N/A`; blank/`N/A`
  performs no membership write.
- Keep Group JSON storage, existing journal/recovery protocol, uppercase
  normalization, Group UUID/slug, metadata, and add-only multi-membership.
- A named-Group write covers all `BacktestBatchConfig.tickers` before theme
  preflight and any ticker execution; Group-write failure aborts the batch.
- No SQL, database, BIGINT scaling, artifact schema, position, replay, UI,
  dependency, Docker, credential, or commit-history change.
- Do not commit; the user manages commits separately.

---

### Task 1: Atomic Batch Group Store

**Files:**
- Modify: `app/backtest_engine/result_store.py:247-303`
- Modify: `tests/test_backtest_persistence.py:143-212`

**Interfaces:**

- Consumes: a validated `Sequence[str]` of ticker symbols, a Group name, and
  `signal_dir`.
- Produces: `assign_tickers_group(tickers: Sequence[str], group_name: str,
  signal_dir: str = DEFAULT_SIGNAL_DIR) -> None`; either one recoverable Group
  JSON update contains every normalized unique ticker or it raises before a
  caller can proceed.
- Preserves: `assign_ticker_group(ticker: str, group_name: str,
  signal_dir: str = DEFAULT_SIGNAL_DIR) -> None` as a compatibility wrapper.

- [x] **Step 1: Write failing store tests**

  Add `test_group_batch_assignment_adds_all_tickers_in_one_group_payload` to
  call the new batch writer with `("FPT", "VCB", "FPT")` and assert that
  `list_groups()` returns exactly one `BANK` Group whose tickers are
  `("FPT", "VCB")`. Add `test_group_batch_assignment_ignores_na_group` and
  assert no Group JSON appears for `"N/A"`.

- [x] **Step 2: Run store tests RED**

  Run in `stock_app`:

  ```powershell
  python -m unittest tests.test_backtest_persistence.BacktestPersistenceTests.test_group_batch_assignment_adds_all_tickers_in_one_group_payload tests.test_backtest_persistence.BacktestPersistenceTests.test_group_batch_assignment_ignores_na_group
  ```

  Expected: both fail because `assign_tickers_group` is absent.

- [x] **Step 3: Implement one atomic batch writer**

  Add this public function beside `assign_ticker_group`:

  ```python
  def assign_tickers_group(
      tickers: Sequence[str],
      group_name: str,
      signal_dir: str = DEFAULT_SIGNAL_DIR,
  ) -> None:
      ...
  ```

  Validate `tickers` as a non-string `Sequence`; normalize and de-duplicate
  tickers. Return immediately when `_normalize_group_name(group_name)` is
  `None`. Reuse `_recover_group_move`, `_load_groups`, `_group_payload`,
  `_write_json_atomically`, and the existing Group journal. Build one updated
  `SignalGroup` whose members are the union of prior members and all normalized
  tickers, then journal exactly one before/after Group payload. Change
  `assign_ticker_group` to call this function with a one-element tuple.

- [x] **Step 4: Run store tests GREEN**

  Re-run the Step 2 command. Expected: both pass.

- [x] **Step 5: Review compatibility**

  Run:

  ```powershell
  python -m unittest tests.test_backtest_persistence.BacktestPersistenceTests.test_group_membership_is_add_only_and_na_is_derived tests.test_backtest_persistence.BacktestPersistenceTests.test_group_reader_rejects_duplicate_group_name_or_same_file_ticker
  ```

  Expected: existing single-ticker add-only and Group validation behavior pass.

  Approved follow-up: Group readers accept unordered uppercase unique ticker
  arrays, return sorted members, and continue to reject duplicate or
  non-uppercase tickers. The BANK runtime Group reads without rewriting it.

### Task 2: Assign Named Groups Before Every Batch Result

**Files:**
- Modify: `app/backtest_engine/pipeline.py:197-327`
- Modify: `tests/test_backtest_pipeline.py:435-610`

**Interfaces:**

- Consumes: `BacktestBatchConfig.tickers`, `BacktestBatchConfig.group_name`,
  and `BacktestBatchConfig.output_dir`.
- Produces: one preflight call to `assign_tickers_group`; Group membership is
  independent of ticker signal certification, exceptions, retry state, and
  themed preflight outcome.
- Preserves: ticker execution order, one deferred retry, per-ticker status,
  output paths, and Group `N/A` no-op semantics.

- [x] **Step 1: Write failing pipeline tests**

  Replace the existing empty-result Group test with
  `test_batch_assigns_all_tickers_before_empty_results`, using `("FPT", "VCB")`
  and `_run_variant(..., False)`. Assert `assign_tickers_group` receives the
  complete tuple once, both ticker states are `done`, and no single-ticker
  writer is called. Add `test_group_assignment_failure_aborts_before_theme_or_ticker_execution`:
  make `assign_tickers_group` raise `OSError("disk full")`; assert
  `_shared_confirmation` and `_prepare_ticker` were not called and the error
  propagates. Retain a themed-failure case and assert Group assignment occurred
  before `_shared_confirmation`.

- [x] **Step 2: Run pipeline tests RED**

  Run in `stock_app`:

  ```powershell
  python -m unittest tests.test_backtest_pipeline.BacktestPipelineTests.test_batch_assigns_all_tickers_before_empty_results tests.test_backtest_pipeline.BacktestPipelineTests.test_group_assignment_failure_aborts_before_theme_or_ticker_execution tests.test_backtest_pipeline.BacktestPipelineTests.test_final_themed_failure_assigns_group_when_no_theme_is_nonempty
  ```

  Expected: fail because the batch writer is not called at pipeline entry and
  result-gated single-ticker assignment remains.

- [x] **Step 3: Implement pipeline entry assignment**

  Import `assign_tickers_group`. Immediately after creating the initial ticker
  statuses and before `report(0.0)`/`_shared_confirmation`, call:

  ```python
  assign_tickers_group(config.tickers, config.group_name, config.output_dir)
  ```

  Delete `final_attempt_qualified`, `pending_final_group_assignment`, the
  result-gated `assign_ticker_group` block in `run_ticker`, and the final retry
  assignment loop. Do not catch the initial writer error: it must abort before
  theme/ticker work. Leave the writer's blank/`N/A` no-op in the store layer.

- [x] **Step 4: Run pipeline tests GREEN**

  Re-run the Step 2 command. Expected: all pass. Then run:

  ```powershell
  python -m unittest tests.test_backtest_pipeline
  ```

  Expected: the complete pipeline module passes.

### Task 3: Strengthen Validate No-Signal Skip Regression

**Files:**
- Modify: `tests/test_backtest_page.py:1850-1935`

**Interfaces:**

- Consumes: a named Group's resolved ticker tuple and
  `tickers_with_no_saved_signal(tickers, signal_dir)` result.
- Produces: validation calls only for eligible tickers; skipped named-Group
  tickers appear in the existing skipped feedback list.
- Preserves: group source-list resolution, fifteen-ticker Group cap, sequential
  validation, progress lifecycle, and stored request identity.

- [x] **Step 1: Strengthen the existing Validate regression test**

  Extend the existing
  `test_validate_group_locks_tickers_and_skips_missing_artifacts_sequentially`
  fixture. Its Group resolves `("FPT", "VCB", "MBB")` and its skip helper
  returns `("VCB",)`. Tighten its existing `Validation calls:` assertion to
  require exactly `['FPT', 'MBB']` in order, and retain the assertion that
  final feedback names `VCB`. Do not modify production code.

- [x] **Step 2: Run the existing-behavior regression check**

  Run in `stock_app`:

  ```powershell
  python -m unittest tests.test_backtest_page.BacktestPageTests.test_validate_group_locks_tickers_and_skips_missing_artifacts_sequentially
  ```

  Expected: pass. The production behavior already exists; this test narrows
  its regression assertion without adding a duplicate implementation.

- [x] **Step 3: Record no production change**

  Confirm `backtest_lab.py` and `signal_catalog.py` are untouched by this
  task. The existing `tickers_with_no_saved_signal()` pre-loop filter remains
  the single behavior owner.

### Task 4: Review, Full Focused Verification, and Documentation

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/plans/2026-08-15-collect-group-membership-independent-of-results.md`
- Create: `docs/superpowers/reports/2026-08-15-collect-group-membership-independent-of-results-verification.md`

**Interfaces:**

- Consumes: completed Task 1–3 test evidence.
- Produces: completed task tracking and a report stating exact test counts,
  implementation-review findings, and remaining known test-topology debt.

- [x] **Step 1: Run focused verification**

  Run in `stock_app`:

  ```powershell
  python -m unittest tests.test_backtest_persistence tests.test_backtest_signal_catalog tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_page
  python -m compileall backtest_engine pages
  ```

  Check Streamlit health:

  ```powershell
  python -c "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:3501/_stcore/health'); print(response.status, response.read().decode())"
  ```

  Expected: focused suite and compilation pass; health returns `200`.

- [x] **Step 2: Perform implementation review**

  Apply `ai-skills/skill-implementation-review.md`. Record that Group writes
  are JSON-only; no SQL, database, BIGINT display/scaling, query, or cache path
  was changed. Confirm no per-ticker Group JSON write remains in the pipeline.

- [x] **Step 3: Update tracking and report**

  Mark Tasks 1–4 complete in this plan. Mark FOCUS complete and move the WIP
  item into Recently Completed with exact verification evidence. Write the
  verification report with RED/GREEN outputs, focused-suite count, compiler and
  health results, scope statement, and no-commit note.
