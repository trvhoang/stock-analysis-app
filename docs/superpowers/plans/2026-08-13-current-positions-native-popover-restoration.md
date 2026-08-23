# Current Positions Native Popover Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the compact native New position popover while keeping every existing creation validation and persistence rule unchanged.

**Architecture:** `st.popover("New position")` owns the form contents and native browser interaction. Streamlit 1.32 has no supported programmatic popover-close API, so there is no inner close control; users dismiss the unsaved form by clicking outside it or pressing Escape. A focused source comment records the exact version limitation and upgrade decision point.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest with Streamlit AppTest.

## Global Constraints

- No SQL, schema, BIGINT scaling, dependency, Docker, credential, or commit-history change.
- Preserve direct manual OPEN/CLOSED position creation, ticker capitalization, saved-signal lookup, frozen-risk snapshot, and field validation.
- Do not add JavaScript, CSS selectors, custom components, or a dependency to force-close a popover.
- No commit: the user manages commits separately.

---

### Task 1: Restore the native New Position popover

**Files:**
- Modify: `app/pages/backtest_lab.py:77,1675-1808,1866-1877`
- Modify: `tests/test_backtest_page.py:358-615,1016-1021`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Interfaces:**
- Consumes: Streamlit 1.32 `st.popover(label, help=None, disabled=False, use_container_width=False)`.
- Produces: `_render_new_position_popover(...) -> None`, rendering the same inputs and calling the existing `manual_position_fn(...)` unchanged.

- [x] **Step 1: Write failing native-popover regression tests**

  Replace panel-specific source assertions with `_render_new_position_popover`
  and `with st.popover("New position")`. Assert `app.get("popover")` contains
  the New position form controls, then retain ticker-normalization and manual
  creation coverage through those controls. Remove the test requiring the
  unsupported inner Close button. Streamlit 1.32 AppTest has no action that
  opens or dismisses a popover, so native browser click-outside/Escape behavior
  remains a documented manual-runtime limitation.

- [x] **Step 2: Run focused tests to verify failure**

  Run:

  ```powershell
  docker exec stock_app python -m unittest `
    tests.test_backtest_page.BacktestPageTests.test_current_position_visible_selection_and_toolbar_layout `
    tests.test_backtest_page.BacktestPageTests.test_new_position_popover_exposes_creation_form -v
  ```

  Expected: failure because the page still exposes `_render_new_position_panel`
  and has no native popover.

- [x] **Step 3: Restore the minimal native-popover implementation**

  Delete `_NEW_POSITION_PANEL_OPEN_KEY`, remove panel placeholders and the Close button, rename the helper to `_render_new_position_popover`, and wrap the unchanged form in:

  ```python
  # TODO(streamlit-upgrade): add an explicit dismiss action only when the
  # supported Streamlit API can close a native popover programmatically.
  with st.popover("New position"):
      ...
  ```

  On successful creation, keep the existing overview invalidation and
  selection clearing, then call `rerun_fn()`. No behavior is added for an
  unsaved dismissal because native click-outside/Escape already provides it.

- [x] **Step 4: Run focused tests to verify success**

  Re-run the command from Step 2. Expected: all selected tests pass.

- [x] **Step 5: Run final verification**

  Run:

  ```powershell
  docker exec stock_app python -m unittest (Get-ChildItem tests -Filter 'test_backtest*.py' | ForEach-Object { 'tests.' + $_.BaseName })
  docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py
  git diff --check
  ```

  Expected: Backtest package gate succeeds with only its documented expected
  skip; compile and whitespace checks exit zero.

- [x] **Step 6: Review and synchronize task records**

  Verify no query, store, or scaling path changed. Mark this focused UI item
  complete in `FOCUS.md` and `ai-context/current-status.md`, record test
  counts and native-dismiss limitation, and do not create a commit.
