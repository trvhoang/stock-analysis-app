# Validate Signals Position-Action Filter Implementation Plan

> **For agentic workers:** Execute test-first in the shared workspace. Do not
> perform Git actions, commits, or commit-tree changes.

**Goal:** Add local Position actions filtering and the requested two-row
Validate Signals control layout.

**Architecture:** Keep cached validation results unchanged. The renderer passes
both local filter selections to its existing result projection, where they
intersect before a ticker heading or expander is rendered.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest/AppTest.

## Global Constraints

- Line 1 is Tickers plus Ticker group; line 2 is Monitoring classifications,
  Position actions, and Validate.
- Position actions options are exactly `ALL`, `can BUY`, `expired BUY`,
  `can SELL`, and `HOLD`; default `ALL`.
- Both local filters use AND semantics; filter changes never replay validation.
- No cached result means no result list.
- No action rule, validation execution, artifact/job/position schema, SQL,
  price scaling, dependency, Docker, credential, or Git change.

### Task 1: Filter cached result actions and render controls

**Files:**

- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**

- Extend `_render_validation_result(ticker, result, classifications,
  position_action)` where `position_action == "ALL"` retains every action.
- Preserve the existing `position_action` fallback of `expired BUY` for an
  older cached result that lacks the field.

- [x] **Step 1: Write failing UI tests**

```python
@staticmethod
def _validate_actions_app():
    return AppTest.from_string(
        "import streamlit as st\\n"
        "from pages.backtest_lab import render_backtest_page\\n"
        "items = [\\n"
        " {'availability': 'available', 'horizon': 'swing', 'rulebook_id': 'buy', 'preferred_variant': 'no-background-theme', 'evaluation_label': 'Exploratory — gross', 'monitoring': {'match_level': 100.0, 'match_classification': 'closely_match'}, 'position_action': 'can BUY', 'audit_eligibility': {}, 'current': {}, 'candidate': {'treatments': {}}},\\n"
        " {'availability': 'available', 'horizon': 'swing', 'rulebook_id': 'sell', 'preferred_variant': 'no-background-theme', 'evaluation_label': 'Exploratory — gross', 'monitoring': {'match_level': 100.0, 'match_classification': 'closely_match'}, 'position_action': 'can SELL', 'audit_eligibility': {}, 'current': {}, 'candidate': {'treatments': {}}},\\n"
        "]\\n"
        "def validate(ticker, *_args):\\n"
        " st.session_state['validate_calls'] = st.session_state.get('validate_calls', 0) + 1\\n"
        " return {'ticker': ticker, 'results': items, 'historical_positions': []}\\n"
        "render_backtest_page(engine=object(), status_dir='unused', signal_dir='unused', positions_dir='unused', validate_fn=validate, position_overview_fn=lambda *_: {'rows': [], 'errors': ()}, rerun_fn=lambda: None)\\n"
    ).run()

def test_validate_position_action_filter_is_local_and_intersects_classification(self):
    app = self._validate_actions_app()
    next(item for item in app.text_input if item.key == "backtest_validate_tickers_v4").set_value("VCB").run()
    next(item for item in app.button if item.label == "Validate").click().run()
    action = next(item for item in app.selectbox if item.label == "Position actions")
    self.assertEqual(action.options, ["ALL", "can BUY", "expired BUY", "can SELL", "HOLD"])
    self.assertEqual(action.value, "ALL")
    action.set_value("can SELL").run()
    self.assertEqual(app.session_state["validate_calls"], 1)
    self.assertEqual(
        [item.label for item in app.expander if item.label != "New Position"],
        ["Swing — sell — no-background-theme"],
    )
```

Add this source-layout assertion:

```python
source = inspect.getsource(backtest_lab._render_validate)
self.assertLess(source.index("tickers_row = st.columns"), source.index("filters = st.columns"))
self.assertLess(source.index('"Monitoring classifications"'), source.index('"Position actions"'))
self.assertLess(source.index('"Position actions"'), source.index('"Validate"'))
```

- [x] **Step 2: Verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: FAIL because Position actions and the two-row layout are absent.

- [x] **Step 3: Add minimal local controls and intersection**

```python
POSITION_ACTION_OPTIONS = ("ALL", "can BUY", "expired BUY", "can SELL", "HOLD")

filters = st.columns((2, 2, 1))
selected_classifications = filters[0].multiselect(...)
selected_action = filters[1].selectbox(
    "Position actions", POSITION_ACTION_OPTIONS, key="backtest_validate_position_action_v4"
)
validate_clicked = filters[2].button("Validate", key="backtest_validate_submit_v4")

visible_items = [
    item for item in result["results"]
    if item.get("availability") == "available"
    and item["monitoring"].get("match_classification") in classifications
    and (position_action == "ALL" or item.get("position_action", "expired BUY") == position_action)
]
```

Render Tickers and Ticker group in the first row. Do not alter session-cache
writes, button handling, batch execution, or result payloads.

- [x] **Step 4: Verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: PASS.

### Task 2: Verify and record

**Files:**

- Create: `docs/superpowers/reports/2026-08-23-validate-signals-position-action-filter-verification.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

- [x] **Step 1: Run final checks**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: zero failures.

Run: `docker exec stock_app python -m py_compile pages/backtest_lab.py`

Expected: exit code 0.

- [x] **Step 2: Review and document**

Confirm `ALL` includes all cached result actions, the selected action and
classification intersect locally, and fresh sessions remain empty. Record test
and compilation evidence plus the unchanged read-only boundary.
