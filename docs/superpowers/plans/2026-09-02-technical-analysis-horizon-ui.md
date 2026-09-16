# Technical Analysis Horizon UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Technical Analysis sidebar inputs with Ticker/Horizon analysis and produce the existing result experience with one added causal Alligator indicator.

**Architecture:** Keep legacy `build_technical_snapshot()` unchanged for Analyze/API callers. Add a focused horizon adapter that reuses schema-5 Backtest rulebook configuration and indicator frames, enriches the native frame with existing Technical-only indicators, and returns a UI-ready snapshot capped at 100 completed native bars.

**Tech Stack:** Python 3.12, Streamlit 1.62, pandas 3.0, Plotly, SQLAlchemy, PostgreSQL, unittest/Streamlit AppTest.

## Global Constraints

- Inputs are only `Ticker` and `Horizon`; horizon choices are `Swing` and `Mid-term`.
- No Technical Analysis control may render in `st.sidebar`.
- Swing uses daily EMA(5/13), RSI(9), causal Alligator 8/5/3 shifted 5/3/2, exact Wilder ADX(14), and exact Wilder ATR(14).
- Mid-term uses completed W-FRI SMA(8/21), RSI(14), causal Alligator 13/8/5 shifted 8/5/3, exact Wilder ADX(14), and exact Wilder ATR(14).
- Output contains up to 100 native bars. Fewer bars remain usable; unavailable indicators show `Unknown`/`N/A`.
- Existing MA, MA Cross, RSI, Stochastic, ADX, OBV, ATR, and Bollinger results remain. Alligator is the only new indicator.
- Relative volume and other Backtest gates are excluded.
- Existing raw-data expander, candlestick/volume chart, result-only indicator selector, overview, and detail tabs remain.
- BIGINT prices stay raw through calculation and divide by 1000 only at the UI snapshot boundary.
- Use `sqlalchemy.text()`, `engine.raw_connection()`, and `%(param)s` bindings. Do not modify protected common query constants.
- No dependency, Docker, database, artifact, trading, or Git change. User explicitly prohibited Git actions, so this plan has no commit steps.

## File Map

- Create `app/commons/technical_horizon.py`: horizon normalization, raw source sizing, schema-5/native-frame construction, Technical-only enrichment, UI scaling, and nine-indicator snapshot.
- Modify `app/commons/technical_analysis.py`: extract one reusable raw ticker fetch from existing `fetch_data()` without changing its public behavior.
- Modify `app/pages/technical_visualization.py`: main-page controls, fixed horizon cache identity, result-only indicator selection, horizon-aware MA/Alligator chart traces, and nine tabs.
- Create `tests/test_technical_horizon.py`: horizon mapping, W-FRI completion, parity, output scaling, and short-history tests.
- Modify `tests/test_technical_analysis.py`: raw-fetch extraction regression.
- Modify `tests/test_technical_snapshot.py`: protect legacy eight-indicator contract.
- Modify `tests/test_technical_visualization_ui.py`: sidebar removal, control contract, Alligator chart, and nine-tab tests.
- Modify `FOCUS.md`, `ai-context/current-status.md`, and `ai-context/architecture.md`: completion state and data-flow ownership.

---

### Task 1: Raw Fetch and Horizon-Native Frame

**Files:**
- Create: `app/commons/technical_horizon.py`
- Modify: `app/commons/technical_analysis.py`
- Create: `tests/test_technical_horizon.py`
- Modify: `tests/test_technical_analysis.py`

**Interfaces:**
- Produces: `fetch_raw_technical_history(ticker: str, limit: int, engine) -> pd.DataFrame`
- Produces: `normalize_technical_horizon(value: object) -> Literal["swing", "midterm"]`
- Produces: `build_horizon_native_frame(source: pd.DataFrame, horizon: str) -> tuple[pd.DataFrame, RulebookSpec]`
- Consumes: `backtest_engine.config.rulebook_for()` and `backtest_engine.indicators.build_indicator_frame()`

- [x] **Step 1: Write failing raw-fetch and horizon tests**

Add tests proving raw BIGINT values are returned unchanged, ticker/limit are bound parameters, Swing remains daily, Mid-term contains only completed Fridays, an incomplete week is excluded, and output is capped at 100 rows.

