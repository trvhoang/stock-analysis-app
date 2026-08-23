# View Signals and New Position Layout Implementation Plan

> **For agentic workers:** Use `executing-plans` task-by-task. Checkbox steps track work.

**Goal:** Round displayed View Signals metrics to one decimal, cap table height
at 20 rows, and arrange New Position fields in requested rows.

**Architecture:** Page-only presentation changes in `backtest_lab.py`; no data
or persistence changes.

## Constraints

- One decimal only for Win rate %, Profit %, Sharpe; n and N/A unchanged.
- View Signals uses native scrolling after approximately 20 rows (`height=720`).
- Preserve all widget keys/form semantics; no Git action.

### Task 1: TDD presentation changes

**Files:** Modify `app/pages/backtest_lab.py`, `tests/test_backtest_page.py`.

- [ ] Write failing tests asserting `60.04 - N/A` renders `60.0 - N/A`, n is
  unchanged, View Signals dataframe height is `720`, and New Position source
  creates rows with `st.columns((1, 2, 1))`, `st.columns(3)`,
  `st.columns(2)`, then `st.form_submit_button`.
- [ ] Run RED: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [ ] Implement `_view_metric(value, decimals=None)` and use one decimal for
  Win rate %, Profit %, Sharpe pairs; pass `height=720` to View Signals
  dataframe; arrange existing New Position widgets in requested columns.
- [ ] Run GREEN: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.

### Task 2: Verification

**Files:** Modify `FOCUS.md`, `ai-context/current-status.md`, this plan; create
`docs/superpowers/reports/2026-08-22-view-signals-and-new-position-layout-verification.md`.

- [ ] Run `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v` and `docker exec stock_app python -m compileall -q pages/backtest_lab.py`.
- [ ] Self-review UI-only boundary; run trailing-whitespace check; record actual
  totals, mark steps complete, update context. Do not run Git.
