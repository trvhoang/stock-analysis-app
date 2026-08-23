# Current Positions Inline Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver safe inline management of legacy and manual Current Positions: filter, sort, refresh, add, edit, close, reopen, and permanently delete exactly one selected position.

**Architecture:** Retain the two existing atomic JSON stores. Extend their update contracts to validate a complete final lifecycle state and add exact-record delete functions. `backtest_lab.py` owns Streamlit-only normalization, filtering, sorting, editor state, confirmation state, and locator routing; the overview remains the sole source for derived current price, P&L, and database-session hold time.

**Tech Stack:** Python 3.12, Streamlit 1.32 (`st.popover`, `st.data_editor`), pandas, pytest-free `unittest`, existing atomic JSON history writers.

## Global Constraints

- Do not create a commit; the user manages commit history.
- No new dependencies and no Streamlit upgrade. `st.dialog` is unavailable in deployed Streamlit 1.32; use `st.popover`.
- Preserve raw BIGINT storage. Use existing `price_from_ui_k_vnd()` and `prepare_price_for_output()` at UI boundaries only.
- Preserve ticker and saved-signal association immutability. A changed ticker or signal set requires delete then recreate.
- Use `Asia/Ho_Chi_Minh` for generated lifecycle audit timestamps.
- Keep direct Current Positions actions ungated by Validate Signals advice. Preserve the one-OPEN saved-set rule across manual and legacy histories.
- Never modify `app/commons/common_queries.py`, ingestion scaling,
  `get_engine_with_retry()`, credentials, Docker files, or dependencies.
- Use `docker exec stock_app python -m unittest ...`; this repository has no root Compose file.

---

### Task 1: Atomic lifecycle update and exact delete in both position stores — Complete

**Files:**

- Modify: `app/backtest_engine/manual_position_store.py`
- Modify: `app/backtest_engine/position_store.py`
- Modify: `tests/test_backtest_manual_position_store.py`
- Modify: `tests/test_backtest_position_store.py`

**Interfaces:**

- Consumes: existing `update_manual_position()`, `update_position()`, `_write_history()`, validators, and frozen-risk helper.
- Produces:

  ```python
  def delete_manual_position(
      ticker: str, position_id: str, positions_dir: str = "backtest-positions"
  ) -> dict[str, object]: ...

  def delete_position(
      ticker: str, theme_variant: str, metric: str, position_id: str,
      positions_dir: str = "backtest-positions",
  ) -> dict[str, object]: ...
  ```

  Both existing `update_*_position(..., updates, ...)` functions accept
  `status`, `buy_date`, `sell_date`, `actual_buy_price`,
  `actual_sell_price`, and `quantity` as a full inline-edit candidate.

- Guarantees: delete returns a deep copy of exactly the removed record; it
  cannot remove another record. An update validates the final record before
  writing. OPEN has no SELL data; CLOSED has both positive SELL price and a
  SELL date on/after BUY date.

- [x] **Step 0: Record protected-file hashes before implementation.**

  This worktree is already dirty, so a final Git diff cannot attribute a
  protected-file change to this feature. Record the current hashes without
  changing any file:

  ```powershell
  Get-FileHash app/commons/common_queries.py, app/pages/data_preparation.py, app/main.py,
    docker/Dockerfile, docker/docker-compose.yml, requirements.txt
  ```

  Expected: six baseline hashes available for Task 5 comparison.

- [x] **Step 1: Write failing generic-history lifecycle/delete tests.**

  Add a test that creates a generic saved-set position, updates it from OPEN to
  CLOSED with an inline candidate, then reopens it and asserts that SELL fields,
  `closed_at`, and `sell_reason` are cleared while `opened_at`, ticker, and
  signal reference are preserved. Add a second position and assert
  `delete_manual_position()` removes only the named ID.

  ```python
  closed = update_manual_position(
      "FPT", opened["id"],
      {
          "status": "closed", "actual_buy_price": 51500,
          "buy_date": "2026-08-08", "actual_sell_price": 53000,
          "sell_date": "2026-08-12", "quantity": 200,
      }, directory,
  )
  reopened = update_manual_position(
      "FPT", opened["id"],
      {
          "status": "open", "actual_buy_price": 51500,
          "buy_date": "2026-08-08", "actual_sell_price": None,
          "sell_date": None, "quantity": 200,
      }, directory,
  )
  removed = delete_manual_position("FPT", other["id"], directory)
  self.assertEqual(closed["status"], "closed")
  self.assertEqual(reopened["status"], "open")
  self.assertIsNone(reopened["actual_sell_price"])
  self.assertEqual(removed["id"], other["id"])
  ```