```python
def test_horizon_contract_uses_registered_schema5_rulebooks():
    swing = normalize_technical_horizon("Swing")
    midterm = normalize_technical_horizon("Mid-term")
    assert rulebook_for(swing).ma_pair == (5, 13)
    assert rulebook_for(midterm).ma_pair == (8, 21)


def test_midterm_excludes_incomplete_week_and_caps_native_rows():
    source = make_daily_ohlcv("2023-01-02", periods=700)
    source = source.loc[source["date"] <= pd.Timestamp("2025-09-03")]
    frame, rulebook = build_horizon_native_frame(source, "Mid-term")
    assert rulebook.horizon == "midterm"
    assert len(frame) <= 100
    assert all(pd.Timestamp(value).weekday() == 4 for value in frame["date"])
    assert pd.Timestamp(frame["date"].max()) <= pd.Timestamp("2025-08-29")
```

- [x] **Step 2: Run tests and confirm red state**

Run:

```bash
python -m unittest tests.test_technical_horizon tests.test_technical_analysis -v
```

Expected: failure because `technical_horizon` and `fetch_raw_technical_history` do not exist.

- [x] **Step 3: Extract raw fetch without changing legacy fetch behavior**

Move the existing bound daily query into this public helper and make `fetch_data()` call it before its existing sorting, resampling, tail, and UI-scaling logic.

```python
def fetch_raw_technical_history(ticker, limit, engine):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("technical history limit must be positive")
    query = text(
        """
        SELECT date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = %(ticker)s
        ORDER BY date DESC
        LIMIT %(limit)s
        """
    )
    connection = engine.raw_connection()
    try:
        return pd.read_sql(
            query.text,
            connection,
            params={"ticker": str(ticker).strip().upper(), "limit": limit},
        )
    finally:
        connection.close()
```

- [x] **Step 4: Implement horizon normalization and native-frame builder**

Use 100 daily source rows for Swing and 800 daily source rows for Mid-term. `build_indicator_frame()` owns daily/W-FRI conversion and exact schema-5 calculations; tail only after that construction.

```python
TECHNICAL_NATIVE_BAR_LIMIT = 100
TECHNICAL_SOURCE_ROW_LIMIT = {"swing": 100, "midterm": 800}
_HORIZON_LABELS = {"swing": "swing", "mid-term": "midterm"}


def normalize_technical_horizon(value):
    normalized = str(value or "").strip().casefold()
    try:
        return _HORIZON_LABELS[normalized]
    except KeyError as error:
        raise ValueError("horizon must be Swing or Mid-term") from error


def build_horizon_native_frame(source, horizon):
    normalized = normalize_technical_horizon(horizon)
    if not isinstance(source, pd.DataFrame) or source.empty or "date" not in source:
        raise ValueError("technical horizon requires OHLCV history")
    dates = pd.to_datetime(source["date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("technical history contains an invalid date")
    common_as_of = pd.Timestamp(dates.max()).date()
    rulebook = rulebook_for(normalized)
    frame = build_indicator_frame(source, normalized, common_as_of=common_as_of)
    return frame.tail(TECHNICAL_NATIVE_BAR_LIMIT).reset_index(drop=True), rulebook
```

- [x] **Step 5: Run Task 1 tests**

Run:

```bash
python -m unittest tests.test_technical_horizon tests.test_technical_analysis -v
```

Expected: all tests pass; existing `fetch_data()` tests still prove k-VND UI scaling.

---

### Task 2: Nine-Indicator Horizon Snapshot

**Files:**
- Modify: `app/commons/technical_horizon.py`
- Modify: `tests/test_technical_horizon.py`
- Modify: `tests/test_technical_snapshot.py`

**Interfaces:**
- Consumes: `build_horizon_native_frame(source, horizon)` from Task 1
- Produces: `build_horizon_technical_snapshot(source: pd.DataFrame, horizon: str) -> dict[str, object]`
- Snapshot keys: `data`, `signals`, `report`, `adx_value`, `profile`, `common_as_of`
- Profile keys: `horizon`, `label`, `ma_kind`, `short_ma`, `long_ma`, `rsi_period`, `native_timeframe`

