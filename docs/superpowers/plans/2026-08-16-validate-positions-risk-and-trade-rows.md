# Validate Positions and Grouped Trade Rows Implementation Plan

> **Status (2026-08-22):** Phase A is complete and verified. Phase B is
> blocked pending its separate risk contract.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the verified schema-4 Horizon V3 replacement, add a Phase A
fourth Backtest Lab tab and collapsible two-row
BUY/SELL position presentation without changing trade or risk behavior;
reserve Phase B for a separately approved risk model.

**Architecture:** Reuse `position_overview`'s read-only position rows and add
one pure raw trade-row projection. `backtest_lab` renders those rows in one
collapsible group per logical position, preserves selection/delete identity at
the group level, and exposes a group-local edit form that delegates to the
existing immutable-locator update path. Phase A does not read V2 artifacts,
write risk values, or calculate a risk score.

**Resolved tab contract (2026-08-22):** `View Signals` is a read-only native
popover inside both Collect Signals and Validate Signals. It is not a
top-level tab. Backtest Lab therefore has exactly the four tabs specified in
Task 2.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, existing Docker
`unittest` and Streamlit `AppTest` suite.

## Global Constraints

- **Phase A entry gate:** verified schema-4 Horizon V3 replacement and explicit
  user authorization on 2026-08-22. Historical parent Tasks 7--9 and V2
  deletion remain separately governed; Phase A does not read, migrate, or
  delete V2 artifacts.
- Do not modify `app/common_queries.py`, `app/data_preparation.py`, `.env`,
  Docker files, credentials, BIGINT storage, or dependencies.
- Use raw BIGINT values in read models and persistence. Only page rendering
  uses the existing `k VND` conversion helpers.
- Retain filters, sorting, refresh, New Position, selection, Select all
  visible, group-level delete confirmation, editable values, manual close,
  and immutable ticker/saved-signal-set identity for both existing and newly
  created positions.
- Preserve View Signals as a read-only native popover in both Collect Signals
  and Validate Signals; it uses the current schema-4 signal catalog and does
  not become a top-level tab.
- Phase A adds no market-clock, intraday, real-time, order, auto-SELL, risk
  formula, risk persistence write, or V2 fallback. Its Validate Positions tab
  must not display a fake Run button.
- Tests use repository `unittest` only. Every test is a method on an existing
  `unittest.TestCase`; Streamlit assertions use the installed 1.32 `AppTest`
  collections already used in `tests/test_backtest_page.py` such as
  `app.tabs`, `app.expander`, `app.dataframe`, `app.button`, and
  `app.markdown`.
- Do not commit, amend, reset, stash, or otherwise modify Git history; the
  user manages commits.
- Update `FOCUS.md` and `ai-context/current-status.md` only after focused
  tests, compilation, whitespace, and implementation self-review pass.

## File Map

| File | Phase A responsibility |
|---|---|
| `app/backtest_engine/position_overview.py` | Convert one existing overview row into two raw BUY/SELL presentation records without mutating stored history. |
| `app/pages/backtest_lab.py` | Render four tabs, group each position, preserve group selection/delete, render the group-local editor, and show the non-actionable Validate Positions state. |
| `tests/test_backtest_position_overview.py` | Prove the raw BUY/SELL projection, risk display state, and OPEN/CLOSED SELL facts. |
| `tests/test_backtest_page.py` | Replace the obsolete one-grid assertion with grouped-page AppTests and preserve action regressions. |
| `FOCUS.md`, `ai-context/current-status.md` | Record Phase A truthfully after verification. |

---

## Phase A — V3-only UI Structure and Grouped Position Presentation

### Task 1: Add the Read-only BUY/SELL Trade-row Projection

**Files:**

- Modify: `app/backtest_engine/position_overview.py`
- Test: `tests/test_backtest_position_overview.py`

**Interfaces:**

- Add `build_position_trade_rows(row: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]`.
- The first returned record has `trade: "BUY"`; the second has `trade: "SELL"`.
- Both records carry `position_id`, `ticker`, and `status` from the unchanged
  overview row. The projection is read-only and never receives a database
  connection or a positions directory.
- BUY record fields are raw `actual_buy_price`, `buy_date`, `quantity`,
  `signal_set`, `current_price`, `profit_raw`, `profit_pct`,
  `holding_sessions`, `opened_at`, `closed_at`, plus
  `risk_suggestion_text` and `risk_struck`.
