# Validate Signals Drafts and Manual Positions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate score similarity from VN-Index eligibility, create gated Validate Signals trade drafts, and add signal-backed or P&L-only manual positions without changing backtest artifacts, database data, or automatic trading behavior.

**Architecture:** Preserve legacy tuple history files and add one atomic generic history at `backtest-positions/<TICKER>/<TICKER>_manual_positions.json`. A shared signal-identity helper prevents a generic signal-backed OPEN record from overlapping a legacy or generic saved-set OPEN record. The overview reads both sources, performs one bound latest-close query plus one bound trading-session query, and the Streamlit page keeps Validate drafts in session state until Current Positions completes or cancels them.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, SQLAlchemy, PostgreSQL, unittest.

## Global Constraints

- Do not commit, alter Docker, dependencies, `.env`, `app/common_queries.py`, `BASE_DELTA_CALC_CTE`, `COMMON_DELTA_FILTER_WHERE_CLAUSE`, `app/data_preparation.py`, or database price storage.
- All stored prices remain raw BIGINT. UI conversion stays in `commons.price_utils`; SQL must never divide prices.
- SQL uses `sqlalchemy.text()`, `engine.raw_connection()`, and `%(parameter)s` bindings.
- Existing legacy per-theme/per-metric JSON files retain current load, edit, and close behavior. Never migrate or rewrite them.
- Validate Signals BUY/SELL gates create drafts only. Current Positions direct create/close actions remain manual and bypass those advisory gates.
- A trade has one corresponding BUY and SELL. Multi-BUY/multi-SELL is out of scope.
- Quantity is persisted as existing optional positive whole-share `quantity`; UI label becomes `Volume (optional)`.
- Position association is immutable. A new association requires a new position.
- Every production change starts with a focused failing test, then turns GREEN before next task. No task requires a commit.

## File Map

| File | Responsibility |
| --- | --- |
| `app/backtest_engine/position_identity.py` | Canonical saved-set key shared by generic store, legacy overlap guard, validation, and catalog. |
| `app/backtest_engine/manual_position_store.py` | Atomic generic history for no-signal and multi-metric signal-backed records. |
| `app/backtest_engine/position_overview.py` | Merge legacy/generic records, latest-price P&L, one-query completed-session counts. |
| `app/backtest_engine/validation_advice.py` | Score-only match level; maps generic OPEN saved-set record to every linked metric and monitors it. |
| `app/backtest_engine/position_monitor.py` | Normalizes manual calendar BUY date to first ticker session on/after it. |
| `app/backtest_engine/signal_catalog.py` | Lists saved-set selector options and read-only prepares current replay reference/risk basis. |
| `app/pages/backtest_lab.py` | Summary grouping/editor/drafts, direct manual creation, direct manual close, display wording. |
| `tests/test_backtest_*.py` | Focused unit/AppTest regression coverage. |

---

### Task 1: Correct Match Similarity Semantics — Complete

**Files:**

- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `tests/test_backtest_validation_advice.py`

**Interfaces:**

- Produces `match_level(current_score: float, threshold_score_buy: int) -> float`.
- Keeps `theme_eligible` separate from the similarity calculation and keeps it in the `buy_eligible` condition.

- [x] **Step 1: Add root-cause regression coverage.**

```python
def test_unconfirmed_theme_keeps_score_similarity_but_blocks_advice(self) -> None:
    themed = _replay(
        "background-theme", {"win_rate": 75, "profit": 75, "sharpe": 75},
        theme_state="not_confirmed",
    )
    with patch(
        "backtest_engine.validation_advice.check_current_situation",
        return_value=themed,
    ):
        result = validate_saved_signals("VCB", True, engine=object())

    metric = result["variants"]["background-theme"]["results"]["win_rate"]
    self.assertEqual(metric["match_level"], 100.0)
    self.assertEqual(metric["match_classification"], "closely_match")
    self.assertFalse(metric["theme_eligible"])
    self.assertFalse(metric["buy_eligible"])
    self.assertEqual(metric["advice"], "observe")
```

- [x] **Step 2: Run the regression RED.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_validation_advice.ValidationAdviceTests.test_unconfirmed_theme_keeps_score_similarity_but_blocks_advice -v
```

Expected: FAIL because current `match_level(75.0, 60, False)` returns `0.0`.

- [x] **Step 3: Remove theme eligibility from `match_level`.**

```python
def match_level(current_score: float, threshold_score_buy: int) -> float:
    """Return capped two-decimal score similarity independent of theme."""

    score = float(current_score)
    threshold = int(threshold_score_buy)
    if not math.isfinite(score) or threshold <= 0:
        raise ValueError("current score must be finite and threshold must be positive")
    return round(min(100.0, score / threshold * 100.0), 2)

