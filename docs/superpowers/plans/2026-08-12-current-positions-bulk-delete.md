# Current Positions Bulk Delete UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add all-visible table selection and one-confirmation safe batch deletion while placing Current Positions controls in the requested three-line layout.

**Architecture:** Keep `st.data_editor` and both existing atomic JSON stores. `backtest_lab.py` owns visible-selection session state, confirmation state, toolbar placement, batch prevalidation, ordered delete execution, partial-result reporting, and the two-second full-success message. Existing source-specific delete functions remain the only writers.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, `unittest`, Streamlit AppTest, existing atomic JSON position stores.

## Global Constraints

- No commit: the user manages commit history.
- No new dependency or Streamlit upgrade.
- Use raw BIGINT price storage and existing `k` UI conversion helpers only.
- Preserve immutable ticker/saved-signal association and direct Current Positions actions ungated by Validate Signals advice.
- Keep `Save changes` single-row only; multi-selection is delete-only.
- The select-all checkbox applies only to currently visible, filtered rows.
- Prevalidate all selected locators before a batch starts; delete in displayed table order; stop at the first failure with no cross-file rollback.
- Do not change SQL, database schema, `common_queries.py`, scaling, credentials, Docker, or dependency files.
- Verify in Docker with package-qualified `unittest` modules; do not use generic discovery.

---

### Task 1: Visible selection state and three-line toolbar

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: `_position_editor_rows()`, `_overview_position_id()`, and the
  filtered Current Positions rows.
- Produces:

  ```python
  def _visible_position_ids(rows: list[Mapping[str, object]]) -> tuple[str, ...]: ...
  def _pruned_selection(selected_ids: set[str], visible_ids: tuple[str, ...]) -> set[str]: ...
  def _position_editor_rows(
      rows: list[Mapping[str, object]], selected_ids: set[str] | None = None,
  ) -> pd.DataFrame: ...
  ```

- Adds page-owned session-state keys for selected IDs and select-all-visible.
  A selector callback/normalization path must use the current visible ID tuple,
  never a database query, and must clear selection after refresh, add, and a
  successful save.

- [x] **Step 1: Write failing selection and layout tests.**

  In `BacktestPageTests`, add a pure helper test with visible IDs
  `("manual-1", "legacy-2")` and a stale selected ID `"hidden-3"`:

  ```python
  self.assertEqual(
      _pruned_selection({"manual-1", "hidden-3"}, ("manual-1", "legacy-2")),
      {"manual-1"},
  )
  frame = _position_editor_rows(rows, {"legacy-2"})
  self.assertEqual(frame["Select"].tolist(), [False, True])
  ```

  Add an AppTest with two overview rows. Assert line-1 labels occur in this
  order: `Ticker filter`, `Position state`, `Sort by`, `Direction`; line 2 has
  native `New position` source usage and `↻`; line 3 has `Delete position`
  with `disabled is True`; and `Select all visible` is present immediately
  before the editor in the page element order.