- `risk_suggestion_text` is the non-empty string at
  `row["position"]["risk_suggestion_text"]` when present; otherwise it is
  exactly `"N/A"`. `risk_struck` is true only for a CLOSED position whose
  text is not `"N/A"`. Phase A writes neither field.
- SELL record fields are raw `actual_sell_price`, `sell_date`, and a
  `suggestion` mapping with `projected_exit`, `suggested_holding_bars`,
  `stop_loss`, and `take_profit`. Read `suggested_holding_bars`, `stop_loss`,
  and `take_profit` only from an existing mapping `risk_snapshot`; set every
  unavailable value to `None`. `projected_exit` is always `None` in Phase A.

- [x] **Step 1: Add RED projection tests.**

```python
def test_build_position_trade_rows_keeps_open_sell_actual_values_empty(self):
    overview = summarize_positions((_position("FPT", status="open"),), {"FPT": {"close": 51000, "date": "2026-08-10"}})[0]

    buy, sell = build_position_trade_rows(overview)

    self.assertEqual(buy["trade"], "BUY")
    self.assertEqual(buy["risk_suggestion_text"], "N/A")
    self.assertFalse(buy["risk_struck"])
    self.assertEqual(sell["trade"], "SELL")
    self.assertIsNone(sell["actual_sell_price"])
    self.assertIsNone(sell["sell_date"])
    self.assertEqual(sell["suggestion"]["stop_loss"], 48500)
    self.assertEqual(sell["suggestion"]["take_profit"], 52500)

def test_closed_position_strikes_only_a_real_risk_suggestion(self):
    position = _position("VCB", status="closed")
    position["risk_suggestion_text"] = "Swing: 90% - very"
    overview = summarize_positions((position,), {})[0]

    buy, sell = build_position_trade_rows(overview)

    self.assertEqual(buy["risk_suggestion_text"], "Swing: 90% - very")
    self.assertTrue(buy["risk_struck"])
    self.assertEqual(sell["actual_sell_price"], 52000)
    self.assertEqual(sell["sell_date"], "2026-08-10")

def test_no_risk_snapshot_leaves_all_sell_suggestion_fields_unavailable(self):
    overview = summarize_positions((_manual_position("FPT", status="open"),), {"FPT": {"close": 51000, "date": "2026-08-10"}})[0]

    _buy, sell = build_position_trade_rows(overview)

    self.assertEqual(
        sell["suggestion"],
        {"projected_exit": None, "suggested_holding_bars": None,
         "stop_loss": None, "take_profit": None},
    )
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_overview -v`

Expected: import fails because `build_position_trade_rows` does not exist.

- [x] **Step 3: Implement the pure projection.**

```python
def _risk_suggestion_text(position: Mapping[str, object]) -> str:
    value = position.get("risk_suggestion_text")
    return value.strip() if isinstance(value, str) and value.strip() else "N/A"


def build_position_trade_rows(
    row: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    position = row.get("position")
    position = position if isinstance(position, Mapping) else {}
    risk = position.get("risk_snapshot")
    risk = risk if isinstance(risk, Mapping) else {}
    risk_text = _risk_suggestion_text(position)
    is_closed = str(row.get("status", "")).lower() == "closed"
    shared = {"position_id": row.get("id"), "ticker": row.get("ticker"), "status": row.get("status")}
    return (
        {**shared, "trade": "BUY", "actual_buy_price": row.get("actual_buy_price"),
         "buy_date": row.get("buy_date"), "quantity": row.get("quantity"),
         "signal_set": row.get("signal_set"), "current_price": row.get("current_price"),
         "profit_raw": row.get("profit_raw"), "profit_pct": row.get("profit_pct"),
         "holding_sessions": row.get("holding_sessions"), "opened_at": row.get("opened_at"),
         "closed_at": row.get("closed_at"), "risk_suggestion_text": risk_text,
         "risk_struck": is_closed and risk_text != "N/A"},
        {**shared, "trade": "SELL", "actual_sell_price": row.get("actual_sell_price"),
         "sell_date": row.get("sell_date"), "suggestion": {
             "projected_exit": None, "suggested_holding_bars": risk.get("max_hold_bars"),
             "stop_loss": risk.get("stop_loss"), "take_profit": risk.get("take_profit"),
         }},
    )
```