- [x] **Step 1: Write failing snapshot/parity tests**

Add deterministic fixtures comparing horizon columns with direct schema-5 output and proving exactly nine report rows.

```python
def test_swing_snapshot_matches_schema5_indicator_columns():
    source = make_daily_ohlcv("2024-01-02", periods=100)
    snapshot = build_horizon_technical_snapshot(source, "Swing")
    expected = build_indicator_frame(
        source, "swing", common_as_of=pd.Timestamp(source["date"].max()).date()
    ).tail(100)
    actual = snapshot["data"]
    pd.testing.assert_series_equal(
        actual["RSI_9"].reset_index(drop=True),
        expected["rulebook_rsi"].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        actual["ADX_14"].reset_index(drop=True),
        expected["rulebook_adx_14"].reset_index(drop=True),
        check_names=False,
    )
    assert not any(column.startswith("rulebook_") for column in actual.columns)


def test_horizon_snapshot_reports_existing_eight_plus_alligator():
    snapshot = build_horizon_technical_snapshot(make_daily_ohlcv(), "Swing")
    assert [row["indicator"] for row in snapshot["report"]] == [
        "MA", "MA cross", "Alligator", "RSI", "Stochastic",
        "ADX", "OBV", "ATR", "Bollinger",
    ]
```

Compare raw MA, Alligator, and ATR values through
`build_horizon_native_frame()` before the UI boundary. Also assert Swing
aliases are `EMA_5`, `EMA_13`, and `RSI_9`; Mid-term aliases are `SMA_8`,
`SMA_21`, and `RSI_14`. Verify OHLC, MA, Alligator, ATR, and Bollinger display
columns divide raw values by 1000 exactly once.

- [x] **Step 2: Run tests and confirm red state**

Run:

```bash
python -m unittest tests.test_technical_horizon tests.test_technical_snapshot -v
```

Expected: failure because `build_horizon_technical_snapshot()` does not exist.

- [x] **Step 3: Enrich one native frame with Technical-only indicators**

Add aliases and calculate MA crosses from the exact schema-5 MA series. Do not
retain a duplicate raw frame in the returned snapshot.

```python
working, rulebook = build_horizon_native_frame(source, horizon)
working, stochastic_trend = calculate_stochastic(working)
working["OBV"] = calculate_obv(working)
working = working.join(calculate_bollinger(working, period=20, std_mult=2))

fast, slow = rulebook.ma_pair
ma_fast_col = f"{rulebook.ma_kind}_{fast}"
ma_slow_col = f"{rulebook.ma_kind}_{slow}"
rsi_col = f"RSI_{rulebook.rsi_period}"
working[ma_fast_col] = working["rulebook_ma_fast"]
working[ma_slow_col] = working["rulebook_ma_slow"]
working[rsi_col] = working["rulebook_rsi"]
working["ADX_14"] = working["rulebook_adx_14"]
working["DMP_14"] = working["rulebook_plus_di_14"]
working["DMN_14"] = working["rulebook_minus_di_14"]
working["ALLIGATOR_JAW"] = working["rulebook_alligator_jaw"]
working["ALLIGATOR_TEETH"] = working["rulebook_alligator_teeth"]
working["ALLIGATOR_LIPS"] = working["rulebook_alligator_lips"]
cross_col = f"cross_{fast}_{slow}"
working[cross_col] = 0
working.loc[series_upcross(working[ma_fast_col], working[ma_slow_col]), cross_col] = 1
working.loc[series_upcross(working[ma_slow_col], working[ma_fast_col]), cross_col] = -1
```

- [x] **Step 4: Build report, signals, and UI-scaled frame**

Map latest `rulebook_alligator_point` values `1/2/3` to `Down/Sideways/Up` and `NaN` to `Unknown`. Give Alligator dimension `trend_direction` and role `gate`; do not add it to shared legacy scoring metadata. Build existing eight records with horizon-specific columns, then insert Alligator after MA Cross.