# _compose_metric keeps this separate gate.
level = match_level(float(current_score), int(combo["threshold_score_buy"]))
buy_eligible = theme_eligible and classify_match(level) != "observe"
```

- [x] **Step 4: Update existing direct `match_level` tests to its two-argument contract.**

```python
self.assertEqual(match_level(49, 70), 70.0)
self.assertEqual(match_level(80, 70), 100.0)
```

- [x] **Step 5: Run Task 1 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_validation_advice -v
```

Expected: all validation-advice tests pass; unconfirmed theme remains ineligible but no longer displays `0` solely for that reason.

---

### Task 2: Add Generic Manual Position Storage and Saved-Set Identity — Complete

**Files:**

- Create: `app/backtest_engine/position_identity.py`
- Create: `app/backtest_engine/manual_position_store.py`
- Create: `tests/test_backtest_manual_position_store.py`

**Interfaces:**

- Produces `signal_link_key(theme_variant: str, metric: str, certified_signal: Mapping[str, object]) -> str`.
- Produces `load_manual_position_history(ticker, positions_dir="backtest-positions") -> dict[str, object]`.
- Produces `create_manual_position(ticker, actual_buy_price, buy_date, *, actual_sell_price=None, sell_date=None, quantity=None, signal_reference=None, entry_context=None, risk_snapshot=None, origin="current_positions", positions_dir="backtest-positions") -> dict[str, object]`.
- Produces `update_manual_position(ticker, position_id, updates, positions_dir="backtest-positions") -> dict[str, object]` and `close_manual_position(ticker, position_id, actual_sell_price, sell_date, positions_dir="backtest-positions") -> dict[str, object]`.

- [x] **Step 1: Write failing generic-history tests.**

```python
def test_creates_open_and_closed_pnl_only_records_with_calendar_dates(self):
    with tempfile.TemporaryDirectory() as directory:
        opened = create_manual_position(
            "FPT", 50300, "2026-08-08", quantity=None, positions_dir=directory
        )
        closed = create_manual_position(
            "FPT", 50000, "2026-08-02", actual_sell_price=52000,
            sell_date="2026-08-10", quantity=100, positions_dir=directory
        )
        history = load_manual_position_history("FPT", directory)

    self.assertEqual(opened["status"], "open")
    self.assertIsNone(opened["signal_reference"])
    self.assertEqual(closed["status"], "closed")
    self.assertEqual(len(history["history"]), 2)

def test_rejects_exactly_one_manual_sell_value(self):
    with self.assertRaisesRegex(ValueError, "SELL price and SELL date"):
        create_manual_position("FPT", 50300, "2026-08-08", actual_sell_price=52000)
```

- [x] **Step 2: Write failing saved-set identity/invariant tests.**

```python
def test_signal_backed_open_links_all_metrics_and_blocks_legacy_overlap(self):
    reference, context, risk = _signal_reference(metrics=("win_rate", "profit"))
    with tempfile.TemporaryDirectory() as directory:
        record = create_manual_position(
            "FPT", 50300, "2026-08-07", signal_reference=reference,
            entry_context=context, risk_snapshot=risk, positions_dir=directory
        )
        with self.assertRaisesRegex(ValueError, "already has an OPEN position"):
            create_manual_position(
                "FPT", 50400, "2026-08-08", signal_reference=reference,
                entry_context=context, risk_snapshot=risk, positions_dir=directory
            )

    self.assertEqual(record["signal_reference"]["metrics"], ["win_rate", "profit"])

def test_pnl_only_open_positions_are_not_limited_per_ticker(self):
    with tempfile.TemporaryDirectory() as directory:
        create_manual_position("FPT", 50000, "2026-08-01", positions_dir=directory)
        create_manual_position("FPT", 51000, "2026-08-02", positions_dir=directory)
        history = load_manual_position_history("FPT", directory)

    self.assertEqual(sum(item["status"] == "open" for item in history["history"]), 2)
```