- [x] **Step 4: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_overview -v`

Expected: existing overview/P&L/session tests and the three new projection
tests pass. Confirm no projection function calls a store, writes JSON, or
formats raw prices for UI.

---

### Task 2: Replace the One-grid Position UI with Collapsible Trade Groups

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Test: `tests/test_backtest_page.py`

**Interfaces:**

- Add `_render_position_trade_group(row, *, selected_ids, positions_dir, update_position_fn, manual_update_fn, rerun_fn) -> None`.
  It renders one position-ID-scoped selection control, one `st.expander`, two
  read-only BUY/SELL display rows from `build_position_trade_rows(row)`, and
  one group-local `Edit position` control.
- Add `_render_position_edit_form(row, positions_dir, update_position_fn, manual_update_fn, rerun_fn) -> None`.
  It uses the current State, BUY price/date, Volume, SELL price/date validation
  and converts UI `k VND` prices through the existing helpers. Ticker and
  Saved signal set are shown read-only. Successful save calls the existing
  `_update_by_locator` function, clears the overview and selection session state,
  and reruns. There is no page-wide editable data grid or unsaved multi-row
  state.
- Add `_render_validate_positions_placeholder() -> None`. It renders the
  title `Validate Positions` and an explicit message that the risk model is
  not available yet. It reads no signal artifact, position, or market data and
  exposes no Run/Validate button.
- Add `_position_trade_display_frame(buy, sell) -> pd.DataFrame` and
  `_position_trade_display_styles(frame, *, buy) -> pd.DataFrame`. The first
  produces exactly the two display rows; the second returns an empty CSS frame
  except for `text-decoration: line-through` in the BUY Risk Suggestion cell
  when `buy["risk_struck"]` is true.
- `render_backtest_page` creates tabs in exactly this order: Collect
  Signals, Validate Signals, Current Positions, Validate Positions.
- Retain `_render_view` as popover content. `_render_collect` and
  `_render_validate` each render `st.popover("View Signals")` and call it;
  it remains read-only and does not submit a job or change validation state.
- Import `build_position_trade_rows` from `backtest_engine.position_overview`.
  Add the page-private `_POSITION_EDITING_ID_KEY`; clear it when the overview
  is refreshed, a position is deleted, or a successful group-local edit
  reruns the page so an old ID cannot reopen a stale form.
- Existing `_POSITION_SELECTED_IDS_KEY`, `_visible_position_ids`,
  `_pruned_selection`, batch-delete preparation, and stale-delete
  confirmation remain the single selection/delete contract. Add
  `_position_selection_widget_key(position_id)`,
  `_sync_visible_position_selection(visible_ids)`,
  `_apply_position_selection(position_id)`, and extend
  `_apply_select_all_visible(visible_ids)` so every visible group checkbox
  and the selected-ID set change together in its callback. This preserves
  Select all visible across reruns without relying on a hidden editable grid.

- [x] **Step 1: Replace obsolete grid fixtures and add RED tests for the
four-tab and group contract.**

Replace `BacktestPageTests._current_positions_frame` with this test-only
helper. It uses the same literal row injection pattern already used by this
test file; it does not invent a callback bridge from `AppTest` to a `Mock`.

```python
def _grouped_positions_app(self, rows):
    return AppTest.from_string(
        "from pages.backtest_lab import render_backtest_page\n"
        f"rows = {rows!r}\n"
        "render_backtest_page(\n"
        "    engine=object(),\n"
        "    status_dir='unused-status-dir',\n"
        "    position_overview_fn=lambda engine, positions_dir: {'rows': rows, 'errors': ()},\n"
        "    rerun_fn=lambda: None,\n"
        ")\n"
    ).run()

def _position_select_widgets(self, app):
    return [item for item in app.checkbox if item.label == "Select"]
```

Use complete literal position rows in each AppTest, including the existing
`position_locator` and `position` mappings. This keeps existing
manual/legacy identity paths testable even though the display projection
gracefully handles rows from earlier fixtures that lack optional details.

```python
def test_backtest_page_renders_four_tabs_and_a_non_actionable_validate_positions_tab(self):
    app = AppTest.from_string(
        "from pages.backtest_lab import render_backtest_page\n"
        "render_backtest_page(engine=object(), status_dir='unused', rerun_fn=lambda: None)\n"
    ).run()

    self.assertEqual(
        [tab.label for tab in app.tabs[:4]],
        ["Collect Signals", "Validate Signals", "Current Positions", "Validate Positions"],
    )
    self.assertTrue(any(item.value == "Validate Positions" for item in app.title))
    self.assertFalse(any("risk" in button.label.lower() for button in app.button))
    self.assertEqual([item.label for item in app.popover if item.label == "View Signals"], ["View Signals", "View Signals"])

