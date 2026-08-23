# View Signals Summary Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show View Signals as a concise preferred-treatment train/test table
without rendering terminal rows or changing schema-4/V3 artifacts.

**Architecture:** Add a pure page-local projection from existing catalog rows
to eight visible columns. `_render_view` consumes only that projection and
retains warnings. `signal_catalog.py` remains untouched, so terminal JSON and
all catalog consumers retain current behavior.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, unittest/AppTest, Docker.

## Global Constraints

- Visible column order is exactly Ticker, Horizon, Theme, Train-test, n, Win
  rate %, Profit %, Sharpe.
- Metrics show `train - test`; absent scalar values show `N/A` without
  rounding or rescaling.
- Theme mapping: `background-theme` is Included; every other value is Excluded.
- Train-test is YES only when Training n and Test n keys both exist, even when
  their values are zero or `None`.
- Do not modify schema-4/V3 JSON, `signal_catalog.py`, terminal JSON, rules,
  SQL, prices, positions, dependencies, Docker, or credentials.
- Use `apply_patch` for edits. Do not run Git commands or create commits.

---

### Task 1: Pure summary projection and terminal-free render

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Consumes: `list_current_signal_set_rows(signal_dir)` valid/terminal/warning
  mapping, unchanged.
- Produces: `_view_signal_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]`.

- [x] **Step 1: Write failing projection and render tests.**

  Add a pure projection test:

  ```python
  def test_view_signal_rows_show_only_summary_train_test_columns(self):
      rows = backtest_lab._view_signal_rows([{
          "Ticker": "VCB", "Horizon": "Swing",
          "Preferred treatment": "background-theme",
          "Training n": 5, "Test n": 0,
          "Training win rate %": 60.0, "Test win rate %": None,
          "Training profit %": 3.2, "Test profit %": -1.0,
          "Training Sharpe": 0.4, "Test Sharpe": None,
          "Rulebook": "hidden", "Selected gates": ["hidden"],
          "Treatments": {"hidden": True}, "Evaluation": "hidden",
      }])

      self.assertEqual(list(rows[0]), ["Ticker", "Horizon", "Theme", "Train-test", "n", "Win rate %", "Profit %", "Sharpe"])
      self.assertEqual(rows[0], {
          "Ticker": "VCB", "Horizon": "Swing", "Theme": "Included",
          "Train-test": "YES", "n": "5 - 0",
          "Win rate %": "60.0 - N/A", "Profit %": "3.2 - -1.0",
          "Sharpe": "0.4 - N/A",
      })
  ```

  Add a render AppTest that patches page-local `list_current_signal_set_rows`
  to return one valid row, one terminal row, and one warning. Assert exactly
  one dataframe with the eight columns, no `Terminal results` caption, and
  preserved warning.

- [x] **Step 2: Run RED.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_view_signal_rows_show_only_summary_train_test_columns tests.test_backtest_page.BacktestPageTests.test_view_signals_render_omits_terminal_rows -v
  ```

  Expected: missing projection helper and current terminal dataframe/caption
  fail.

- [x] **Step 3: Implement projection and render change.**

  Add page-local helpers before `_render_view`:

  ```python
  _VIEW_SIGNAL_COLUMNS = (
      "Ticker", "Horizon", "Theme", "Train-test", "n", "Win rate %",
      "Profit %", "Sharpe",
  )

  def _view_metric(value):
      return "N/A" if value is None or pd.isna(value) else str(value)

  def _view_signal_rows(rows):
      output = []
      for row in rows:
          train_test = "YES" if "Training n" in row and "Test n" in row else "NO"
          def paired(metric):
              return f"{_view_metric(row.get('Training ' + metric))} - {_view_metric(row.get('Test ' + metric))}"
          output.append({
              "Ticker": row.get("Ticker"), "Horizon": row.get("Horizon"),
              "Theme": "Included" if row.get("Preferred treatment") == "background-theme" else "Excluded",
              "Train-test": train_test, "n": paired("n"),
              "Win rate %": paired("win rate %"),
              "Profit %": paired("profit %"), "Sharpe": paired("Sharpe"),
          })
      return output
  ```

  Update `_render_view` to pass `catalog["valid"]` through
  `_view_signal_rows`, render that dataframe only when nonempty, remove the
  terminal caption/dataframe block, and leave warning rendering unchanged.

- [x] **Step 4: Run GREEN.**

  Re-run Step 2 command. Expected: both tests pass.

- [x] **Step 5: Run focused regressions.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
  ```

  Expected: page projection passes and catalog still exposes its existing raw
  schema-4 fields to non-UI callers.

### Task 2: Verification and context sync

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/plans/2026-08-22-view-signals-summary-columns.md`
- Create: `docs/superpowers/reports/2026-08-22-view-signals-summary-columns-verification.md`

- [x] **Step 1: Run final tests and compilation.**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
  docker exec stock_app python -m compileall -q pages/backtest_lab.py backtest_engine/signal_catalog.py
  ```

  Expected: all named tests pass; compilation has no output.

- [x] **Step 2: Run static checks.**

  Run:

  ```powershell
  rg -n "Terminal results|catalog\[\"terminal\"\]" app/pages/backtest_lab.py
  rg -n "[ \t]+$" app/pages/backtest_lab.py tests/test_backtest_page.py docs/superpowers/specs/2026-08-22-view-signals-summary-columns-design.md docs/superpowers/plans/2026-08-22-view-signals-summary-columns.md
  ```

  Expected: no output. Do not run Git checks.

- [x] **Step 3: Self-review and record evidence.**

  Confirm all eight columns/order, theme mapping, train/test pairing, missing
  values, terminal suppression, warnings, and unchanged `signal_catalog.py`.
  Record actual test totals, compilation/static results, changed files, and
  no Git action. Mark plan steps complete and update status without marking
  separate Validate Positions Phase B work complete.
