# Collect Signals Edit Group Implementation Plan

> **For agentic workers:** Execute test-first. Do not perform Git actions,
> commits, or commit-tree changes.

**Goal:** Atomically edit the members of a selected named Collect Group from a
hidden-by-default popover.

**Architecture:** Add one replace-membership operation to the existing Group
journal store. The Collect popover keeps draft state local, then calls that
operation once on Save Group and reruns the page to refresh locked Tickers.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest/AppTest.

## Constraints

- Row 1: Tickers, Group, Edit Group; row 2: Horizon, Range, Run Backtest.
- Edit Group appears only for named Groups; N/A and New group… cannot edit.
- Save is atomic and permits empty named Groups.
- No automatic backtest; no SQL, prices, artifacts/jobs, positions, rulebooks,
  dependencies, Docker, credentials, or Git changes.

### Task 1: Atomic Group replacement

**Files:** `app/backtest_engine/result_store.py`,
`tests/test_backtest_result_store.py`

- [ ] Write a failing test:

```python
replace_group_tickers("BANK", ("FPT",), directory)
self.assertEqual(resolve_group_tickers("BANK", directory), ("FPT",))
replace_group_tickers("BANK", (), directory)
self.assertEqual(resolve_group_tickers("BANK", directory), ())
```

- [ ] Run `docker exec stock_app python -m unittest tests.test_backtest_result_store -v`; expect missing helper failure.
- [ ] Implement `replace_group_tickers(group_name, tickers, signal_dir)` using
  `_normalize_group_name`, `_normalize_ticker`, `_group_payload`, the existing
  journal, and `_recover_group_move`. Reject an unknown Group; preserve its ID,
  path, and metadata; replace its sorted unique ticker tuple, including `()`.
- [ ] Re-run the focused store suite; expect PASS.

### Task 2: Collect layout and Edit Group popover

**Files:** `app/pages/backtest_lab.py`, `tests/test_backtest_page.py`

- [ ] Write failing AppTest/source tests proving the two Collect rows, named
  Group-only `st.popover("Edit Group")`, draft Add/Remove controls, and one
  Save Group callback with no submit call.
- [ ] Run `docker exec stock_app python -m unittest tests.test_backtest_page -v`; expect failure.
- [ ] Add `replace_group_fn=replace_group_tickers` injection to
  `_render_collect` and `render_backtest_page`. Use session state for draft
  members keyed by selected Group. Normalize additions with `parse_batch_tickers`;
  remove only the clicked member; Save invokes replacement once, clears draft,
  and reruns. Existing Group Tickers stays disabled from resolver output.
- [ ] Re-run focused page suite; expect PASS.

### Task 3: Verify and record

**Files:** verification report, `FOCUS.md`, `ai-context/current-status.md`

- [ ] Run store and page suites plus compilation of `pages/backtest_lab.py` and
  `backtest_engine/result_store.py` in Docker; expect zero failures.
- [ ] Review atomic journaling, empty-Group retention, no-submit edit behavior,
  and unchanged boundaries; record exact evidence.