def test_current_positions_renders_one_expander_with_buy_and_sell_rows(self):
    rows = [{
        "id": "manual-1", "ticker": "FPT", "status": "open",
        "actual_buy_price": 50000, "actual_sell_price": None,
        "quantity": None, "current_price": 51000, "profit_raw": 1000,
        "profit_pct": 2.0, "opened_at": "2026-08-01T09:00:00+07:00",
        "closed_at": None, "buy_date": "2026-08-01", "sell_date": None,
        "holding_sessions": 4, "signal_set": "-",
        "position_locator": {"record_source": "manual", "ticker": "FPT", "id": "manual-1"},
        "position": {"risk_snapshot": None},
    }]
    app = self._grouped_positions_app(rows)

    group = next(item for item in app.expander if "FPT" in item.label)
    trade_frame = group.dataframe[0].value
    self.assertEqual(trade_frame["Trade"].tolist(), ["BUY", "SELL"])
    self.assertEqual(trade_frame.loc[0, "Risk Suggestion"], "N/A")
    self.assertEqual(trade_frame.loc[1, "Actual SELL"], "-")
    self.assertTrue(any(button.label == "Edit position" for button in group.button))

def test_closed_group_marks_non_na_risk_as_historical(self):
    row = {
        "id": "legacy-1", "ticker": "VCB", "status": "closed",
        "actual_buy_price": 50000, "actual_sell_price": 52000,
        "quantity": None, "current_price": None, "profit_raw": 2000,
        "profit_pct": 4.0, "opened_at": "2026-08-01T09:00:00+07:00",
        "closed_at": "2026-08-10T09:00:00+07:00", "buy_date": "2026-08-01",
        "sell_date": "2026-08-10", "holding_sessions": 5,
        "signal_set": "win_rate: strategy-a",
        "position_locator": {"record_source": "legacy", "ticker": "VCB", "id": "legacy-1", "theme_variant": "no-background-theme", "metric": "win_rate"},
        "position": {"risk_suggestion_text": "Swing: 90% - very"},
    }
    app = self._grouped_positions_app([row])
    next(item for item in app.multiselect if item.label == "Position state").set_value(
        ["OPEN", "CLOSED"]
    ).run()

    group = next(item for item in app.expander if "VCB" in item.label)
    trade_frame = group.dataframe[0].value
    self.assertEqual(trade_frame.loc[0, "Risk Suggestion"], "Swing: 90% - very")
    self.assertTrue(backtest_lab.build_position_trade_rows(row)[0]["risk_struck"])
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: the previous three-tab page and one global `current_positions_editor`
are rendered; no grouped trade renderer or placeholder tab exists.

- [x] **Step 3: Render the read-only two-row group and group-local editor.**

Implement the renderer with this exact control flow:

1. `_render_validate_positions_placeholder()` calls `st.title("Validate
   Positions")` and `st.info("Risk model is not available yet.")` only.
2. `_position_trade_display_frame(buy, sell)` produces two rows with the
   columns `Trade`, `Price`, `Date`, `Volume`, `Saved signal set`, `Current
   price`, `Profit %`, `Profit`, `Hold time`, `Risk Suggestion`, `SELL
   suggestion`, and `Actual SELL`. The BUY row uses the current existing date
   and raw-price formatting helpers. Its SELL-only columns are `"-"`. The
   SELL row has `"-"` in BUY-only fields; its `SELL suggestion` is `"-"` when
   every projected-exit/max-hold/SL/TP value is `None`, otherwise it lists
   `Projected exit: <date> | Holding: <native bars> | SL/TP: <price> / <price>`.
   Its `Actual SELL` is `<price> / <date>` only when both values exist,
   otherwise `"-"`.
3. `_position_trade_display_styles(frame, buy=buy)` returns a same-shaped CSS
   dataframe. It sets `text-decoration: line-through` only at the BUY row's
   `Risk Suggestion` cell when `risk_struck` is true; all other cells are
   empty CSS strings. Pass it to `st.dataframe` through
   `frame.style.apply(_position_trade_display_styles, buy=buy, axis=None)`.
