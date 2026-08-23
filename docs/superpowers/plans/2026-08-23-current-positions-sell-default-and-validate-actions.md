# Current Positions SELL Default and Validate Actions Implementation Plan

> **For agentic workers:** Execute test-first in the shared workspace. Do not
> perform Git actions, commits, or commit-tree changes.

**Goal:** Show an empty SELL date for new OPEN positions and report actionable
BUY/SELL/HOLD status during Validate Signals.

**Architecture:** `validation_advice` derives a reusable `position_action`
from the current replay and matching OPEN position. `backtest_lab` supplies
progress updates and renders that value, without duplicating decision logic.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest/AppTest.

## Global Constraints

- New OPEN SELL date is `None`, never literal `"None"` or `"-"`.
- Actions are exactly `can BUY`, `expired BUY`, `can SELL`, and `HOLD`.
- A matching OPEN position is `can SELL` at frozen SL/TP or when
  `literal_entry` is false; otherwise it is `HOLD`.
- Validation preserves sequential processing and reports one progress update
  after each attempted ticker, including failures.
- No SQL, price scaling, artifact/job/position schema, risk formula,
  dependency, Docker, credential, or Git change.

---

## File Structure

- `app/backtest_engine/validation_advice.py` derives one validated action.
- `app/pages/backtest_lab.py` renders the empty date, progress bar, summary,
  and collapsed diagnostics.
- `tests/test_backtest_validation_advice.py` verifies domain action precedence.
- `tests/test_backtest_page.py` verifies UI state and batch progress callback.

### Task 1: Derive position actions

**Files:**

- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `app/backtest_engine/validation_advice.py`

**Interfaces:**

- Produces `position_action` in every available `_replay_rulebook` result.
- Consumes `current["literal_entry"]`, `current["latest_close"]`, and the
  matching OPEN position's frozen `risk_snapshot.stop_loss` and
  `risk_snapshot.take_profit`.

- [x] **Step 1: Write failing action tests**

```python
def test_position_action_maps_buy_expiry_sell_and_hold(self):
    self.assertEqual(position_action({"literal_entry": True}, None, True), "can BUY")
    self.assertEqual(position_action({"literal_entry": False}, None, False), "expired BUY")
    self.assertEqual(position_action(
        {"literal_entry": False, "latest_close": 50000},
        {"risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}},
        False,
    ), "can SELL")
    self.assertEqual(position_action(
        {"literal_entry": True, "latest_close": 50000},
        {"risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}},
        False,
    ), "HOLD")

def test_position_action_sells_at_frozen_stop_or_take_profit(self):
    position = {"risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}}
    self.assertEqual(position_action(
        {"literal_entry": True, "latest_close": 48000}, position, False
    ), "can SELL")
    self.assertEqual(position_action(
        {"literal_entry": True, "latest_close": 54000}, position, False
    ), "can SELL")
```

- [x] **Step 2: Verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation_advice -v`

Expected: FAIL because `position_action` is absent.

- [x] **Step 3: Add the minimal pure action helper and result field**

```python
def position_action(current, open_position, buy_eligible) -> str:
    if open_position is None:
        return "can BUY" if buy_eligible else "expired BUY"
    risk = open_position.get("risk_snapshot")
    close = current.get("latest_close")
    if (
        not bool(current.get("literal_entry"))
        or close <= risk["stop_loss"]
        or close >= risk["take_profit"]
    ):
        return "can SELL"
    return "HOLD"
```

Pass the returned label as `position_action` from `_replay_rulebook`.
Validate close/risk values defensively: unavailable or non-numeric values do
not invent a price-triggered SELL; a false literal entry still emits `can SELL`.

- [x] **Step 4: Verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation_advice -v`

Expected: PASS.

### Task 2: Render the new form and validation UI

**Files:**

- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**

- Consumes an available result's `position_action` label.
- Extends `_run_validation_batches(..., progress_fn=None)` where
  `progress_fn(completed: int, total: int, ticker: str)` fires after every
  attempt.

- [x] **Step 1: Write failing page tests**

```python
def test_new_open_position_sell_date_is_empty(self):
    app = self._grouped_positions_app([])
    new_position = next(item for item in app.expander if item.label == "New Position")
    sell_date = next(item for item in new_position.date_input if item.label == "SELL date")
    self.assertIsNone(sell_date.value)

def test_validation_batches_report_success_and_failure_progress(self):
    progress = []
    batch = backtest_lab._run_validation_batches(
        ("VCB", "BAD"), object(), "signals", "positions", validate,
        progress_fn=lambda done, total, ticker: progress.append((done, total, ticker)),
    )
    self.assertEqual(progress, [(1, 2, "VCB"), (2, 2, "BAD")])
    self.assertEqual(batch["errors"], {"BAD": "broken artifact"})
```

```python
def test_validation_result_shows_action_and_collapsed_json(self):
    item = {
        "availability": "available", "horizon": "swing", "rulebook_id": "rule",
        "preferred_variant": "no-background-theme", "evaluation_label": "Exploratory — gross",
        "monitoring": {"match_level": 100.0, "match_classification": "closely_match"},
        "position_action": "can BUY", "audit_eligibility": {}, "current": {},
        "candidate": {"treatments": {}},
    }
    app = AppTest.from_string(
        "import pages.backtest_lab as lab\\n"
        f"item = {item!r}\\n"
        "lab._render_validation_result('VCB', {'results': [item], 'historical_positions': []}, {'closely_match'})\\n"
    ).run()
    self.assertTrue(any(
        entry.value == "Monitoring: 100.0% — closely match | can BUY"
        for entry in app.markdown
    ))
    self.assertIn("expanded=False", inspect.getsource(backtest_lab._render_validation_result))
```

- [x] **Step 2: Verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: FAIL because the date still defaults to today, the callback and
summary action are absent, and JSON remains expanded.

- [x] **Step 3: Add the minimal UI changes**

```python
sell_date = trade_row[4].date_input(
    "SELL date", value=None, key="backtest_position_new_sell_date_v4"
)

progress = st.progress(0, text=f"Validating 0/{len(tickers)} tickers")
batch = _run_validation_batches(
    tickers, engine, signal_dir, positions_dir, validate_fn,
    progress_fn=lambda done, total, ticker: progress.progress(
        done / total, text=f"Validated {done}/{total} tickers: {ticker}"
    ),
)

st.write(
    f"Monitoring: {monitoring['match_level']}% — "
    f"{monitoring['match_classification'].replace('_', ' ')} | "
    f"{item['position_action']}"
)
st.json(diagnostics, expanded=False)
```

Keep the current sequential nested loops, errors, batch cache, classification
filter, expander labels, and diagnostic payload fields unchanged.

- [x] **Step 4: Verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: PASS.

### Task 3: Complete verification and records

**Files:**

- Create: `docs/superpowers/reports/2026-08-23-current-positions-sell-default-and-validate-actions-verification.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

- [x] **Step 1: Run final verification**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_validation_advice -v`

Expected: PASS with zero test failures.

Run: `docker exec stock_app python -m py_compile pages/backtest_lab.py backtest_engine/validation_advice.py`

Expected: exit code 0.

- [x] **Step 2: Review and record**

Verify actions use frozen values only, progress reports errors as completed,
and no SQL/artifact/schema/risk changes occurred. Record the exact evidence in
the verification report and project status files.