- [x] **Step 2: Run the generic RED test.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_manual_position_store.ManualPositionStoreTests.test_inline_lifecycle_update_and_exact_delete -v
  ```

  Expected: FAIL because the current update rejects `status`/dates and no
  delete function exists.

- [x] **Step 3: Write failing legacy-history lifecycle/delete and cross-history reopen tests.**

  Add a test that closes then reopens one legacy record in place and asserts the
  same cleared/retained fields. While it is closed, create an overlapping generic
  saved-set OPEN position, then assert legacy reopen raises
  `ValueError("saved signal set already has an OPEN position")`. Add a delete
  assertion that preserves a sibling legacy record.

  ```python
  with self.assertRaisesRegex(ValueError, "already has an OPEN position"):
      update_position(
          "FPT", "no-background-theme", "win_rate", legacy["id"],
          {"status": "open", "actual_buy_price": 50300,
           "buy_date": "2026-08-07", "actual_sell_price": None,
           "sell_date": None, "quantity": None}, directory,
      )
  ```

- [x] **Step 4: Run the legacy RED test.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_position_store.PositionStoreTests.test_inline_lifecycle_update_and_exact_delete -v
  ```

  Expected: FAIL because legacy updates reject lifecycle fields and no delete
  function exists.

- [x] **Step 5: Implement complete-candidate validation and atomic delete.**

  In both stores, build a deep-copied candidate from the stored position and
  supplied permitted fields. Normalize dates/raw values with the existing
  validators, then derive lifecycle fields from its final state before
  `_validated_history()` and `_write_history()`:

  ```python
  if candidate["status"] == "open":
      candidate.update({
          "actual_sell_price": None, "sell_date": None,
          "closed_at": None, "sell_reason": None,
      })
  else:
      candidate["actual_sell_price"] = _positive_raw_int(
          candidate.get("actual_sell_price"), "actual_sell_price"
      )
      candidate["sell_date"] = _iso_date(candidate.get("sell_date"), "sell_date")
      if candidate["sell_date"] < candidate["buy_date"]:
          raise ValueError("sell date cannot be before BUY date")
      if previous["status"] == "open":
          candidate["closed_at"] = datetime.now(_MARKET_TIMEZONE).isoformat()
      candidate["sell_reason"] = "manual"
  ```

  Preserve `opened_at`. If BUY price changes and a frozen risk snapshot exists,
  recalculate only SL/TP with `_risk_for_buy_price()`.

  For generic reopening, reuse `_assert_no_open_signal_overlap()` before
  writing. For legacy reopening, reject another OPEN in the tuple and lazily
  load generic manual history to compare the legacy signal's `signal_link_key`
  against generic OPEN reference link keys. The lazy imports avoid the existing
  module-import cycle (`manual_position_store` already imports
  `position_store`).

  Implement delete by locating the exact ID, removing only that element from
  the loaded history, validating the remaining history, calling `_write_history`,
  and returning a copy of the removed record. Export all new functions in
  `__all__`.

- [x] **Step 6: Run focused stores GREEN.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_manual_position_store \
    tests.test_backtest_position_store -v
  ```

  Expected: all store tests pass, including exact deletion, reopening, frozen
  SL/TP recalculation, and cross-history one-OPEN protection.

- [x] **Step 7: Review this task.**

  Confirm no history is mutated before complete candidate validation, no ticker
  or signal reference becomes editable, reopening clears closure data, and the
  only deliberate ceiling remains the pre-existing atomic-per-file writer.

---

### Task 2: Pure Current Positions formatting, filter, and sort contract — Complete

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: overview rows produced by `summarize_positions()` and existing
  price conversion helpers.
- Produces pure page helpers:

  ```python
  def _uppercase_ticker_state(widget_key: str) -> None: ...
  def _filter_and_sort_positions(
      rows: Iterable[Mapping[str, object]], ticker_filter: str,
      states: Iterable[str], sort_by: str, direction: str,
  ) -> list[Mapping[str, object]]: ...
  def _position_editor_rows(rows: Iterable[Mapping[str, object]]) -> pd.DataFrame: ...
  ```

- Guarantees: three-character uppercase exact filter, Open date ASC default,
  selectable sort/direction, unavailable numeric values last, and audit dates
  formatted `DD/MM/YYYY` only.

- [x] **Step 1: Write failing pure page-helper tests.**

  Add rows with different `opened_at`, numeric/None profit values, and holding
  session counts. Assert that default Open date ASC is oldest first, Profit
  DESC puts the largest valid value first, missing values are last, and `Fpt`
  session state normalizes to `FPT`. Assert the editor frame shows
  `01/08/2026`, not ISO timestamps, for audit fields.

  ```python
  ordered = _filter_and_sort_positions(rows, "FPT", ("OPEN",), "Open date", "ASC")
  self.assertEqual([row["id"] for row in ordered], ["old-open", "new-open"])
  self.assertEqual(_position_editor_rows(ordered).iloc[0]["Open time"], "01/08/2026")
  ```

- [x] **Step 2: Run the helper RED test.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_page.BacktestPageTests.test_current_position_filter_sort_and_editor_rows -v
  ```

  Expected: FAIL because the helpers and date-only editor model do not exist.

