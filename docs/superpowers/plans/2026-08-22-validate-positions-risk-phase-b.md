# Validate Positions Risk — Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for inline
> task-by-task execution. Steps use checkbox syntax for tracking. The user has
> explicitly prohibited every Git action; do not commit, inspect, or alter Git.

**Goal:** Provide after-session, manual risk assessment for selected eligible
OPEN positions without changing trading, SELL, legacy-history, or V3 artifact
contracts.

**Architecture:** Add a pure `position_risk` service that selects manual
schema-4/no-signal records only, determines one shared latest DB bar, rebuilds
current V3 rulebook facts from raw frames, and returns persisted-result rows.
Keep `position_monitor` as the unchanged SELL monitor. Add a narrowly-scoped
manual-history writer for `risk_suggestion_text`, then render the service in
the existing fourth Backtest Lab tab.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy Core/text, PostgreSQL,
Streamlit 1.32, unittest/AppTest, Docker.

**Status:** Complete and verified on 2026-08-25. Evidence:
`../reports/2026-08-25-validate-positions-phase-b-verification.md`.

## Global Constraints

- Use only persisted completed DB bars; never current date, realtime, or
  intraday data.
- Raw DB prices remain BIGINT; divide by 1000 only at the existing UI boundary.
- SQL uses `sqlalchemy.text()`, `%(param)s` parameters, and
  `engine.raw_connection()`.
- Use `Asia/Ho_Chi_Minh` for datetime work.
- Never modify `common_queries.py`, BIGINT scaling, Docker, credentials, or
  V3 rulebook inputs/entry/SELL semantics.
- Validate Positions reads no legacy artifact or legacy position history.
- No new dependency, no Git action, and no commit.
- Exact user-facing results: `Updated`,
  `Unavailable — risk score missing/invalid.`, `Failed — assess failed.`, and
  `T+3 required`.

---

### Task 1: Pure risk formula and frozen-reference routing

**Files:**

- Create: `app/backtest_engine/position_risk.py`
- Create: `tests/test_backtest_position_risk.py`
- Modify: `app/backtest_engine/indicators.py`
- Test: `tests/test_backtest_position_risk.py`

**Interfaces:**

- Consumes `rulebook_for`, `ENTRY_GATE_NAMES`, `RulebookExecution`,
  `build_rulebook_frame`, `rulebook_entry_signal`,
  `monitoring_match_level`, and unchanged `monitor_position`.
- Produces:

```python
def risk_label(score: float) -> str: ...
def render_risk_suggestion(scores: dict[str, float]) -> str: ...
def assess_signal_backed_position(
    position: dict[str, object],
    raw_history: pd.DataFrame,
    as_of_date: date,
    vnindex_history: pd.DataFrame | None,
) -> dict[str, object]: ...
def assess_no_signal_position(
    raw_history: pd.DataFrame, as_of_date: date
) -> dict[str, object]: ...
def theme_eligibility_for_dates(
    ticker_dates: pd.Series, vnindex_history: pd.DataFrame, rulebook: RulebookSpec,
    as_of_date: date,
) -> pd.Series: ...
```

- Each assessment returns only `{"availability": "available", "scores":
  {"swing": 40.0}}` or `{"availability": "unavailable"}`. It never
  writes storage and never reads an artifact.

- [x] **Step 1: Write formula RED tests.**

```python
def test_signal_score_at_or_below_stop_is_very_one_hundred():
    result = assess_signal_backed_position(_v4_position(), _history(close=80), DATE, None)
    self.assertEqual(result["scores"]["swing"], 100.0)
    self.assertEqual(risk_label(100.0), "very")

def test_signal_score_uses_t_plus_three_and_matching_daily_units():
    result = assess_signal_backed_position(_v4_position(signal_date="2026-01-05"), _history(), DATE_T3, None)
    self.assertEqual(result["scores"]["swing"], 23.64)

def test_manual_score_counts_all_four_no_theme_gates_and_returns_both_horizons():
    result = assess_no_signal_position(_history_with_gate_count(swing=3, midterm=1), DATE)
    self.assertEqual(result["scores"], {"swing": 25.0, "midterm": 75.0})
    self.assertEqual(render_risk_suggestion(result["scores"]), "Swing: 25.00% - low\nMid-term: 75.00% - high")
```

