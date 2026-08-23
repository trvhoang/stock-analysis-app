# Backtest Signal Tabs and Batch Group Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared View Signals tab, requested control layouts, and serial
group-based Validate Signals batches without changing signal/risk behavior.

**Architecture:** Keep the page-local UI in `pages/backtest_lab.py`. Add small
pure helpers there for ticker resolution, 15-ticker chunking, batch service
execution, and ticker-keyed validation state. Reuse the existing group store
only through its public choice/resolution functions. Native Streamlit tabs
remain; View Signals is a direct second tab, not a popover or programmatic
navigation target.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, unittest/AppTest, Docker.

## Global Constraints

- Tab order is exactly Collect Signals, View Signals, Validate Signals,
  Current Positions, Validate Positions.
- No View Signals button or popover remains in Collect or Validate.
- Manual Collect and Validate ticker input accepts 1–15 unique comma/space
  separated symbols.
- Validate group choices are `-`, `N/A`, then defined groups; non-`-` locks
  the resolved ticker textbox and runs every member serially in 15-ticker
  chunks.
- A failed ticker never stops later ticker validation; results preserve input
  or resolved-group order.
- Preserve schema-4 rules, raw-BIGINT handling, SQL, artifacts, positions,
  SELL advice, risk formulas, dependencies, Docker files, and credentials.
- Use `apply_patch` for every edit. Do not run Git commands or create commits.

---

### Task 1: Pure batch-validation and ticker-keyed state helpers

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: `parse_batch_tickers(value, maximum=15)`,
  `resolve_group_tickers(selection, signal_dir)`, and existing single-ticker
  `validate_saved_signals(ticker, engine, signal_dir, positions_dir)`.
- Produces:
  - `_validation_tickers(tickers_text: str, group_name: str, signal_dir: str,
    group_resolver: Callable) -> tuple[str, ...]`
  - `_ticker_chunks(tickers: tuple[str, ...], size: int = 15) -> tuple[tuple[str, ...], ...]`
  - `_run_validation_batches(tickers: tuple[str, ...], engine, signal_dir: str,
    positions_dir: str, validate_fn: Callable) -> dict[str, object]`
  - `_validation_result_for_ticker(value: object, ticker: str) -> dict[str, object] | None`

- [x] **Step 1: Write failing helper tests.**

  Add to `BacktestPageTests` in `tests/test_backtest_page.py`:

  ```python
  def test_validation_tickers_uses_manual_limit_or_every_resolved_group_member(self):
      self.assertEqual(
          backtest_lab._validation_tickers("fpt, vcb", "-", "signals", lambda *_: ()),
          ("FPT", "VCB"),
      )
      self.assertEqual(
          backtest_lab._validation_tickers("ignored", "BANK", "signals", lambda *_: ("VCB", "TCB")),
          ("VCB", "TCB"),
      )
      with self.assertRaisesRegex(ValueError, "between 1 and 15"):
          backtest_lab._validation_tickers(" ".join(f"T{i}" for i in range(16)), "-", "signals", lambda *_: ())
      with self.assertRaisesRegex(ValueError, "no tickers"):
          backtest_lab._validation_tickers("ignored", "N/A", "signals", lambda *_: ())

  def test_validation_batches_chunk_group_members_continue_after_failure_and_preserve_order(self):
      calls = []
      def validate(ticker, *_args):
          calls.append(ticker)
          if ticker == "T16":
              raise ValueError("broken artifact")
          return {"ticker": ticker, "results": [], "historical_positions": []}

      tickers = tuple(f"T{i}" for i in range(1, 18))
      batch = backtest_lab._run_validation_batches(tickers, object(), "signals", "positions", validate)

      self.assertEqual(calls, list(tickers))
      self.assertEqual(
          batch["chunks"],
          (tuple(f"T{i}" for i in range(1, 16)), ("T16", "T17")),
      )
      self.assertEqual(list(batch["by_ticker"]), [ticker for ticker in tickers if ticker != "T16"])
      self.assertEqual(batch["errors"], {"T16": "broken artifact"})
  ```