- [x] **Step 2: Run the selection/layout RED gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_current_position_visible_selection_and_toolbar_layout -v
  ```

  Expected: FAIL because selection is hard-coded false, controls occupy two
  different rows, and delete is rendered after the editor without disabled
  state.

- [x] **Step 3: Implement the minimal selection model and layout.**

  Add `_POSITION_SELECTED_IDS_KEY` and `_POSITION_SELECT_ALL_VISIBLE_KEY`.
  After filtering, derive `visible_ids` once, prune stored selections to that
  set, and use those IDs as the `Select` values passed to
  `_position_editor_rows()`.

  Render line 1 in four columns. Render line 2 with the existing
  `_render_new_position_popover(...)` and refresh icon only. Render line 3
  with:

  ```python
  delete_clicked = st.button(
      "Delete position",
      disabled=not selected_visible_ids,
      key="current_positions_delete",
  )
  ```

  Render `Select all visible` directly above the editor. Checking it replaces
  the visible selection with all visible IDs; unchecking it clears visible
  selection. After the editor returns, derive individual selected IDs from its
  `Select` column, persist only their intersection with `visible_ids`, and
  synchronize the select-all value to `selected == set(visible_ids)`.

  Move `Save changes` below the editor and retain its existing exactly-one-row
  validation. Clear `_POSITION_SELECTED_IDS_KEY` on refresh, successful New
  position, and successful Save changes.

- [x] **Step 4: Run the selection/layout GREEN gate.**

  Run the command from Step 2. Expected: PASS with no AppTest exception.

- [x] **Step 5: Review Task 1.**

  Confirm no selected ID outside the current filtered rows can enable delete,
  no selection action queries the database, and Save changes still rejects
  more than one selected row.

---

### Task 2: Ordered batch-delete prevalidation and confirmation

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: `_position_row_locator()`, `_position_delete_summary()`, and
  `_delete_by_locator()`.
- Produces:

  ```python
  def _validated_delete_locator(locator: Mapping[str, object]) -> dict[str, str]: ...
  def _prepare_batch_delete(
      rows: list[Mapping[str, object]], selected_ids: set[str],
  ) -> tuple[dict[str, object], ...]: ...
  def _run_batch_delete(
      entries: tuple[Mapping[str, object], ...], positions_dir: str,
      delete_position_fn: Callable, manual_delete_fn: Callable,
  ) -> tuple[int, Mapping[str, object] | None, Exception | None]: ...
  ```

- Each prepared entry has `position_id`, validated immutable `locator`, and
  rendered `summary`; it follows table row order, not unordered selected-ID
  set order. `_run_batch_delete()` returns the count deleted before the first
  error and never calls a later writer after that error.

- [x] **Step 1: Write failing batch helper tests.**

  Use one manual and two legacy locators plus fake writers. Add tests that:

  ```python
  entries = _prepare_batch_delete(rows, {"manual-1", "legacy-2"})
  self.assertEqual([entry["position_id"] for entry in entries], ["manual-1", "legacy-2"])
  deleted, failed, error = _run_batch_delete(entries, "positions", legacy_delete, manual_delete)
  self.assertEqual((deleted, failed, error), (2, None, None))
  ```

  Add a malformed second locator test and assert `_prepare_batch_delete()`
  raises before either fake writer is called. Add a second-writer failure test
  and assert `deleted == 1`, the failed entry is the second record, and the
  third writer is never called.

- [x] **Step 2: Run the batch-helper RED gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_current_position_batch_delete_prevalidates_and_stops -v
  ```

  Expected: FAIL because batch preparation/execution helpers do not exist.

- [x] **Step 3: Implement batch helpers and batch confirmation state.**

  Extract the validation portion of `_delete_by_locator()` into
  `_validated_delete_locator()` so both single and batch routes apply the same
  manual/legacy requirements. Implement `_prepare_batch_delete()` by walking
  the visible row list, retaining only selected IDs, resolving the immutable
  locator, validating every locator, and creating summaries before returning
  any entry. Reject an empty batch.

  Implement `_run_batch_delete()` with the following ordered loop:

  ```python
  deleted = 0
  for entry in entries:
      try:
          _delete_by_locator(entry["locator"], positions_dir, delete_position_fn, manual_delete_fn)
      except (OSError, TypeError, ValueError) as error:
          return deleted, entry, error
      deleted += 1
  return deleted, None, None
  ```

  Replace the one-record confirmation state with `entries` and the exact
  ordered selected IDs. Show every summary before `Confirm permanent delete`.
  If filters, refresh, or row selection no longer match the stored ID tuple,
  cancel rather than delete. On partial failure, clear overview and selection,
  rerun, and show `Deleted N of M positions; stopped at <summary>: <error>`.
  Do not show a success message for a partial batch.

- [x] **Step 4: Run the batch-helper GREEN gate and existing delete tests.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_current_position_batch_delete_prevalidates_and_stops `
    tests.test_backtest_page.BacktestPageTests.test_current_position_locator_lifecycle_and_delete_are_exact `
    tests.test_backtest_page.BacktestPageTests.test_pending_delete_requires_the_same_visible_position -v
  ```

  Expected: PASS. The third fake entry remains untouched after second-entry
  failure.

- [x] **Step 5: Review Task 2.**

  Confirm prevalidation uses no writer, a batch never executes hidden rows,
  and the documented atomicity ceiling is only cross-file rollback.

---

### Task 3: Two-second success feedback and integrated UI regression

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: Task 1 selection state and Task 2 batch result.
- Produces:

  ```python
  def _show_timed_delete_success(
      message: str, show_fn: Callable, clear_fn: Callable,
      sleep_fn: Callable = time.sleep,
  ) -> None: ...
  ```

- The page stores a successful batch message, reruns to reload its overview,
  then invokes this helper with an `st.empty()` placeholder. It must call
  `show_fn(message)`, `sleep_fn(2)`, then `clear_fn()` exactly once. The
  blocking two seconds are intentional: Streamlit 1.32 has no configurable
  toast duration and the requirement is an exact two-second visible message.

- [x] **Step 1: Write failing timed-success and UI integration tests.**

  Add a direct helper test:

  ```python
  calls = []
  _show_timed_delete_success("2 positions permanently deleted.", calls.append, lambda: calls.append("clear"), calls.append)
  self.assertEqual(calls, ["2 positions permanently deleted.", 2, "clear"])
  ```

  Add an AppTest for two rows that asserts default delete is disabled, and an
  AppTest/source-contract assertion that the batch confirmation action exists
  separately from the disabled delete trigger. Keep the existing documented
  limitation: Streamlit 1.32 AppTest cannot simulate a data-editor checkbox
  click, so selection/batch mutation is covered through pure helper/store
  tests rather than a browser-grid interaction.

- [x] **Step 2: Run the feedback/UI RED gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_current_position_timed_batch_delete_success -v
  ```

  Expected: FAIL because timed batch-success feedback does not exist.