```python
alligator_trend = {1.0: "Down", 2.0: "Sideways", 3.0: "Up"}.get(
    _latest_numeric(working, "rulebook_alligator_point"), "Unknown"
)
alligator_record = {
    "indicator": "Alligator",
    "dimension": "trend_direction",
    "role": "gate",
    "value": (
        f"Lips: {_price(lips)} - Teeth: {_price(teeth)} - Jaw: {_price(jaw)}"
    ),
    "trend": alligator_trend,
}
signals = [
    [index, record["indicator"], record["value"], record["trend"]]
    for index, record in enumerate(report)
]
```

Before returning `data`, apply `prepare_price_for_output(..., PRICE_OUTPUT_UI)`
to OHLC plus MA, Alligator, ATR, and Bollinger price columns. Do not scale RSI,
Stochastic, ADX/DI, OBV, bandwidth, percent-B, volume, or cross/event columns.
Drop every internal `rulebook_*` column after its user-facing alias/report value
has been built. This prevents the Raw Data view from exposing raw-price helper
columns or excluded Backtest gates.

- [x] **Step 5: Prove legacy snapshot isolation**

Keep the existing test assertion unchanged:

```python
snapshot = build_technical_snapshot(make_ohlcv(), 5, 10)
assert len(snapshot["report"]) == 8
assert "Alligator" not in {row["indicator"] for row in snapshot["report"]}
```

This ensures Analyze/API output is not silently altered.

- [x] **Step 6: Run Task 2 tests**

Run:

```bash
python -m unittest tests.test_technical_horizon tests.test_technical_snapshot -v
```

Expected: all tests pass, including exact schema-5 parity and legacy eight-indicator isolation.

---

### Task 3: Sidebar-Free Technical Analysis UI

**Files:**
- Modify: `app/pages/technical_visualization.py`
- Modify: `tests/test_technical_visualization_ui.py`

**Interfaces:**
- Consumes: `fetch_raw_technical_history()`, `TECHNICAL_SOURCE_ROW_LIMIT`, and `build_horizon_technical_snapshot()`
- Extends: `get_indicator_chart_spec(indicator, short_ma, long_ma, ma_kind="SMA")`
- Extends: `_add_selected_indicator(..., ma_kind="SMA")`

- [x] **Step 1: Write failing UI contract tests**

Update constants and source/AppTest assertions.

```python
def test_technical_page_has_only_main_ticker_and_horizon_analysis_inputs():
    source = inspect.getsource(technical_visualization.technical_analysis_page)
    assert "st.sidebar" not in source
    assert 'st.text_input("Ticker"' in source
    assert 'st.selectbox("Horizon", ("Swing", "Mid-term")' in source
    assert "Max Time (Lookback)" not in source
    assert "MA Cross Pair" not in source


def test_overview_has_existing_indicators_plus_alligator():
    assert TECHNICAL_INDICATOR_TABS == (
        "Overview", "MA", "MA Cross", "Alligator", "RSI", "Stochastic",
        "ADX", "OBV", "ATR", "Bollinger Bands",
    )
```

Add chart test expecting Alligator line names `Alligator Lips`, `Alligator Teeth`, and `Alligator Jaw`.

- [x] **Step 2: Run tests and confirm red state**

Run:

```bash
python -m unittest tests.test_technical_visualization_ui -v
```

Expected: failures for sidebar controls, missing Alligator tab/spec, and missing horizon inputs.

- [x] **Step 3: Move analysis controls into main page**

Render one main row. Clear remains a utility action, not an analysis parameter.

```python
ticker_column, horizon_column, analyze_column, clear_column = st.columns((3, 2, 1, 1))
with ticker_column:
    ticker = st.text_input("Ticker", value="FPT").strip().upper()
with horizon_column:
    horizon_label = st.selectbox("Horizon", ("Swing", "Mid-term"))
with analyze_column:
    analyze = st.button("Analyze", icon=":material/query_stats:")
with clear_column:
    clear = utility_icon_button(
        "clear_cache",
        help="Clear Technical Analyze cached data",
        key="technical_clear_cache",
    )
```

Cache identity becomes `(ticker, horizon_label, 100)`. On Analyze, reject blank ticker, fetch the horizon-specific source limit, build one horizon snapshot, and save it. If fetch/build fails or returns no native bars, clear prior result and show one safe warning.