- [x] **Step 3: Implement only the pure presentation helpers.**

  Keep `summarize_positions()` unchanged. Build editor rows from its raw values,
  retaining a hidden record ID/locator key for routing. Use raw numeric values
  for sortable Profit, Profit %, and Hold time; convert displayed prices through
  existing `k` helpers. Parse audit timestamps once and render dates with
  `%d/%m/%Y`. Sort values must use `(is_missing, value)` so unavailable values
  are consistently last for either direction.

- [x] **Step 4: Run the helper GREEN test.**

  Run the command from Step 2. Expected: PASS.

- [x] **Step 5: Review this task.**

  Confirm filtering/sorting are in-memory after the one cached overview load,
  do not query per sort/filter change, and do not mutate position records.

  **Result:** PASS. The helper RED failure was the expected absent interface;
  its focused GREEN test and the Backtest Page suite pass 25/25. Sorting keeps
  missing sort values last for both directions without querying or mutating a
  position record.

---

### Task 3: Current Positions toolbar and native New Position popover — Complete

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: Task 2 helpers, `create_manual_position()`,
  `list_saved_signal_options()`, `prepare_signal_reference()`, and
  `_risk_snapshot_from_basis()`.
- Produces: `_render_new_position_popover(...)` plus toolbar controls inside
  `_render_current_positions_tab(...)`.
- Guarantees: a typed ticker reruns before signal options render; no add write
  occurs until `Add position`; volume controls use minimum/step 100; successful
  writes invalidate `_POSITION_OVERVIEW_KEY` and rerun.

- [x] **Step 1: Write failing AppTests for controls and popover creation.**

  Assert the Current Positions tab contains three-character `Ticker filter`,
  State selector, `New position`, refresh-icon button, Sort by, and Direction.
  Open the popover, enter lower-case `fpt`, assert the selected saved-set
  callback receives `FPT`, set only BUY fields and volume `100`, then click
  `Add position`. Assert one manual OPEN record has raw BUY price `50300`.
  Add a separate test that one SELL field alone produces the existing paired
  SELL validation error and writes nothing.

- [x] **Step 2: Run the New Position RED gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_page.BacktestPageTests.test_current_positions_toolbar_and_new_popover -v
  ```

  Expected: FAIL because the page has `Add new position`, the old form, and
  `Refresh positions` instead of the approved controls.

- [x] **Step 3: Replace the old add/refresh form path.**

  Remove `_MANUAL_POSITION_FORM_KEY` and the old `Add new position` form. Use
  `with st.popover("New position"):` and normal widgets in three `st.columns`
  rows. Bind ticker text inputs to `_uppercase_ticker_state()` with
  `max_chars=3`, then fetch saved-set options from the normalized value on the
  rerun. Keep saved-set selection optional (`"-"`).

  Replace the text refresh button with a captioned icon button such as
  `st.button("↻", help="Refresh positions")`. Its click alone clears the
  overview cache. Add `Sort by` and `Direction` controls with values from Task
  2 and defaults `Open date`/`ASC`.

  Use shared `min_value=100`, `step=100` for new-position volume and pending
  Validate BUY draft volume. Retain `None` as the optional quantity value.
  Rename the write action to `Add position`; its error message becomes
  `Unable to add position: ...`.

- [x] **Step 4: Run New Position GREEN and prior page regressions.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page -v
  ```

  Expected: all Backtest Lab page tests pass; no old add/refresh labels remain.