4. `_render_position_trade_group` gets its `position_id` through
   `_overview_position_id`, renders `st.checkbox("Select", key=` the
   position-specific selection key, `on_change=_apply_position_selection`,
   `args=(position_id,))`, then renders an expander named
   `<ticker> — <UPPERCASE status>`. Within the expander, build/render the two
   rows and render the ID-specific `Edit position` button. The button stores
   the ID in `_POSITION_EDITING_ID_KEY`; only the matching group renders
   `_render_position_edit_form`. Give every widget/form a position-ID-specific
   key so two expanded groups cannot collide.
5. `_render_position_edit_form` uses `st.form` and `st.form_submit_button`.
   On submit, build the `_editor_row_to_updates` mapping, call
   `_update_by_locator`, clear `_POSITION_OVERVIEW_KEY`, delete confirmation,
   selection, and the editing ID, set existing position feedback to
   `"Position updated."`, and call `rerun_fn`. On `KeyError`, `OSError`,
   `TypeError`, or `ValueError`, call `st.error` and retain the form data.

Replace the current `st.data_editor` call, its grid-diff helpers
`_position_editor_rows`, `_changed_editor_position_ids`, and
`_selected_editor_row`, and their obsolete tests. Retain
`_editor_row_to_updates` as the one raw/UI conversion contract. Leave
filter/sort, refresh, New Position, visible-ID calculation, Select all
visible, delete preparation, and `_render_delete_confirmation` intact.

Before rendering any group checkbox, call
`_sync_visible_position_selection(visible_ids)`. It prunes the selected-ID
set and initializes each current visible checkbox session-state key from that
set. If `_POSITION_EDITING_ID_KEY` is not in `visible_ids`, it removes that
key before rendering groups. Each group checkbox calls
`_apply_position_selection(position_id)`, which
updates `_POSITION_SELECTED_IDS_KEY` only; the select-all callback sets both
the selected-ID set and every current visible group checkbox key. Derive
`selected_ordered_ids` from that set in `visible_ids` order before rendering
the delete control and confirmation. This retains the existing stale-delete
guard without a page-wide editor.

The group edit form uses a `st.form` scoped to the position ID and offers only
State (`OPEN`/`CLOSED`), BUY price (`k`, required), BUY date (required),
Volume (optional, min 100/step 100), SELL price (optional), and SELL date
(optional). It displays ticker and saved signal set as read-only text. Build
the existing column-name mapping for `_editor_row_to_updates`, then call
`_update_by_locator` once. The existing stores remain authoritative: they
clear SELL data when a CLOSED position is changed back to OPEN, reject a
CLOSED position without both SELL fields, preserve immutable ticker/saved-set
identity, and recalculate frozen SL/TP if the stored position contract already
requires it. Do not duplicate those persistence rules in the page.

- [x] **Step 4: Add preservation regression tests.**

