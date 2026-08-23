# View Signals Current-Tab Ticker Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user narrow the currently displayed View Signals result tab by ticker text.

**Architecture:** Reuse the Backtest page's existing ticker-session-state uppercasing callback. The native popover reads one label-hidden input, then applies its normalized partial ticker value to the rows rendered in All, Valid, or Invalid; the persisted catalog remains unchanged.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, unittest Streamlit AppTest.

## Global Constraints

- One input only: no visible label and placeholder exactly `ticker name`.
- Ticker input auto-capitalizes and uses case-insensitive partial matching.
- Filter only the currently displayed tab's rendered rows; do not change tab order, catalog reading, warnings, actions, artifacts, jobs, replay, SQL, BIGINT prices, dependencies, Docker, credentials, or commits.
- No commit: the user manages commits separately.

---

### Task 1: Render and validate ticker filtering

**Files:**
- Modify: `app/pages/backtest_lab.py:2050-2105`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- Consumes: `{"valid": list[dict[str, object]], "invalid": list[dict[str, object]]}`.
- Produces: label-hidden `View Signals ticker filter` text input and filtered tab tables.

- [x] **Step 1: Write the failing AppTest**

```python
filter_widget = next(
    item for item in view_popover.text_input
    if item.label == "View Signals ticker filter"
)
assert filter_widget.proto.placeholder == "ticker name"
filter_widget.set_value("tc").run()
assert filter_widget.value == "TC"
assert all_frame["Ticker"].tolist() == ["TCB"]
```

- [x] **Step 2: Run RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_view_signals_popover_filters_the_active_tab_by_uppercase_ticker -v
```

Expected: FAIL because no View Signals ticker filter exists.

- [x] **Step 3: Add the smallest renderer change**

```python
ticker_filter = st.text_input(
    "View Signals ticker filter",
    placeholder="ticker name",
    label_visibility="collapsed",
    key="view_signals_ticker_filter",
    on_change=_uppercase_ticker_state,
    args=("view_signals_ticker_filter",),
).strip().upper()
filtered_rows = [
    row for row in rows if ticker_filter in str(row.get("Ticker", "")).upper()
]
```

Pass the filtered rows separately to each existing tab renderer. Keep warnings
and tab visibility based on the unfiltered invalid rows, so a valid filter does
not remove the Invalid tab itself.

- [x] **Step 4: Run GREEN and regression checks**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
docker exec stock_app python -m compileall -q pages/backtest_lab.py
git diff --check
```

Expected: the new AppTest and existing Backtest page/catalog tests pass.

- [x] **Step 5: Review and synchronize records**

Review the changed filter for no writes, SQL, price, or job behavior. Update
FOCUS, current status, and a verification report; record no commit.
