# View Current Signal Sets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users open a read-only Collect Signals popover that lists every current saved signal set in the system.

**Architecture:** A new catalog reader scans only the expected current ticker/theme JSON artifact paths and converts certified metric sets into presentation rows. Collect Signals renders the rows inside a native Streamlit popover beside Run backtest, so click-outside and Escape retain their framework-native close behavior. Invalid artifact files become warning rows with the same user-approved nine columns; their detailed error is rendered as a warning, not as a new table column.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, unittest with Streamlit AppTest.

## Global Constraints

- Read current signal artifacts only; never replay, certify, submit a job, write a file, or change a position.
- Place `View Signals` beside `Run backtest` in Collect Signals; do not add action controls inside its popover.
- Use native `st.popover` for click-outside and Escape close behavior; do not add a manual close button or session-state panel.
- Valid rows use exactly: Ticker, Theme (`YES`/`NO`), Metric, Horizon (`Swing`/`Mid-term`), Certified at, n, Win rate %, Profit %, Sharpe.
- Invalid rows use the same nine columns only, receive red highlighting, and have a separate visible warning identifying the artifact and failure reason.
- If no invalid artifact exists, render only `All`; otherwise render `All`, `Valid`, `Invalid` in that order with `All` first.
- Preserve checkbox defaults/disabled state, job submission/locking, signal persistence, current JSON overwrite semantics, SQL, BIGINT pricing, dependencies, Docker, credentials, and commit history.
- No commit: the user manages commits separately.

---

### Task 1: Read all current saved-signal artifacts safely

**Files:**
- Modify: `app/backtest_engine/signal_catalog.py:21-95`
- Modify: `tests/test_backtest_signal_catalog.py`

**Interfaces:**
- Consumes: `signal_dir/ticker/ticker_signals_{theme_variant}.json`, existing
  `load_certified_signals()`, `_METRICS`, and `THEME_VARIANTS`.
- Produces: `list_current_signal_set_rows(signal_dir: str = "ticker-signals") -> dict[str, list[dict[str, object]]]` with `valid` and `invalid` rows.

- [x] **Step 1: Write the failing catalog tests**

  Use a temporary artifact directory. Create one valid saved document with
  `save_certified_signals()` and one malformed expected artifact file. Assert:

  ```python
  catalog = list_current_signal_set_rows(directory)
  self.assertEqual(catalog["valid"][0], {
      "Ticker": "TCB",
      "Theme": "YES",
      "Metric": "Win Rate",
      "Horizon": "Swing",
      "Certified at": "2026-08-11T22:34:24.717629+07:00",
      "n": 65,
      "Win rate %": 49.23,
      "Profit %": 71.69,
      "Sharpe": 0.25,
  })
  self.assertEqual(catalog["invalid"][0]["Ticker"], "BAD")
  self.assertEqual(catalog["invalid"][0]["Theme"], "NO")
  self.assertIn("invalid", catalog["invalid"][0]["_issue"].casefold())
  ```

  Assert `None` metric slots create no valid rows, ordering is ticker then
  no-theme before themed then metric order, and the function creates no files.

- [x] **Step 2: Run the focused catalog tests to prove RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_catalog -v
  ```

  Expected: FAIL because `list_current_signal_set_rows` does not exist.

- [x] **Step 3: Implement the minimal catalog reader**

  Add `list_current_signal_set_rows()` to `signal_catalog.py`. For sorted
  ticker directories and each existing expected theme file, use the existing
  loader and validation conventions. Convert every non-null certified metric
  into the exact display schema above: `Win Rate`, `% Profit`, or `Sharpe` and
  its original ISO certification timestamp. On an artifact read/shape failure,
  append one invalid row with the same display columns, blank numeric values
  for unavailable metrics, plus private `_source` and `_issue` metadata for
  renderer warnings.
  Do not treat missing expected files or null metric slots as invalid.

- [x] **Step 4: Run the focused catalog tests to prove GREEN**

  Run the command from Step 2.

  Expected: PASS; valid and invalid rows are deterministic and read-only.

### Task 2: Render native View Signals popover

**Files:**
- Modify: `app/pages/backtest_lab.py:45-65, 2039-2091, 2101-2166`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- Consumes: `list_current_signal_set_rows(signal_dir) -> {"valid": rows, "invalid": rows}`.
- Produces: `_render_current_signal_catalog(catalog: Mapping[str, object]) -> None` and a `View Signals` native popover beside the unchanged Run backtest control.

- [x] **Step 1: Write failing popover AppTests**

  Inject a deterministic catalog containing one valid row and one invalid row
  into `render_backtest_page()`. Assert the rendered button/popover is named
  `View Signals`, `All`, `Valid`, and `Invalid` tabs appear in that order, no
  action control appears in the popover, the valid row appears in the table,
  and a warning includes the invalid artifact reason. Add a no-invalid catalog
  test asserting only `All` appears.

- [x] **Step 2: Run the focused page tests to prove RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_view_signals_popover_lists_valid_and_invalid_rows -v
  ```

  Expected: FAIL because the page accepts no catalog injection and has no View
  Signals popover.

- [x] **Step 3: Implement the smallest popover renderer**

  Add the catalog reader as an injectable `render_backtest_page()` dependency.
  Render `Run backtest` and `st.popover("View Signals")` in two columns below
  the Collect Signals inputs. In the popover, render artifact warnings before
  the tables. Use `st.dataframe(..., use_container_width=True)` for the nine
  visible columns; use a pandas `Styler` only to give rows with private `_issue`
  metadata a red background. Render tabs only when invalid rows exist. Do not
  render a button, form, selectbox, checkbox, or close control in the popover.

- [x] **Step 4: Run focused Page tests to prove GREEN**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
  ```

  Expected: PASS for popover existence, valid/invalid tabs, empty catalog,
  native controls, and existing page behavior.

- [x] **Step 5: Review and synchronize records**

  Complete the implementation-review checklist: no price/SQL/data integrity
  path changed, no writes/replays/jobs happen in the catalog reader, and no
  N+1 database work is introduced. Run the combined page/catalog gates,
  compilation, `git diff --check`, and live Streamlit health. Update FOCUS,
  current status, and a verification report; record no commit.