- [x] **Step 2: Run RED.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_validation_tickers_uses_manual_limit_or_every_resolved_group_member tests.test_backtest_page.BacktestPageTests.test_validation_batches_chunk_group_members_continue_after_failure_and_preserve_order -v
  ```

  Expected: import or attribute failures for all new helpers.

- [x] **Step 3: Implement only helpers.**

  In `app/pages/backtest_lab.py`, import public group functions:

  ```python
  from backtest_engine.result_store import (
      list_validation_group_choices,
      resolve_group_tickers,
  )
  ```

  Add helpers after `parse_batch_tickers`:

  ```python
  def _validation_tickers(tickers_text, group_name, signal_dir, group_resolver):
      if group_name == "-":
          return parse_batch_tickers(tickers_text)
      tickers = tuple(group_resolver(group_name, signal_dir))
      if not tickers:
          raise ValueError("Selected Ticker group has no tickers.")
      return tickers

  def _ticker_chunks(tickers, size=15):
      return tuple(tuple(tickers[index:index + size]) for index in range(0, len(tickers), size))

  def _run_validation_batches(tickers, engine, signal_dir, positions_dir, validate_fn):
      by_ticker, errors = {}, {}
      chunks = _ticker_chunks(tickers)
      for chunk in chunks:
          for ticker in chunk:
              try:
                  by_ticker[ticker] = validate_fn(ticker, engine, signal_dir, positions_dir)
              except (OSError, ValueError) as error:
                  errors[ticker] = str(error)
      return {"chunks": chunks, "by_ticker": by_ticker, "errors": errors}

  def _validation_result_for_ticker(value, ticker):
      if isinstance(value, Mapping) and value.get("ticker") == ticker:
          return value
      if isinstance(value, Mapping):
          candidate = value.get("by_ticker", {}).get(ticker)
          return candidate if isinstance(candidate, dict) else None
      return None
  ```

  Keep exception scope restricted to expected service failures. Let malformed
  injected test doubles surface as tests, rather than treating programming
  errors as ticker failures.

- [x] **Step 4: Run GREEN.**

  Re-run Step 2 command. Expected: both tests pass.

- [x] **Step 5: Refactor shared saved-set lookup.**

  Change `_validated_v4_candidates` to obtain `validation` through
  `_validation_result_for_ticker(validation, ticker)` before reading
  `results`. Preserve its legacy single-result input compatibility. Add a
  focused assertion:

  ```python
  self.assertEqual(
      backtest_lab._validation_result_for_ticker(
          {"by_ticker": {"FPT": {"ticker": "FPT", "results": []}, "VCB": {"ticker": "VCB", "results": []}}, "errors": {}},
          "VCB",
      )["ticker"],
      "VCB",
  )
  ```

- [x] **Step 6: Re-run Task 1 tests.**

  Run Step 2 command plus the existing saved-set page tests. Expected: all
  pass.

### Task 2: Shared View Signals tab and Collect layout

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: `_render_view(signal_dir)` unchanged.
- Produces: five native tab containers in required order; two-row Collect
  controls without a View Signals popover.

- [x] **Step 1: Write failing page-contract test.**

  Replace the old four-tab/popover assertions with:

  ```python
  self.assertEqual(
      [tab.label for tab in app.tabs],
      ["Collect Signals", "View Signals", "Validate Signals", "Current Positions", "Validate Positions"],
  )
  self.assertEqual(
      inspect.getsource(backtest_lab._render_collect).count('st.popover("View Signals")'),
      0,
  )
  self.assertEqual(
      inspect.getsource(backtest_lab._render_validate).count('st.popover("View Signals")'),
      0,
  )
  ```

  Add an AppTest assertion that Collect has `Tickers`, `Horizon`, `Range`,
  `Group (optional)`, and `Run Backtest`, while View Signals has title
  `View Signals`.

- [x] **Step 2: Run RED.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_backtest_page_has_shared_view_signals_tab_and_no_view_popovers -v
  ```

  Expected: old four-tab/popover implementation fails.

- [x] **Step 3: Implement tab and Collect layout.**

  In `render_backtest_page`, construct five `st.tabs` values in exact order
  and render `_render_view(signal_dir)` only in the second container. In
  `_render_collect`, use `st.columns` twice: row one for `Tickers`; row two
  for Horizon, Range, Group, and Run Backtest. Do not alter widget keys,
  `parse_batch_tickers`, or job-state behavior. Update existing AppTest tab
  indexing so Validate Positions is checked at index `4`, not `3`.

- [x] **Step 4: Run GREEN.**

  Re-run Step 2 command. Expected: passes, with no View Signals popover.

### Task 3: Validate layout, locked groups, and serial batch rendering

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: Task 1 helpers, `list_validation_group_choices`,
  `resolve_group_tickers`, and single-ticker `validate_fn` injection.
- Produces: group-locked Validate input and per-ticker validation render path.

- [x] **Step 1: Write failing AppTests.**

  Add a helper app that injects:

  ```python
  group_choices_fn=lambda _dir: ("-", "N/A", "BANK"),
  group_resolver_fn=lambda name, _dir: ("VCB", "TCB") if name == "BANK" else (),
  validate_fn=lambda ticker, *_args: {"ticker": ticker, "results": [], "historical_positions": []},
  ```

  Assert all of the following:

  ```python
  group = next(item for item in app.selectbox if item.label == "Ticker group")
  self.assertEqual(group.value, "-")
  self.assertTrue(any(item.label == "Monitoring classifications" for item in app.multiselect))

  group.set_value("BANK").run()
  ticker_box = next(item for item in app.text_input if item.label == "Tickers")
  self.assertEqual(ticker_box.value, "VCB TCB")
  self.assertTrue(ticker_box.disabled)
  ```

  Then click Validate and assert service calls are `VCB`, `TCB` in order and
  both ticker headings render. Add a 17-ticker group fixture asserting call
  order includes all 17 names, not only first 15. Add a failing middle ticker
  fixture asserting later ticker result still renders its success.