```python
def test_group_local_editor_exposes_only_existing_editable_fields(self):
    app = self._grouped_positions_app([{
        "id": "manual-1", "ticker": "FPT", "status": "open",
        "actual_buy_price": 50000, "actual_sell_price": None,
        "quantity": None, "current_price": 51000, "profit_raw": 1000,
        "profit_pct": 2.0, "opened_at": "2026-08-01T09:00:00+07:00",
        "closed_at": None, "buy_date": "2026-08-01", "sell_date": None,
        "holding_sessions": 4, "signal_set": "-",
        "position_locator": {"record_source": "manual", "ticker": "FPT", "id": "manual-1"},
        "position": {"risk_snapshot": None},
    }])
    group = next(item for item in app.expander if "FPT" in item.label)
    next(button for button in group.button if button.label == "Edit position").click().run()
    self.assertTrue(any(item.label == "State" for item in app.selectbox))
    self.assertTrue(any(item.label == "BUY price (k)" for item in app.number_input))
    self.assertFalse(any(item.label == "Ticker" for item in app.text_input))
    self.assertFalse(any(item.label == "Saved signal set" for item in app.selectbox))

def test_editor_row_to_updates_retains_the_existing_raw_write_contract(self):
    updates = backtest_lab._editor_row_to_updates({
        "State": "CLOSED", "BUY price": 51.0, "BUY date": date(2026, 8, 1),
        "Volume": 100, "SELL price": 52.0, "SELL date": date(2026, 8, 10),
    })
    self.assertEqual(updates["actual_buy_price"], 51000)
    self.assertEqual(updates["actual_sell_price"], 52000)
    self.assertEqual(updates["quantity"], 100)

def test_group_local_editor_updates_the_existing_manual_history(self):
    with tempfile.TemporaryDirectory() as directory:
        position = create_manual_position("FPT", 50000, "2026-08-01", positions_dir=directory)
        rows = [{
            "id": position["id"], "ticker": "FPT", "status": "open",
            "actual_buy_price": 50000, "actual_sell_price": None,
            "quantity": None, "current_price": 51000, "profit_raw": 1000,
            "profit_pct": 2.0, "opened_at": position["opened_at"],
            "closed_at": None, "buy_date": "2026-08-01", "sell_date": None,
            "holding_sessions": 4, "signal_set": "-",
            "position_locator": {"record_source": "manual", "ticker": "FPT", "id": position["id"]},
            "position": position,
        }]
        app = AppTest.from_string(
            "from pages.backtest_lab import render_backtest_page\n"
            f"rows = {rows!r}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status-dir',\n"
            f"    positions_dir={directory!r},\n"
            "    position_overview_fn=lambda engine, positions_dir: {'rows': rows, 'errors': ()},\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()
        next(button for button in app.button if button.label == "Edit position").click().run()
        next(item for item in app.number_input if item.label == "BUY price (k)").set_value(51.0).run()
        next(button for button in app.button if button.label == "Save position changes").click().run()

        saved = load_manual_position_history("FPT", directory)["history"][0]
    self.assertEqual(saved["actual_buy_price"], 51000)

def test_group_selection_keeps_existing_select_all_and_delete_enablement(self):
    first_row = {
        "id": "manual-1", "ticker": "FPT", "status": "open",
        "actual_buy_price": 50000, "actual_sell_price": None,
        "quantity": None, "current_price": 51000, "profit_raw": 1000,
        "profit_pct": 2.0, "opened_at": "2026-08-01T09:00:00+07:00",
        "closed_at": None, "buy_date": "2026-08-01", "sell_date": None,
        "holding_sessions": 4, "signal_set": "-",
        "position_locator": {"record_source": "manual", "ticker": "FPT", "id": "manual-1"},
        "position": {"risk_snapshot": None},
    }
    second_row = {
        **first_row, "id": "legacy-2", "ticker": "VCB",
        "position_locator": {"record_source": "legacy", "ticker": "VCB", "id": "legacy-2", "theme_variant": "no-background-theme", "metric": "win_rate"},
    }
    app = self._grouped_positions_app([first_row, second_row])

    next(widget for widget in app.checkbox if widget.label == "Select all visible").set_value(True).run()

    self.assertEqual([widget.value for widget in self._position_select_widgets(app)], [True, True])
    self.assertFalse(next(button for button in app.button if button.label == "Delete position").disabled)
```

Extend the existing `manual_position_store` test import with
`create_manual_position` for the real-history edit regression above; retain
its existing `load_manual_position_history` import.

Test the reverse transition too: set Select all visible to false, assert both
group checkboxes are false, and assert Delete position is disabled. Existing
position-store tests, not AppTest callback injection, remain the evidence that
the form's one `_update_by_locator` call persists through the correct legacy
or manual store.

Update the remaining current-position tests in the same edit: (1) replace
`test_current_positions_renders_one_inline_editor` with the first grouped-row
test above; (2) change the default OPEN/closed-filter test to compare visible
expander labels and their two-row frames; (3) retain
`_filter_and_sort_positions` assertions but remove the retired
`_position_editor_rows` assertion; (4) remove direct checks of retired
grid-diff helpers; and (5) change the existing Select all visible regression
to inspect the two group checkboxes rather than a `Select` dataframe column.

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_position_overview -v`

Expected: group rendering, existing create/edit/delete actions, Select all
visible, stale-delete guard, and existing Validate Signals controls pass. The
former global editor assertion is removed because its behavior is deliberately
replaced by group-local editing, not silently lost.

---

### Task 3: Phase A Verification and Documentation

**Files:**

- Modify: `FOCUS.md`, `ai-context/current-status.md`
- Test: `tests/test_backtest_position_overview.py`, `tests/test_backtest_page.py`,
  existing position-store tests.

**Interfaces:**

- The Phase A page displays no risk calculation, no common as-of result, and
  no new position persistence field. Every visible BUY risk cell is `N/A`
  unless a future Phase B record already supplies a non-empty display string.
- Existing V3-only cutover behavior remains intact: Phase A never opens a V2
  result artifact or exposes a V2 saved-set option.

- [x] **Step 1: Run the focused Backtest and position regression gate.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_overview tests.test_backtest_position_store tests.test_backtest_manual_position_store tests.test_backtest_position_monitor tests.test_backtest_page -v`