Include exact band-boundary tests for `40`, `40.01`, `60`, `60.01`, `80`, and
`80.01`; stop-proximity clamp above BUY/below stop; ATR and holding clamps;
saved-match versus current-match drop; T+3 = third session strictly after the
saved signal date; and Mid-term elapsed denominator `80`.

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_risk -v`

Expected: import failure because `position_risk` does not exist.

- [x] **Step 3: Add the pure theme helper and formula implementation.**

Move the data-frame-only VNINDEX alignment from private
`early_warning._theme_facts` into `indicators.theme_eligibility_for_dates`.
The helper must build the registered VNINDEX frame with `today=as_of_date`,
merge backward by ticker dates, and return only the boolean eligibility
series. Keep `early_warning` as a caller of the helper; it retains DB loading
and its public result shape.

Implement risk calculations exactly as follows:

```python
def _clamp_score(value: float) -> float:
    return min(100.0, max(0.0, value))

def risk_label(score: float) -> str:
    rounded = round(_clamp_score(score), 2)
    if rounded <= 40:
        return "low"
    if rounded <= 60:
        return "medium"
    if rounded <= 80:
        return "high"
    return "very"

def _signal_score(entry: float, stop: float, close: float, atr: float,
                  holding: int, maximum: int, drop: float, elapsed: float) -> float:
    if close <= stop:
        return 100.0
    distance = entry - stop
    base = (0.55 * _clamp_score(100 * (entry - close) / distance)
            + 0.25 * _clamp_score(100 * atr / distance)
            + 0.20 * _clamp_score(100 * holding / maximum))
    return round(_clamp_score(base + 0.30 * max(_clamp_score(drop), _clamp_score(elapsed))), 2)
```

Reject unavailable required values rather than coercing them: raw close, raw
ATR, frozen stop/max hold, positive entry-to-stop distance, entry match level,
entry-context `as_of_date`, frozen gate list, current gate facts, and themed
VNINDEX facts. Use `monitor_position` only to obtain native holding bars from
the frozen one-horizon position; do not modify its SELL output.

For a saved schema-4 reference, construct `RulebookExecution` from frozen
`selected_gates`, `preferred_variant`, and `AND` only when themed. Current
match level comes from `monitoring_match_level`. For a no-signal position,
build both registered no-theme frames and count boolean values for every name
in `ENTRY_GATE_NAMES`; never use a saved artifact or reference.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_risk tests.test_backtest_early_warning tests.test_backtest_position_monitor -v`

Expected: formula, theme alignment, existing replay, and SELL-monitor tests pass.

- [x] **Step 5: Self-review task boundary.**

Confirm `position_risk.py` contains no storage writer, Streamlit import,
artifact loader, legacy position store import, current-date call, or SELL
reason. Confirm `position_monitor.py` is unchanged.

### Task 2: Batch inputs, shared-bar gate, candidates, and cache

**Files:**

- Modify: `app/backtest_engine/position_risk.py`
- Modify: `tests/test_backtest_position_risk.py`
- Test: `tests/test_backtest_position_risk.py`

**Interfaces:**

```python
def list_validate_position_candidates(
    positions_dir: str = "backtest-positions",
) -> tuple[dict[str, object], ...]: ...

def validate_open_positions(
    position_ids: tuple[str, ...], engine, positions_dir: str = "backtest-positions",
    persist_risk_suggestion_fn: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]: ...
```

`validate_open_positions` returns:

```python
{
    "as_of_date": "YYYY-MM-DD" | None,
    "results": [
        {"ticker": "FPT", "position_id": "...", "evaluation": "Swing",
         "risk_suggestion": "Swing: 42.00% - medium", "result": "Updated"}
    ],
}
```

