# View Signals Ticker and Horizon Filters Implementation Plan

> **For agentic workers:** Execute test-first in the shared workspace. Do not
> perform Git actions, commits, or commit-tree changes.

**Goal:** Add local ticker and horizon filtering to the View Signals table.

**Architecture:** Keep the current catalog projection pure, then apply a small
pure row filter before the existing dataframe renderer. Streamlit owns only the
two filter widgets and their session keys.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest/AppTest.

## Global Constraints

- Horizon options are exactly `Both`, `Swing`, and `Mid-term`; default `Both`.
- Ticker is uppercase, case-insensitive, and partial-match.
- Filters use AND semantics and are read-only.
- No Git action, artifact/catalog mutation, SQL, or dependency change.

### Task 1: Test and render local View Signals filters

**Files:**

- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

- [x] Write a failing test for ticker/horizon intersection, including default
  `Both` behavior.
- [x] Run the focused Docker test and confirm the new test fails because the
  row filter does not exist.
- [x] Add the minimal pure filter and render a ticker input plus Horizon
  selectbox before the existing dataframe.
- [x] Re-run focused and full Backtest page tests, then compile the module.

### Task 2: Verify and document

**Files:**

- Create: `docs/superpowers/reports/2026-08-23-view-signals-ticker-horizon-filter-verification.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

- [x] Review the code against project UI, SQL, and performance rules.
- [x] Record exact test and compilation evidence.
- [x] Record the completed UI change and its read-only boundary in project
  status files.