- [x] **Step 2: Run RED.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_validate_group_locks_resolved_tickers_and_runs_every_member tests.test_backtest_page.BacktestPageTests.test_validate_group_continues_after_ticker_failure -v
  ```

  Expected: no Ticker group control and single-ticker validation behavior fail.

- [x] **Step 3: Implement Validate UI and rendering.**

  Extend `_render_validate` dependencies with optional injected
  `group_choices_fn=list_validation_group_choices` and
  `group_resolver_fn=resolve_group_tickers`. Read the selected group from
  session state before creating row-one controls, so the visible layout remains
  ticker first while a rerun after group selection immediately locks it. Render:

  ```python
  active_group = st.session_state.get("backtest_validate_group_v4", "-")
  resolved = () if active_group == "-" else _validation_tickers("", active_group, signal_dir, group_resolver_fn)
  if active_group == "-":
      tickers_text = st.text_input("Tickers", key="backtest_validate_tickers_v4")
  else:
      tickers_text = st.text_input(
          "Tickers", value=" ".join(resolved), disabled=True,
          key="backtest_validate_group_tickers_v4",
      )
  group_name = st.selectbox("Ticker group", group_choices_fn(signal_dir), key="backtest_validate_group_v4")
  ```

  Avoid changing an existing Streamlit widget's session-state value after it
  is instantiated. Use separate manual/locked widget keys when needed, then
  pass the currently displayed text to `_validation_tickers`.

  Pass `group_choices_fn` and `group_resolver_fn` through
  `render_backtest_page` as injectable arguments for AppTest. On Validate,
  call `_validation_tickers(tickers_text, group_name, signal_dir,
  group_resolver_fn)`, then call `_run_validation_batches`; write its returned
  batch object to `backtest_v4_validation_result`. Render errors as `Validate <ticker>
  failed: <message>`, then render every successful ticker with a ticker
  subheader followed by current rulebook expanders/filtering/historical notice.
  Extract the existing single-result expander body into a helper such as
  `_render_validation_result(ticker, result, allowed)` so output is identical
  for every ticker. Keep output order from `tickers`, never dictionary sort.

- [x] **Step 4: Run GREEN.**

  Re-run Step 2 command. Expected: all group locking, all-member serial calls,
  continuation, and ordering assertions pass.

- [x] **Step 5: Run focused page suite.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page -v
  ```

  Expected: existing position/risk UI contracts and new tab/group tests pass.

### Task 4: Completion review and context sync

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/plans/2026-08-22-backtest-signal-tabs-and-batch-group-validation.md`
- Create: `docs/superpowers/reports/2026-08-22-backtest-signal-tabs-and-batch-group-validation-verification.md`

**Interfaces:** No product interface changes.

- [x] **Step 1: Run final regression and compilation.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_validation_advice tests.test_backtest_result_store -v
  docker exec stock_app python -m compileall -q pages/backtest_lab.py backtest_engine/result_store.py backtest_engine/validation_advice.py
  ```

  Expected: all tests pass and compile produces no output.

- [x] **Step 2: Run static boundary checks.**

  Run:

  ```powershell
  rg -n "st\.popover\(\"View Signals\"\)" app/pages/backtest_lab.py
  rg -n "load_rulebook_result|load_current_rulebook_document|load_all_positions|load_position_history" app/pages/backtest_lab.py
  rg -n "[ \t]+$" app/pages/backtest_lab.py tests/test_backtest_page.py
  ```

  Expected: first and third searches have no output; the second search only
  shows existing allowed direct rendering imports, not new batch logic. Do not
  run Git checks.

- [x] **Step 3: Perform implementation self-review.**

  Confirm: exact tab order; no View Signals buttons/popovers; manual ticker
  cap still 15; `N/A` uses existing resolver semantics; selected groups run all
  members in 15-ticker chunks; service calls are serial; failure isolation and
  display order hold; ticker-keyed state feeds New Position; no schema/SQL/
  BIGINT/risk/SELL changes occurred. Correct every finding before proceeding.

- [x] **Step 4: Record evidence and completion state.**

  Write the verification report with actual command totals, files changed,
  known limitation that native Streamlit 1.32 tabs are direct-select only, and
  no Git action. Mark every completed checkbox in this plan. Update FOCUS and
  current status without claiming Phase B complete unless its separate
  verification gate is complete.