- [x] **Step 1: Write batch RED tests.**

```python
def test_candidates_include_only_open_manual_v4_and_pnl_only_records():
    self.assertEqual([row["id"] for row in list_validate_position_candidates(DIR)], ["v4-open", "pnl-open"])

def test_batch_reuses_one_cached_frame_for_two_same_ticker_horizon_rows():
    result = validate_open_positions(("one", "two"), ENGINE, DIR, persist)
    self.assertEqual(load_history.call_count, 1)
    self.assertEqual([row["result"] for row in result["results"]], ["Updated", "Updated"])

def test_mismatched_latest_completed_bars_are_failed_without_an_as_of_header():
    result = validate_open_positions(("fpt", "vcb"), ENGINE, DIR, persist)
    self.assertIsNone(result["as_of_date"])
    self.assertEqual({row["result"] for row in result["results"]}, {"Failed — assess failed."})
```

Also cover: no legacy `position_store.load_position_history` call; selected
ID missing/not eligible; six IDs rejected before any DB/read/write; themed
VNINDEX participates in latest-date equality and is cached; sequential result
order; an unexpected second-row exception does not stop a third row; and
missing input yields `Unavailable — risk score missing/invalid.`.

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_risk -v`

Expected: batch interface and candidate filtering are absent.

- [x] **Step 3: Implement batch orchestration.**

Scan only `<positions_dir>/<TICKER>/<TICKER>_manual_positions.json` through
`load_manual_position_history`; do not call `load_all_positions` because it
opens legacy histories. Candidate requirements are `status == "open"` and
either no `signal_reference` or schema-4 `signal_reference`.

Use one parameterized `sqlalchemy.text()` query for `MAX(date)` per required
ticker. Required series are all candidate tickers plus `VNINDEX` only for a
selected themed schema-4 reference. If the returned dates are not exactly one
value, create one failed result per selected position, perform no frame load or
write, and return `as_of_date=None`. This is the strict implementation of the
shared-bar rule.

For a shared date, load raw history once per `(ticker, horizon,
shared_as_of_date)` cache key with `load_ticker_history`; use a 15-year bounded
start date and shared date end. Pass the shared date into
`build_rulebook_frame(today=...)` so Mid-term retains existing completed
W-FRI semantics. Reuse the same cached VNINDEX history/frame for every themed
assessment. Catch expected validation/data errors as Unavailable and all other
per-row exceptions as Failed; always continue to the next position.

For saved schema-4 positions, calculate completed ticker sessions strictly
after `entry_context["as_of_date"]` through the shared as-of date. Return
`T+3 required` with no persistence call before the third session. For every
other successful result call the injected persistence function once.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_risk -v`

Expected: all formula, routing, cache, shared-date, and continuation cases pass.

- [x] **Step 5: Self-review database and legacy boundaries.**

Inspect the new SQL: `text()` plus `%(tickers)s`, raw connection closed in
`finally`, uppercase inputs only. Confirm no V2 filename, artifact loader,
`load_all_positions`, or legacy-store reader is reachable from this module.

### Task 3: Manual risk-text persistence and Current Positions invalidation

**Files:**

- Modify: `app/backtest_engine/manual_position_store.py`
- Modify: `app/backtest_engine/position_overview.py`
- Modify: `tests/test_backtest_manual_position_store.py`
- Modify: `tests/test_backtest_position_overview.py`

**Interfaces:**

```python
def update_manual_position_risk_suggestion(
    ticker: str, position_id: str, risk_suggestion_text: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]: ...
```

The writer accepts only a non-empty text, finds one manual record atomically,
requires it to remain OPEN, writes only `risk_suggestion_text`, validates the
history, and returns a deep copy. It is the only Phase B persistence writer.

- [x] **Step 1: Write persistence RED tests.**