- [x] **Step 3: Implement success feedback and wire all batch states.**

  Add a dedicated session-state key for the pending full-success message. On a
  fully successful `_run_batch_delete()` result, clear overview/selection and
  confirmation, save `f"{deleted} positions permanently deleted."`, and rerun.
  At the next Current Positions render, create `placeholder = st.empty()`,
  invoke `_show_timed_delete_success(message, placeholder.success,
  placeholder.empty)`, then remove the message key. Partial failures use the
  normal durable error path only.

  Keep the existing one-record `Delete position` wording for the trigger even
  when multiple rows are selected; the confirmation itself states the exact
  selected count and lists all entries.

- [x] **Step 4: Run the integrated page/store GREEN gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page `
    tests.test_backtest_manual_position_store `
    tests.test_backtest_position_store `
    tests.test_backtest_position_overview -v
  ```

  Expected: all page, selection, batch, legacy/manual delete, lifecycle, and
  overview regressions pass.

- [x] **Step 5: Review Task 3.**

  Confirm the two-second sleep executes only for all-success delete feedback,
  the success key is removed afterward, partial failure cannot appear as
  success, and no new query or per-row database work exists.

---

### Task 4: Complete verification and status handoff

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-12-current-positions-bulk-delete-verification.md`

**Interfaces:**

- Consumes: Tasks 1–3 and their test evidence.
- Produces: final verification report, completed plan checkboxes, and current
  project status. No commit is created.

- [x] **Step 1: Run complete package-qualified Backtest verification.**

  ```powershell
  $backtestModules = Get-ChildItem tests -Filter 'test_backtest*.py' |
    ForEach-Object { 'tests.' + $_.BaseName }
  docker exec stock_app python -m unittest $backtestModules
  ```

  Expected: zero failures; retain the documented expected skip.

- [x] **Step 2: Compile and verify boundaries.**

  ```powershell
  docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py
  git diff --check
  Get-FileHash app/commons/common_queries.py, app/pages/data_preparation.py, app/main.py,
    docker/Dockerfile, docker/docker-compose.yml, requirements.txt
  ```

  Expected: compilation and whitespace check pass; protected-file hashes match
  their pre-feature baseline.

- [x] **Step 3: Run live container health smoke.**

  ```powershell
  docker exec stock_app python -c "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:3501/_stcore/health', timeout=5); print(response.status, response.read().decode())"
  ```

  Expected: `200 ok`. Document the existing headless AppTest limitation for
  direct grid-click automation, not as a production error.

- [x] **Step 4: Complete implementation review and documentation.**

  Read `ai-skills/skill-implementation-review.md`; document logic, SQL, and
  performance findings. Mark every plan task complete only after its command
  output exists, update FOCUS/current status, write the report with exact test
  count and known limitation, and preserve the user-managed commit history.

## Plan Self-Review

| Requirement | Task coverage |
| --- | --- |
| Three-line layout and disabled delete trigger | Task 1 |
| Individual/all-visible selection, filter pruning | Task 1 |
| Prevalidation and stable ordered mixed-source batch | Task 2 |
| Stop-on-first-failure/partial result/no rollback | Task 2 |
| Exact two-second full-success feedback | Task 3 |
| Final regression, boundaries, health, and documentation | Task 4 |

No placeholders, protected-file changes, dependency changes, or commit step
remain. All helper names consumed by later tasks are defined in the producing
task above.