Expected: all focused tests pass. Investigate every failure before changing a
test or weakening an existing position contract.

- [x] **Step 2: Run static and V3-only checks.**

Run:

```text
docker exec stock_app python -m compileall backtest_engine pages/backtest_lab.py
git diff --check
rg -n "load_rulebook_result|list_current_signal_set_rows|V2|schema_version" backtest_engine/position_overview.py pages/backtest_lab.py
```

Expected: compilation and whitespace pass. Review the final search results to
prove Phase A did not add a V2 artifact reader or a risk-write path.

- [x] **Step 3: Self-critique before updating docs.**

Confirm all of the following from code and tests: the new tab is
non-actionable; only logical position IDs are selected/deleted; both OPEN and
CLOSED groups have exactly BUY and SELL display rows; CLOSED non-`N/A` risk
text carries the tested `risk_struck` flag and is rendered with the dataframe
style; no auto-SELL or real-time path exists; raw values are converted only in
UI rendering; ticker and saved signal set stay immutable.

- [x] **Step 4: Record evidence-based completion.**

Update `FOCUS.md` and `ai-context/current-status.md` with the actual focused
test totals, changed presentation behavior, Phase B's then-blocked status,
and any observed limitation. Do not mark Phase B complete and do not claim a
risk calculation exists.

---

## Phase B — Risk Formula Approval Gate

This is the historical Phase B approval gate for the Phase A plan. The
dedicated Phase B design is now approved at
`docs/superpowers/specs/2026-08-22-validate-positions-risk-phase-b-design.md`.
Do not implement from this document; its detailed implementation plan remains
to be written and approved.

### Task 4: Produce the Required Phase B Contract Before Planning Code

**Files:** None. After all required inputs are approved, create a separate
dated Phase B design and implementation plan; do not predeclare or create
placeholder files.

**Required approval content:**

1. One deterministic `0–100` risk formula and exact inclusive/exclusive
   thresholds for `low`, `medium`, `high`, and `very`.
2. Separate exact inputs for V3 saved-set evaluation and no-signal Swing plus
   Mid-term evaluation, including every missing/invalid-input outcome.
3. The full per-position batch-result columns and exact text for unavailable,
   failure, and successful outcomes; the common run-level as-of date remains
   informational and is never stored per position.
4. The precise persisted risk schema on the BUY record, overwrite semantics,
   CLOSED display semantics, and behavior after BUY-price/state edits.
5. Batch cache key, five-position hard cap, sequential progress, and
   continue-on-error evidence.
6. The relationship, if any, between risk level and manual SELL suggestion.
   It must state explicitly whether risk can add a new SELL reason; absent a
   new approved rule, current ATR/hold-based manual SELL rules remain the only
   SELL advice.

- [x] **Step 1: Obtain the six written approvals above (2026-08-22).**

Expected: each item has one unambiguous rule; no formula or band is inferred
from the example `Swing: 90% - very`.

- [x] **Step 2: Write and self-review the dedicated Phase B design (2026-08-22).**

The design must preserve the V3-only boundary, raw-BIGINT calculations,
latest-completed-bar-only inputs, no real-time behavior, no risk history, and
per-position error isolation. It must resolve all six approval items before a
plan is written.

- [ ] **Step 3: User approved the Phase B design (2026-08-22); implementation
plan review is pending.** See
`docs/superpowers/plans/2026-08-22-validate-positions-risk-phase-b.md`.

Expected: the new plan contains RED/GREEN `unittest` coverage for the formula,
storage overwrite, cache reuse, five-position cap, V3/no-signal routing,
V2 non-reading, batch continuation, result rendering, and CLOSED strike-through
behavior. Do not implement Phase B from this document.