```python
def test_risk_writer_overwrites_only_open_manual_position_text():
    updated = update_manual_position_risk_suggestion("FPT", opened["id"], "Swing: 42.00% - medium", directory)
    self.assertEqual(updated["risk_suggestion_text"], "Swing: 42.00% - medium")

def test_buy_price_date_and_reopen_clear_risk_text_but_quantity_and_close_preserve_it():
    self.assertNotIn("risk_suggestion_text", update_manual_position("FPT", opened["id"], {"actual_buy_price": 51000}, directory))
    self.assertEqual(closed["risk_suggestion_text"], "Unavailable")

def test_legacy_buy_row_never_displays_a_legacy_risk_text():
    buy, _ = build_position_trade_rows(_legacy_row(risk_suggestion_text="Swing: 99.00% - very"))
    self.assertEqual(buy["risk_suggestion_text"], "N/A")
```

Cover invalid/blank writer text, missing ID, CLOSED writer rejection, BUY-date
clear, CLOSED-to-OPEN clear, and position-validator rejection of a non-string
risk field. Retain the existing V4 frozen risk-snapshot recalculation test.

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_manual_position_store tests.test_backtest_position_overview -v`

Expected: missing writer and stale risk text failures.

- [x] **Step 3: Implement narrow persistence changes.**

Validate optional `risk_suggestion_text` as a stripped non-empty string when
present. New records omit it. In `update_manual_position`, remove the key when
`actual_buy_price` or `buy_date` changes, or when a CLOSED record reopens;
leave it intact for quantity edits and OPEN-to-CLOSED transition. Do not touch
legacy `position_store.py`.

Change `_risk_suggestion_text` to accept `record_source` from
`build_position_trade_rows`. Return `N/A` for every nonmanual record or
non-schema-4 saved reference before inspecting text. This retains legacy P&L
rows while removing legacy risk-display dependency.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_manual_position_store tests.test_backtest_position_overview -v`

Expected: persistence, invalidation, strike-through projection, and legacy-N/A tests pass.

- [x] **Step 5: Self-review storage safety.**

Confirm only manual JSON files can receive `risk_suggestion_text`; a T+3
result never calls the writer; Unavailable does. Confirm closing preserves
stored text and reopening removes it.

### Task 4: Validate Positions UI and result rendering

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`
- Test: `tests/test_backtest_page.py`

**Interfaces:**

```python
def _render_validate_positions(
    engine, positions_dir: str, *,
    candidates_fn: Callable = list_validate_position_candidates,
    validate_positions_fn: Callable = validate_open_positions,
) -> None: ...
```

Extend `render_backtest_page` with injected defaults for these two callables;
keep existing call sites valid. The page passes only selected candidate IDs to
the batch service.

- [x] **Step 1: Write UI RED tests.**

```python
def test_validate_positions_lists_only_two_eligible_open_positions_and_runs_selected_ids():
    app = self._validate_positions_app(CANDIDATES, RESULT)
    self.assertEqual([box.label for box in app.checkbox if box.label.startswith("Validate ")], ["Validate FPT — v4-open", "Validate VCB — pnl-open"])
    app.checkbox[0].set_value(True).run()
    next(button for button in app.button if button.label == "Run validation").click().run()
    self.assertEqual(called_ids, ("v4-open",))

def test_validate_positions_renders_exact_result_copy_and_common_as_of_only():
    app = self._validate_positions_app(CANDIDATES, RESULT)
    self.assertTrue(any("As of: 22/08/2026" in item.value for item in app.caption))
    self.assertTrue(any("T+3 required" in str(item.value) for item in app.dataframe))