- [x] **Step 5: Review this task.**

  Confirm the popover is a native Streamlit 1.32 capability, a typed ticker is
  visibly uppercase, saved-set preparation remains read-only until add, and no
  new direct trade bypass is introduced.

  **Result:** PASS. Streamlit 1.32 AppTest does not expose a popover accessor,
  so the AppTest proves its rendered controls and source uses the native
  `st.popover` context. The focused tests and the Backtest Page suite pass
  27/27. No action writes before `Add position`; the only preparation remains
  the existing read-only saved-signal lookup.

---

### Task 4: One-row inline save, reopen, and permanent delete confirmation — Complete

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: Task 1 store functions; Task 2 editor frame; existing
  `position_locator` structure.
- Produces:

  ```python
  def _update_by_locator(
      locator: Mapping[str, object], updates: Mapping[str, object],
      positions_dir: str, update_position_fn: Callable,
      manual_update_fn: Callable,
  ) -> dict[str, object]: ...

  def _delete_by_locator(
      locator: Mapping[str, object], positions_dir: str,
      delete_position_fn: Callable, manual_delete_fn: Callable,
  ) -> dict[str, object]: ...
  ```

- Guarantees: only one selected row can save/delete, save routes by exact
  locator, delete confirmation contains record summary and writes only after
  confirmation, and all writes refresh derived data by cache invalidation plus
  rerun.

- [x] **Step 1: Write failing routing/helper tests.**

  Test `_update_by_locator()` invokes only `update_position_fn` for a legacy
  locator and only `manual_update_fn` for a manual locator. Do the same for
  `_delete_by_locator()`. Assert missing/invalid locator fields fail before a
  writer is called.

- [x] **Step 2: Run routing RED tests.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_page.BacktestPageTests.test_current_position_locator_routes_inline_update_and_delete -v
  ```

  Expected: FAIL because shared update/delete locator routing does not exist.

- [x] **Step 3: Write failing AppTests for editor lifecycle and delete confirmation.**

  Supply one manual OPEN and one legacy CLOSED overview row. Assert the table
  has editable State/BUY/SELL/date/Volume columns, read-only Ticker/Saved
  signal/derived columns, and `DD/MM/YYYY` audit fields. Select one OPEN row,
  edit it to CLOSED with both SELL values, save, and assert the exact manual
  history record is closed. Select that row, change to OPEN, save, and assert
  closure fields clear.

  For deletion, click `Delete position`, assert the warning contains the
  selected ticker/state/BUY data and the history still contains its ID, then
  click `Confirm permanent delete` and assert only that history record is gone.

  Add a regression where values change in two editor rows but only one is
  selected; assert Save rejects the request and neither history changes.

- [x] **Step 4: Run editor/delete RED gate.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_page.BacktestPageTests.test_current_positions_inline_lifecycle_and_confirmed_delete -v
  ```

  Expected: FAIL because the page still uses per-row expanders/forms and has no
  delete confirmation state.

- [x] **Step 5: Implement one-row editor/actions.**

  Delete `_render_position_edit_form()` and its per-row expanders. Render a
  fixed-row `st.data_editor` from Task 2 with a `Select` checkbox, hidden record
  identity, `SelectboxColumn` State, `DateColumn` BUY/SELL dates, and
  `NumberColumn` volume (`min_value=100`, `step=100`). Disable Ticker, Saved
  signal set, current/derived fields, and audit timestamps.

  `Save changes` requires exactly one selected row. Compare editor values with
  the baseline frame and reject any changed row other than the selected ID;
  this keeps every persistence call atomic to one history record. Convert only
  that row's BUY/SELL UI prices to raw BIGINT and send its complete editable
  candidate to `_update_by_locator()`. A failed validation keeps persisted
  history and shows its error; a successful save clears
  `_POSITION_OVERVIEW_KEY` and reruns.

  `Delete position` requires exactly one selected row and stores its immutable
  locator/summary in a dedicated session-state confirmation key. On the next
  render, show `st.warning` with the saved summary and separate `Confirm
  permanent delete` and Cancel controls. Confirmation uses `st.spinner`, calls
  `_delete_by_locator()`, clears confirmation and overview state, and reruns.
  If selected row changes, cancel the stale confirmation rather than deleting a
  different record.

  Pass default `delete_position` and `delete_manual_position` dependencies from
  `render_backtest_page()` into the tab renderer to keep AppTests injectable.