- [x] **Step 3: Run generic-store tests RED.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_manual_position_store -v
```

Expected: FAIL with `ModuleNotFoundError` before generic store exists.

- [x] **Step 4: Implement canonical immutable link keys.**

```python
def signal_link_key(
    theme_variant: str,
    metric: str,
    certified_signal: Mapping[str, object],
) -> str:
    payload = {
        "theme_variant": theme_variant,
        "metric": metric,
        "certified_signal": copy.deepcopy(dict(certified_signal)),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
```

Validate theme/metric/certificate consistency before hashing. Do not use Python `hash()`, because it changes across processes.

- [x] **Step 5: Implement generic history schema and atomic writes.**

```python
{
    "schema_version": 1,
    "ticker": "FPT",
    "history": [
        {
            "id": "uuid",
            "ticker": "FPT",
            "status": "open",
            "origin": "current_positions",
            "signal_reference": None,
            "certified_signal": None,
            "entry_context": None,
            "risk_snapshot": None,
            "actual_buy_price": 50300,
            "quantity": None,
            "buy_date": "2026-08-08",
            "opened_at": "2026-08-12T09:00:00+07:00",
            "actual_sell_price": None,
            "sell_date": None,
            "closed_at": None,
        }
    ],
}
```

Use existing `_normalize_ticker`, raw-price/quantity validators, Ho Chi Minh timestamp rule, `_risk_for_buy_price`, and `_write_history` from `position_store.py`. A signal-backed record stores immutable `signal_reference` with `theme_variant`, ordered `metrics`, per-metric certified snapshots, and canonical link keys; it also stores one representative `certified_signal`, `entry_context`, and frozen risk snapshot for native monitoring.

- [x] **Step 6: Enforce generic/legacy OPEN overlap safely.**

```python
def _assert_no_open_signal_overlap(reference, ticker, positions_dir):
    requested = set(reference["link_keys"])
    for position in _all_manual_open_records(ticker, positions_dir):
        if requested.intersection(position_signal_link_keys(position)):
            raise ValueError("saved signal set already has an OPEN position")
    for theme_variant, metric in reference_metric_pairs(reference):
        legacy = load_position_history(ticker, theme_variant, metric, positions_dir)
        if any(item["status"] == "open" for item in legacy["history"]):
            raise ValueError("saved signal set already has an OPEN position")
```

Do not suppress invalid JSON/schema errors from the relevant legacy tuple: inability to prove no existing OPEN signal set must reject creation rather than create a duplicate.

- [x] **Step 7: Implement generic update/close rules.**

```python
allowed = {"actual_buy_price", "actual_sell_price", "quantity"}
# BUY price recalculates SL/TP only when risk_snapshot exists.
# signal_reference and its metrics are never accepted update fields.
# close_manual_position changes one OPEN record to CLOSED and writes both SELL fields.
```

`create_manual_position` accepts OPEN only with both SELL fields absent, CLOSED only with both supplied, and rejects a SELL date before BUY date. `close_manual_position` permits any generic OPEN record because Current Positions actions bypass advisory gates.

- [x] **Step 8: Run Task 2 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_manual_position_store tests.test_backtest_position_store -v
```

Expected: generic and legacy position tests pass; legacy files remain untouched.

---

### Task 3: Combine Position Sources, P&L, and Completed Trading Sessions — Complete

**Files:**

- Modify: `app/backtest_engine/position_overview.py`
- Modify: `tests/test_backtest_position_overview.py`

**Interfaces:**

- `load_all_positions()` returns legacy and generic records with `record_source` and a storage-specific `position_locator`.
- Produces `load_completed_trading_sessions(records, latest_prices, engine) -> dict[str, list[str]]`, where each list contains all database sessions from that ticker's earliest relevant BUY date through its latest required reference date. `summarize_positions()` filters that shared list per position.
- Extends `summarize_positions(records, latest_prices, sessions_by_ticker)` with `holding_sessions` and generic signal labels.

- [x] **Step 1: Write failing dual-source and hold-session tests.**

```python
def test_overview_merges_legacy_and_generic_records_without_writing(self):
    with tempfile.TemporaryDirectory() as directory:
        legacy = _create_legacy_open(directory)
        generic = create_manual_position("VCB", 50000, "2026-08-02", positions_dir=directory)
        records, errors = load_all_positions(directory)

    self.assertEqual({record["record_source"] for record in records}, {"legacy", "manual"})
    self.assertEqual(errors, ())
    self.assertEqual({record["id"] for record in records}, {legacy["id"], generic["id"]})

def test_completed_sessions_exclude_buy_and_use_last_session_on_or_before_calendar_sell(self):
    sessions = {"FPT": ("2026-08-03", "2026-08-04", "2026-08-05", "2026-08-07")}
    row = summarize_positions(
        (_manual_position(buy_date="2026-08-02", sell_date="2026-08-08", status="closed"),),
        {}, sessions,
    )[0]
    self.assertEqual(row["holding_sessions"], 4)

def test_completed_sessions_filter_shared_ticker_rows_per_position_buy_and_reference_dates(self):
    sessions = {"FPT": ("2026-08-03", "2026-08-04", "2026-08-05", "2026-08-07")}
    rows = summarize_positions(
        (
            _manual_position(buy_date="2026-08-02", sell_date="2026-08-08", status="closed"),
            _manual_position(buy_date="2026-08-04", sell_date="2026-08-05", status="closed"),
        ),
        {}, sessions,
    )
    self.assertEqual([row["holding_sessions"] for row in rows], [4, 1])
```

- [x] **Step 2: Write the one-query session-loader test.**

```python
def test_completed_sessions_uses_one_bound_query_per_refresh(self):
    records = (_manual_position("FPT"), _manual_position("VCB"))
    engine, connection = Mock(), Mock()
    engine.raw_connection.return_value = connection
    with patch("backtest_engine.position_overview.pd.read_sql", return_value=_session_frame()) as read_sql:
        sessions = load_completed_trading_sessions(records, {"FPT": {"date": "2026-08-10"}}, engine)

    read_sql.assert_called_once()
    self.assertEqual(sorted(read_sql.call_args.kwargs["params"]["tickers"]), ["FPT"])
    self.assertEqual(sessions["FPT"][-1], "2026-08-10")
    connection.close.assert_called_once()
```

- [x] **Step 3: Run overview tests RED.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_position_overview -v
```

Expected: FAIL because generic records and completed-session loader do not exist.

- [x] **Step 4: Merge generic records while isolating bad files.**

```python
try:
    generic = load_manual_position_history(ticker, str(root))
except (OSError, ValueError) as error:
    errors.append(f"{ticker}/manual: {error}")
else:
    records.extend(_with_locator(record, "manual") for record in generic["history"])
```

Read each generic file once. Keep legacy malformed-file isolation unchanged.

- [x] **Step 5: Add one parameterized trading-session query.**

```sql
WITH requested AS (
    SELECT *
    FROM unnest(
        %(tickers)s::text[],
        %(start_dates)s::date[],
        %(end_dates)s::date[]
    ) AS request(ticker, start_date, end_date)
)
SELECT data.ticker, data.date
FROM trading_data AS data
JOIN requested
  ON requested.ticker = data.ticker
 AND data.date > requested.start_date
 AND data.date <= requested.end_date
ORDER BY data.ticker, data.date
```

Build one requested range per ticker: earliest BUY date and latest usable reference date. For OPEN use the loaded latest-price date; for CLOSED use SELL date. Return no session rows for an OPEN ticker without a latest price. This directly implements completed sessions after BUY through last database session on/before reference date.

- [x] **Step 6: Extend display rows.**

```python
reference_date = latest.get("date") if is_open else position.get("sell_date")
holding_sessions = sum(
    buy_date < session_date <= reference_date
    for session_date in sessions_by_ticker.get(ticker, ())
)
signal_set = _signal_set(position)  # "-" for P&L-only; linked metric labels otherwise
```

Keep price P&L calculations raw and unchanged. Add `holding_sessions` to summary data and render `Hold time` as `"{n} sessions"` or `"Unavailable"`.

- [x] **Step 7: Run Task 3 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_position_overview tests.test_backtest_manual_position_store -v
```

Expected: overview shows combined positions, exact raw P&L, and completed-session timing using one bound session query.

---

### Task 4: Replay Catalog and Generic Position Monitoring — Complete

**Files:**

- Create: `app/backtest_engine/signal_catalog.py`
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `app/backtest_engine/position_monitor.py`
- Create: `tests/test_backtest_signal_catalog.py`
- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `tests/test_backtest_position_monitor.py`

**Interfaces:**

- Produces `list_saved_signal_options(ticker, signal_dir) -> list[dict[str, object]]`.
- Produces `prepare_signal_reference(ticker, theme_variant, metric, engine, signal_dir) -> dict[str, object]`.
- `validate_saved_signals()` maps a generic signal-backed OPEN record to every immutable linked metric.

- [x] **Step 1: Write failing catalog/reference tests.**

```python
def test_catalog_lists_each_available_saved_metric_without_replaying(self):
    with tempfile.TemporaryDirectory() as directory:
        _save_artifact(directory, "FPT", "no-background-theme", {"win_rate": _certified("win_rate")})
        options = list_saved_signal_options("FPT", directory)

    self.assertEqual(options[0]["label"], "No theme — Best by Win Rate")
    self.assertEqual(options[0]["metrics"], ("win_rate",))

def test_prepare_reference_uses_current_replay_as_of_and_frozen_atr_basis(self):
    with patch("backtest_engine.signal_catalog.check_current_situation", return_value=_replay_for("win_rate")):
        reference = prepare_signal_reference("FPT", "no-background-theme", "win_rate", object(), "signals")

    self.assertEqual(reference["as_of_date"], "2026-08-10")
    self.assertEqual(reference["risk_basis"], {"atr": 1000, "max_hold_bars": 15})
```

- [x] **Step 2: Write failing generic-position validation/monitor tests.**

```python
def test_generic_open_signal_record_is_attached_to_every_linked_metric(self):
    generic = _generic_open_reference(metrics=("win_rate", "profit"))
    with patch("backtest_engine.validation_advice.load_manual_position_history", return_value={"history": [generic]}):
        result = validate_saved_signals("FPT", False, object())

    metrics = result["variants"]["no-background-theme"]["results"]
    self.assertEqual(metrics["win_rate"]["open_position"]["id"], generic["id"])
    self.assertEqual(metrics["profit"]["open_position"]["id"], generic["id"])

def test_manual_weekend_buy_monitor_starts_from_first_database_session_after_buy(self):
    history = _daily_history(5)
    result = monitor_position(_position(buy_date="2026-01-03"), history, history.loc[4, "date"])
    self.assertEqual(result["holding_bars"], 5)
```

- [x] **Step 3: Run Task 4 RED.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_validation_advice tests.test_backtest_position_monitor -v
```

Expected: FAIL because catalog/reference and generic metric mapping are absent; monitor rejects weekend BUY dates.

- [x] **Step 4: Implement catalog-only artifact listing and read-only reference preparation.**

```python
def prepare_signal_reference(ticker, theme_variant, metric, engine, signal_dir):
    replay = check_current_situation(
        ticker, metric=metric, theme_variant=theme_variant, engine=engine, output_dir=signal_dir
    )
    metric_replay = replay["results"][metric]
    current = metric_replay["current"]
    certified = metric_replay["certified"]
    return _validated_reference(ticker, theme_variant, metric, certified, current)
```

`list_saved_signal_options` only reads existing artifact JSON through `load_certified_signals`; it never invokes replay. `prepare_signal_reference` performs the one needed read-only replay on form submission and returns the selected certificate, current as-of date, raw ATR, native max hold, and canonical link key. Reject missing/nonpositive ATR or invalid current context before storage.

- [x] **Step 5: Attach generic OPEN records to all linked metrics.**

```python
for position in manual_history["history"]:
    if position.get("status") != "open":
        continue
    reference = position.get("signal_reference")
    if not isinstance(reference, Mapping):
        continue
    for metric in reference.get("metrics", ()):
        positions_by_variant[reference["theme_variant"]][metric] = position
```

Pass each unique generic signal-backed record to `monitor_position` once. P&L-only records have no reference and never enter Validate Signals monitoring.

- [x] **Step 6: Normalize manual calendar BUY date in native monitor.**

```python
entry_rows = source[source_dates >= buy_date]
if entry_rows.empty:
    raise ValueError("position buy_date has no ticker trading session on or after it")
entry_date = pd.Timestamp(entry_rows.iloc[0]["date"]).normalize()
```

Use `entry_date` instead of direct exact-date equality for daily/weekly native holding calculations. Legacy valid trading-date behavior remains unchanged.

- [x] **Step 7: Run Task 4 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_validation_advice tests.test_backtest_position_monitor -v
```

Expected: direct signal selection prepares a frozen current-as-of reference; generic linked positions monitor once and appear under all linked metrics.

---

### Task 5: Redesign Validate Summary and Create Session Drafts — Complete

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Produces pure `_group_summary_rows(ticker, theme_variant, metric_results) -> list[dict[str, object]]`.
- Produces pure `_build_validate_trade_draft(ticker, theme_variant, group) -> dict[str, object]`.
- Uses session key `_VALIDATE_TRADE_DRAFT_KEY` for one pending draft.

- [x] **Step 1: Add focused summary formatting/grouping tests.**

```python
def test_summary_formats_leaf_indicators_dates_and_prices_without_vnd(self):
    row = _summary_row("FPT", "no-background-theme", "win_rate", _validation_metric())
    self.assertEqual(row["Strategy: Indicators"], "MA cross, RSI, OBV")
    self.assertEqual(row["Trade: Signal date"], "2026-08-07")
    self.assertNotIn("VND", row["Trade: Entry"])

def test_summary_groups_only_identical_non_metric_values_and_action_state(self):
    grouped = _group_summary_rows("FPT", "no-background-theme", _matching_metric_results())
    self.assertEqual(grouped[0]["display"]["Identity: Metric"], "Best by Win Rate, Best by %Profit")
    self.assertEqual(grouped[0]["metrics"], ("win_rate", "profit"))
    self.assertEqual(len(_group_summary_rows("FPT", "no-background-theme", _different_action_results())), 2)
```

- [x] **Step 2: Add draft gate and one-pending-draft tests.**

```python
def test_build_draft_accepts_only_gated_buy_or_sell_summary_group(self):
    buy = _build_validate_trade_draft("FPT", "no-background-theme", _buy_group())
    sell = _build_validate_trade_draft("FPT", "no-background-theme", _sell_group())
    self.assertEqual(buy["action"], "buy")
    self.assertEqual(sell["action"], "sell")
    with self.assertRaisesRegex(ValueError, "not eligible"):
        _build_validate_trade_draft("FPT", "no-background-theme", _observe_group())
```

- [x] **Step 3: Add AppTest structure coverage.**

```python
app = AppTest.from_string(_page_script(_validation_payload(include_theme=True))).run()
_click(app, "Validate saved signals")
self.assertTrue(any(item.label == "Summary columns" for item in app.expander))
self.assertTrue(any("Create trade" == item.label for item in app.button))
self.assertFalse(any("VND" in item.label for item in app.number_input))
```

Also assert `Backtest: Date range` checkbox defaults false while default performance/match/trade/position fields remain selected.

- [x] **Step 4: Run page tests RED.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_page -v
```

Expected: FAIL because summary has a multiselect, shows `k VND`, has one row per metric, and directly persists BUY/SELL forms.

- [x] **Step 5: Implement display helpers and grouping.**

```python
def _display_signal_date(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "-" if pd.isna(parsed) else parsed.date().isoformat()

def _indicator_names(indicators: object) -> str:
    if not isinstance(indicators, Mapping):
        return "-"
    return ", ".join(str(name) for names in indicators.values() if isinstance(names, list) for name in names)
```

Change `_format_raw_price` to return `"{rendered} k"`. Remove `Backtest: Date range` from `_SUMMARY_DEFAULT_COLUMNS`. Group using every display key except `Identity: Metric` plus action kind and SELL locator; preserve all metric result objects privately in each group.

- [x] **Step 6: Replace multiselect with collapsed checkbox controls and a non-persistent editor.**

```python
with st.expander("Summary columns", expanded=False):
    selected = [
        column for column in columns
        if st.checkbox(column, value=column in _SUMMARY_DEFAULT_COLUMNS, key=f"summary_column_{theme_variant}_{column}")
    ]
edited = st.data_editor(
    pd.DataFrame(summary_display_rows),
    disabled=[column for column in selected if column != "Select"],
    column_config={"Select": st.column_config.CheckboxColumn(required=False)},
    hide_index=True,
    key=f"summary_editor_{theme_variant}",
)
```

Keep `Select` and user-selected display columns only. Derive selected indices from returned `edited["Select"]`; do not persist checkbox data in artifacts or position files.

- [x] **Step 7: Replace direct detail BUY/SELL forms with draft creation.**

```python
if st.button("Create trade", disabled=draft_exists, key=f"create_trade_{theme_variant}"):
    selected_rows = edited.index[edited["Select"].fillna(False)]
    if len(selected_rows) != 1:
        st.error("Select exactly one signal-set row.")
    else:
        st.session_state[_VALIDATE_TRADE_DRAFT_KEY] = _build_validate_trade_draft(
            ticker, theme_variant, grouped_rows[int(selected_rows[0])]
        )
        st.rerun()
```

`_render_metric_advice` becomes read-only detail content. BUY draft includes frozen risk basis and locked as-of date; SELL draft includes one exact legacy/manual locator. A pending draft renders a block message until Current Positions saves or cancels it.

- [x] **Step 8: Run Task 5 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_page tests.test_backtest_validation_advice -v
```

Expected: summary is grouped/readable, actions create no records, and only a valid selected gated row produces one pending draft.

---

### Task 6: Complete Drafts and Direct Manual Positions in Current Positions — Complete

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- `render_backtest_page()` gains injectable `manual_position_fn`, `manual_close_fn`, `manual_update_fn`, `signal_options_fn`, and `prepare_signal_reference_fn` defaults.
- Produces `_close_by_locator(locator, actual_sell_price, sell_date, positions_dir) -> dict[str, object]` for one exact legacy or generic OPEN record.
- Current Positions renders `_render_pending_trade_draft`, `_render_add_manual_position`, and locator-routed individual edit/close forms.

- [x] **Step 1: Write AppTest coverage for direct no-signal records.**

```python
def test_current_positions_adds_open_and_closed_pnl_only_positions(self):
    app = AppTest.from_string(_manual_page_script()).run()
    _click(app, "Add new position")
    _set_text(app, "New position ticker", "FPT")
    _set_number(app, "BUY price (k)", 50.3)
    _click(app, "Save new position")
    self.assertEqual(_manual_records(app)[0]["status"], "open")

    _set_number(app, "SELL price (k)", 52.0)
    _set_date(app, "SELL date", date(2026, 8, 10))
    _click(app, "Save new position")
    self.assertEqual(_manual_records(app)[1]["status"], "closed")
```

Add a failing one-SELL-field test asserting a visible `SELL price and SELL date` error and no storage call.

- [x] **Step 2: Write draft/save contract coverage.**

```python
def test_direct_saved_set_replays_then_creates_closed_record_without_validate_gate(self):
    app = AppTest.from_string(_manual_page_script(signal_options=_options())).run()
    _select(app, "Saved signal set", "No theme — Best by Win Rate")
    _set_number(app, "BUY price (k)", 50.3)
    _set_number(app, "SELL price (k)", 52.0)
    _click(app, "Save new position")
    self.assertEqual(_manual_records(app)[0]["signal_reference"]["metrics"], ["win_rate"])
    self.assertEqual(_manual_records(app)[0]["status"], "closed")

def test_validate_buy_draft_locks_as_of_date_and_cancel_removes_only_draft(self):
    app = AppTest.from_string(_draft_page_script()).run()
    self.assertTrue(_date_input(app, "BUY date").disabled)
    _click(app, "Cancel draft")
    self.assertFalse(_draft_exists(app))
    self.assertEqual(_manual_records(app), [])
```

- [x] **Step 3: Write exact-record close/routing coverage.**

```python
def test_current_positions_closes_exact_open_manual_record_and_keeps_other_open_record(self):
    app = AppTest.from_string(_two_open_manual_records_script()).run()
    _set_number(app, "Actual SELL price (k)", 53.0, occurrence=0)
    _click(app, "Close position", occurrence=0)
    records = _manual_records(app)
    self.assertEqual(records[0]["status"], "closed")
    self.assertEqual(records[1]["status"], "open")
```

Also assert an edit cannot change `signal_reference`, buy/sell timestamps remain unchanged for price/volume edits, and generic BUY price recalculates its SL/TP from frozen ATR.

- [x] **Step 4: Run page regression to expose obsolete direct-form expectations.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_page -v
```

Expected: FAIL because no add form, draft completion, generic record router, or direct generic close form exists.

- [x] **Step 5: Implement pending-draft UI.**

```python
draft = st.session_state.get(_VALIDATE_TRADE_DRAFT_KEY)
if isinstance(draft, Mapping) and draft["action"] == "buy":
    st.date_input("BUY date", value=draft["as_of_date"], disabled=True)
    if st.form_submit_button("Save draft BUY"):
        create_manual_position(
            draft["ticker"],
            price_from_ui_k_vnd(actual_buy_price_k),
            draft["as_of_date"],
            quantity=volume,
            signal_reference=draft["signal_reference"],
            entry_context=draft["entry_context"],
            risk_snapshot=draft["risk_snapshot"],
            origin="validate_draft",
            positions_dir=positions_dir,
        )
if isinstance(draft, Mapping) and draft["action"] == "sell":
    if st.form_submit_button("Save draft SELL"):
        _close_by_locator(
            draft["position_locator"],
            price_from_ui_k_vnd(actual_sell_price_k),
            sell_date,
            positions_dir,
        )
if st.button("Cancel draft"):
    st.session_state.pop(_VALIDATE_TRADE_DRAFT_KEY, None)
    st.rerun()
```

Clear draft and cached overview only after the underlying atomic store call succeeds. For a failed store call, keep the draft and show the validation error.

- [x] **Step 6: Implement direct Add new position.**

```python
if st.button("Add new position"):
    st.session_state[_MANUAL_POSITION_FORM_KEY] = True
if not st.session_state.get(_MANUAL_POSITION_FORM_KEY):
    return

new_ticker = st.text_input("New position ticker", key="manual_position_ticker").strip().upper()
options = signal_options_fn(new_ticker, signal_dir) if new_ticker else ()
choice = st.selectbox("Saved signal set", ("-", *(item["label"] for item in options)))
buy_price = st.number_input("BUY price (k)", min_value=0.001, value=None, step=0.001)
buy_date = st.date_input("BUY date", value=date.today())
volume = st.number_input("Volume (optional)", min_value=1, value=None, step=1)
sell_price = st.number_input("SELL price (k)", min_value=0.001, value=None, step=0.001)
sell_date = st.date_input("SELL date", value=None)
```

When choice is `-`, create P&L-only generic record. For selected option, call `prepare_signal_reference` at save time, derive frozen raw risk from its current ATR/max hold and user BUY price, then create generic signal-backed record. Both OPEN and CLOSED direct records bypass advisory gates but enforce atomic input and duplicate-OPEN invariants.

Before invoking either store path, pass `None` for both SELL values only when
both widgets are blank; reject exactly one supplied SELL value with `SELL price
and SELL date must be supplied together`. Pass direct `buy_date` and complete
`sell_date` through unchanged so calendar dates are accepted; database session
lookup alone derives hold time.

- [x] **Step 7: Route existing edit and close forms by locator.**

```python
if locator["record_source"] == "legacy":
    update_position(
        locator["ticker"], locator["theme_variant"], locator["metric"],
        locator["id"], updates, positions_dir,
    )
    close_position(
        locator["ticker"], locator["theme_variant"], locator["metric"],
        locator["id"], actual_sell_price, sell_date, "manual_close", positions_dir,
    )
else:
    update_manual_position(locator["ticker"], locator["id"], updates, positions_dir)
    close_manual_position(locator["ticker"], locator["id"], sell_price, sell_date, positions_dir)
```

Render `Close position` for every OPEN record in Current Positions. It writes the corresponding existing record only; never creates a second unrelated SELL record. Rename editable `Quantity (optional)` labels to `Volume (optional)` without changing stored field names.

- [x] **Step 8: Run Task 6 GREEN.**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest tests.test_backtest_page tests.test_backtest_manual_position_store tests.test_backtest_position_overview -v
```

Expected: direct/manual/draft position paths create or close one exact record, preserve immutable signal association, and keep P&L/hold-time display correct.

---

### Task 7: Regression Gate, Review, and Context — Complete

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-12-validate-signals-drafts-manual-positions-verification.md`

- [x] **Step 1: Run complete package-named Backtest gate.**

```powershell
$backtestModules = Get-ChildItem tests -Filter 'test_backtest*.py' |
  ForEach-Object { 'tests.' + $_.BaseName }
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m unittest $backtestModules -v
```

Expected: zero failures. Keep package-qualified names; plain discovery breaks worker-fixture imports.

- [x] **Step 2: Compile and run scoped checks.**

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -m compileall -q backtest_engine pages/backtest_lab.py
rg -n "[ \t]+$" app/backtest_engine/position_identity.py `
  app/backtest_engine/manual_position_store.py app/backtest_engine/signal_catalog.py `
  app/backtest_engine/position_overview.py app/backtest_engine/validation_advice.py `
  app/backtest_engine/position_monitor.py app/pages/backtest_lab.py `
  tests/test_backtest_manual_position_store.py tests/test_backtest_signal_catalog.py `
  tests/test_backtest_position_overview.py tests/test_backtest_validation_advice.py `
  tests/test_backtest_position_monitor.py tests/test_backtest_page.py
git diff --check
```

Expected: compiler exit `0`, no scoped trailing whitespace, and no diff errors.

- [x] **Step 3: Run read-only live probes.**

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app `
  python -c "from backtest_engine.validation_advice import validate_saved_signals; from backtest_engine.pipeline import _database_url; from pages.data_preparation import get_engine_with_retry; engine=get_engine_with_retry(_database_url()); result=validate_saved_signals('VCB', True, engine, 'ticker-signals', 'backtest-positions'); print(result['variants']['background-theme']['results']['win_rate']['match_level']); engine.dispose()"
```

Expected: VCB themed score similarity prints nonzero/`100.0` when score is 75 and threshold is 60, while `theme_eligible` remains false. Run a Current Positions read-only overview refresh only; do not save a position, artifact, or database row.

- [x] **Step 4: Complete implementation review and update context.**

Review SQL parameterization/raw connections, BIGINT display boundary, generic atomic overwrite, legacy compatibility, one-open saved-set invariant, session-only drafts, no automatic trade, and monitor calendar-date normalization. Record exact command outcomes in report, mark all plan tasks in `FOCUS.md`, update WIP status, and do not commit.