```

Cover: Run disabled with zero or six selections; only OPEN candidates render;
legacy candidate is absent; T+3 shows no prior-risk mutation; Unavailable and
Failed exact copy; no header when service returns `None`; and overview session
cache is cleared after at least one Updated/Unavailable write.

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: placeholder-only tab fails control/result assertions.

- [x] **Step 3: Replace the placeholder with the injected UI.**

Use checkbox labels `Validate <TICKER> — <POSITION_ID>` and preserve candidate
order. Render an explicit error `Select one to five OPEN positions.` for an
invalid count; keep Run disabled until count is one through five. On click,
call the service once, render a prominent `As of: DD/MM/YYYY` only when
supplied, and render exactly the four approved result-table columns in service
order: Ticker, Evaluation, Risk, Result. Use
the service's `risk_suggestion` value without price rescaling because it is
already text. After an Updated or Unavailable row, remove
`_POSITION_OVERVIEW_KEY` from session state so Current Positions reloads its
persisted BUY risk text.

Do not add a fifth tab, popover, worker, auto refresh, auto SELL, legacy
selection, realtime source, or position edit action to this tab.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: existing Collect/Validate/Current Position regressions and new
Validate Positions AppTests pass.

- [x] **Step 5: Self-review page behavior.**

Confirm the existing View Signals popovers remain native and unchanged; the
new tab has one manual Run action only; no legacy locator is passed to the
risk service; and no output changes a SELL suggestion.

### Task 5: Full verification, documentation, and final review

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`
- Create: `docs/superpowers/reports/2026-08-22-validate-positions-phase-b-verification.md`
- Test: `tests/test_backtest_position_risk.py`,
  `tests/test_backtest_manual_position_store.py`,
  `tests/test_backtest_position_overview.py`,
  `tests/test_backtest_position_monitor.py`, `tests/test_backtest_early_warning.py`,
  `tests/test_backtest_page.py`

**Interfaces:** No new product interface. The report records commands and
actual totals; never invent a pass count.

- [x] **Step 1: Run the focused regression gate.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_position_risk tests.test_backtest_manual_position_store tests.test_backtest_position_overview tests.test_backtest_position_monitor tests.test_backtest_early_warning tests.test_backtest_page -v`

Expected: every named test passes. Investigate every failure before changing a
test or weakening any V3/position contract.

- [x] **Step 2: Run static and boundary checks.**

Run: `docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py`

Run: `rg -n "load_rulebook_result|load_current_rulebook_document|load_all_positions|load_position_history" app/backtest_engine/position_risk.py`

Run: `rg -n "SELL|sell_reason|close_manual_position" app/backtest_engine/position_risk.py app/pages/backtest_lab.py`

Run: `rg -n "[ \t]+$" app/backtest_engine/position_risk.py app/backtest_engine/manual_position_store.py app/backtest_engine/position_overview.py app/backtest_engine/indicators.py app/pages/backtest_lab.py tests/test_backtest_position_risk.py`

Expected: compilation succeeds; first search has no matches; second search
contains no Phase B SELL-write path; trailing-whitespace search has no output.
Do not run Git checks.

- [x] **Step 3: Perform implementation self-criticism.**

Check the delivered code against every design rule: T+3 strict count, shared
latest bar, no current date, raw BIGINT math, freeze-only schema-4 routing,
both manual horizons/four gates, cache key, exact text, persistence
invalidation, CLOSED strike-through, and no legacy/SELL path. Fix each found
issue and rerun affected tests.

- [x] **Step 4: Record evidence-based completion.**

Write the verification report with actual command output totals, changed files,
the one shared-bar behavior, and known limits. Mark the Phase B plan complete
only after every Task 1–5 checkbox is complete. Update FOCUS/current status to
show Phase B verified and that Validate Positions remains informational/manual.

---

## Plan self-review

- Spec coverage: Tasks 1–2 cover all formulas, T+3, V4/no-signal routing,
  shared data, theme, cache, and error isolation. Task 3 covers only the
  approved manual risk field/invalidation and legacy display removal. Task 4
  covers selection and exact presentation. Task 5 covers verification/docs.
- Completeness scan: no `TBD`, deferred behavior, or implicit error handling.
  Every error state has an exact route/result.
- Type consistency: the page uses candidate IDs from
  `list_validate_position_candidates`; the batch service owns assessment and
  writer calls; the manual writer is the only persistence endpoint.
