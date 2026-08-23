# Collect Signals Group Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline test-driven execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Collect Signals create a named Group at run time or run a selected existing Group's members.

**Architecture:** `backtest_lab.py` reuses the injected group-choice and member-resolver dependencies already used by Validate Signals. It converts UI state to the unchanged `BacktestBatchConfig`; the existing pipeline remains the only writer of group JSON.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest/AppTest.

## Global Constraints

- Default Group is exactly `N/A`.
- Existing selected Groups disable Tickers and use all their members.
- A new Group saves only when Run Backtest triggers the existing pipeline.
- No SQL, persistence, raw-BIGINT scaling, artifact, dependency, Docker, or Git change.

---

### Task 1: Test group selection routes

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**
- Consumes: `group_choices_fn(signal_dir)` and `group_resolver_fn(group_name, signal_dir)`.
- Produces: Collect `Group` selection, disabled resolved Tickers, and unchanged `BacktestBatchConfig.group_name` submission.

- [x] Add AppTest coverage that expects a default `N/A` Group selector and,
  after selecting `BANK`, disabled Tickers value `VCB TCB` from the injected
  resolver.
- [x] Run RED: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [x] Update `_render_collect()` to accept the existing group dependencies;
  render `N/A`, `New group…`, and named groups. Resolve a selected named group
  before rendering its disabled Tickers control. Reject a blank or existing
  `New group name` when Run Backtest is clicked.
- [x] Pass the dependencies through `render_backtest_page()` and keep
  `build_backtest_batch_config()` plus pipeline group persistence unchanged.
- [x] Run GREEN: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [x] Run compilation: `docker exec stock_app python -m compileall -q pages/backtest_lab.py tests/test_backtest_page.py`.