- [x] **Step 4: Make chart selection result-only and horizon-aware**

Create `Show one indicator` only after the current snapshot matches the current input identity. Read `ma_kind`, `short_ma`, and `long_ma` from `snapshot["profile"]`; remove all MA-pair input logic.

```python
chart_indicator = st.selectbox(
    "Show one indicator",
    options=TECHNICAL_CHART_OPTIONS,
    index=0,
    key="technical_result_indicator",
)
profile = snapshot["profile"]
short_ma = profile["short_ma"]
long_ma = profile["long_ma"]
ma_kind = profile["ma_kind"]
spec = get_indicator_chart_spec(
    chart_indicator, short_ma, long_ma, ma_kind=ma_kind
)
```

- [x] **Step 5: Add Alligator chart and detail tab**

`get_indicator_chart_spec("Alligator", ...)` returns an overlay using `ALLIGATOR_LIPS`, `ALLIGATOR_TEETH`, and `ALLIGATOR_JAW`. Add three traces on the price row with distinct colors. Extend `_INDICATOR_RULES` and `_report_name()` while keeping Bollinger alias behavior.

```python
if indicator == "Alligator":
    for column, name, color in (
        ("ALLIGATOR_LIPS", "Alligator Lips", "green"),
        ("ALLIGATOR_TEETH", "Alligator Teeth", "red"),
        ("ALLIGATOR_JAW", "Alligator Jaw", "blue"),
    ):
        fig.add_trace(
            go.Scatter(x=df["date"], y=df[column], mode="lines", name=name,
                       line=dict(color=color, width=1)),
            row=1,
            col=1,
        )
    return
```

Only Swing receives calendar-date range breaks. Mid-term already contains completed Friday bars and must not synthesize daily breaks.

- [x] **Step 6: Run UI and integrated Technical tests**

Run:

```bash
python -m unittest tests.test_technical_visualization_ui tests.test_technical_horizon tests.test_technical_snapshot tests.test_main_entrypoint -v
```

Expected: all tests pass; main navigation still clears only `tech_*` state when leaving Technical Analyze.

---

### Task 4: Full Verification and Documentation

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `ai-context/architecture.md`

**Interfaces:**
- Consumes completed Tasks 1–3.
- Produces final verification evidence and an exact stopping point.

- [x] **Step 1: Run focused Technical regression**

Run in Docker:

```bash
python -m unittest discover -s tests -p 'test_technical*.py' -v
```

Expected: all Technical tests pass with no exceptions.

- [x] **Step 2: Run affected shared-consumer regression**

Run in Docker:

```bash
python -m unittest tests.test_common_functions tests.test_analyze_snapshot_reuse tests.test_analyze_trend_classification tests.test_historical_technical_context tests.test_api_routes tests.test_main_entrypoint -v
```

Expected: Analyze/API/navigation behavior remains green.

- [x] **Step 3: Compile changed modules**

Run:

```bash
python -m compileall -q commons/technical_analysis.py commons/technical_horizon.py pages/technical_visualization.py
```

Expected: exit code 0 and no output.

- [x] **Step 4: Perform implementation self-review**

Apply `ai-skills/skill-implementation-review.md` and verify:

- raw BIGINT prices cross exactly one UI scaling boundary;
- no SQL f-string or concatenated dynamic value exists;
- raw connection always closes;
- incomplete W-FRI bar cannot appear;
- Alligator uses schema-5 causal shifted series;
- shared legacy snapshot remains eight indicators;
- no sidebar input or hidden user-tunable horizon parameter remains;
- no dependency, protected query, Backtest rulebook, or Git change exists.

- [x] **Step 5: Update project state**

Mark design and Tasks 1–4 complete in `FOCUS.md` and
`ai-context/current-status.md`. Update `ai-context/architecture.md` so Technical
Analysis ownership states: main-page Ticker/Horizon input, schema-5 horizon
adapter, fixed 100-bar output cap, existing eight indicators plus Alligator,
and unchanged Analyze/API legacy snapshot.

- [x] **Step 6: Final handoff**

Report exact passing test counts, compilation result, files changed, and any
remaining limitation. Do not claim completion if any required test or parity
check fails.