- [x] **Step 6: Run editor/delete GREEN and store/page regressions.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest \
    tests.test_backtest_page \
    tests.test_backtest_manual_position_store \
    tests.test_backtest_position_store \
    tests.test_backtest_position_overview -v
  ```

  Expected: all focused UI/store/overview tests pass, including legacy/manual
  routing, no pre-confirmation delete, reopening checks, and refreshed P&L
  inputs.

- [x] **Step 7: Review this task.**

  Confirm table edits never mutate ticker/signal identity, derived P&L is never
  user-editable, permanent deletion needs a second explicit action, and the
  Streamlit table has no per-row database query.

  **Result:** PASS. Routing, selected-row/change-set guards, raw/UI conversion,
  lifecycle close/reopen, exact delete, and stale-confirmation cancellation all
  have regression coverage. Streamlit 1.32 AppTest exposes a data editor as a
  dataframe but has no edit interaction API; its rendered-column contract is
  covered while direct helper/store tests exercise the exact persistence path.
  The focused page/store/overview gate passes 58/58. No SQL was added; all
  filters, sorting, and editor work run in memory after the cached overview.

---

### Task 5: Full verification and documentation handoff — Complete

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-12-current-positions-inline-management-verification.md`

**Interfaces:**

- Consumes: all completed Tasks 1-4 and test results.
- Produces: completed plan checklist, verification evidence, and a precise
  resume point with no changed protected boundary.

- [x] **Step 1: Run the complete package-qualified Backtest gate.**

  Run:

  ```powershell
  $backtestModules = Get-ChildItem tests -Filter 'test_backtest*.py' |
    ForEach-Object { 'tests.' + $_.BaseName }
  docker exec stock_app python -m unittest $backtestModules
  ```

  Expected: zero failures; keep package-qualified names because generic test
  discovery has the documented fixture/import limitation.

- [x] **Step 2: Compile and inspect boundaries.**

  Run:

  ```powershell
  docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py
  git diff --check
  Get-FileHash app/commons/common_queries.py, app/pages/data_preparation.py, app/main.py, docker/Dockerfile, docker/docker-compose.yml, requirements.txt
  ```

  Expected: compilation/diff check pass; every protected-file hash matches the
  Task 1 baseline. Existing unrelated Git diffs are preserved and ignored.

- [x] **Step 3: Run a headless Streamlit smoke.**

  In Backtest Lab → Current Positions, verify: lowercase filter normalizes,
  OPEN default is oldest first, each sort/direction works, refresh icon reloads,
  New position popover supports optional saved set, UI volume increments by
  100, one row saves/reopens correctly, and delete retains the record until
  the permanent-confirmation action.

- [x] **Step 4: Run implementation review and fix findings.**

  Read and execute `ai-skills/skill-implementation-review.md`. Address every
  logic, performance, SQL, comment, or boundary finding before completion.

- [x] **Step 5: Record completion.**

  Mark all plan steps complete only after evidence exists. Update `FOCUS.md`,
  `ai-context/current-status.md`, and the verification report with exact test
  count, smoke outcome, known limitations, and no-commit statement.

  **Result:** PASS. The final package-qualified Backtest gate passes 185 with
  one expected skip; compilation, whitespace inspection, and protected-hash
  comparison pass. The running app returned `200 ok` from its configured
  Streamlit port `3501`. Full evidence and the Streamlit-AppTest interaction
  limitation are recorded in
  `docs/superpowers/reports/2026-08-12-current-positions-inline-management-verification.md`.

## Plan Self-Review

| Requirement | Task coverage |
| --- | --- |
| Two-row filter/refresh/sort controls; default Open date ASC | Tasks 2-3 |
| Native popup creation and required three-row fields | Task 3 |
| Volume minimum/step 100 | Task 3 and Task 4 |
| Inline editable state/prices/dates/volume; immutable ticker/signal | Tasks 1 and 4 |
| OPEN/CLOSED bidirectional lifecycle | Tasks 1 and 4 |
| DD/MM/YYYY audit dates and post-write data refresh | Tasks 2 and 4 |
| Exact legacy/manual permanent deletion after confirmation | Tasks 1 and 4 |
| Tests, review, docs, and boundary checks | Task 5 |

No placeholders remain. The plan has one lifecycle contract per store, one pure
presentation contract, and one UI orchestration contract; it does not introduce
new storage, SQL, dependencies, or a multi-row transaction.
