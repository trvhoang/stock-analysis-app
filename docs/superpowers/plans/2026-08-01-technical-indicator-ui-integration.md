# Technical Indicator UI Integration Implementation Plan

**Status: COMPLETE — 2026-08-02**

> **For agentic workers:** Use the executing-plans workflow to implement this plan task-by-task with a review checkpoint after each task.

**Goal:** Surface the implemented technical indicators, dimension-aware scoring, and ADX gating consistently on the Technical Analyze Page and Analyze Page without introducing repeated database reads or indicator calculations.

**Architecture:** Build one shared, pure-Python technical snapshot from a fetched OHLCV DataFrame. The snapshot contains the enriched chart DataFrame, canonical indicator signals for the existing scorer, and display-ready report records. Technical Analyze consumes the snapshot from session state; Analyze and API paths consume the same report/signals from the existing analysis result so current technical advice and Final Advice remain the authorities.

**Tech Stack:** Python 3.12, Streamlit, pandas, Plotly, existing unittest suite, PostgreSQL access through existing project helpers.

## Global Constraints

- Do not modify `app/common_queries.py`, delta CTEs, database schema, Docker, credentials, or BIGINT storage/scaling.
- Do not add dependencies or remove `pandas_ta` in this task.
- Do not use or modify `IMPLEMENTED.md`.
- Keep the existing technical advice thresholds, score return shape, ADX gate contract, and Final Advice matrix.
- ADX remains a non-voting gate: `<20` halves only `trend_direction`; `>=20` keeps full weight; missing/Unknown/NaN skips gating.
- Keep candlestick and volume visible; render at most one additional selected indicator visualization.
- The eight displayed indicators are MA, MA cross, RSI, Stochastic, ADX, OBV, ATR, and Bollinger Bands. Ichimoku is removed from placeholders and implementation surface.
- All tests use deterministic fixtures and must run without a live database unless a focused integration probe is explicitly required.

## Planned Files

- Modify `app/commons/technical_analysis.py`: add the shared snapshot builder and remove the unused Ichimoku placeholder function.
- Modify `app/commons/common_functions.py`: consume the snapshot for current technical scoring and expose display-ready indicator records without breaking existing callers.
- Modify `app/pages/technical_visualization.py`: add Overview/detail tabs, single-indicator chart selection, cached snapshot reuse, and no Ichimoku placeholder.
- Modify `app/pages/analyze_visualization.py`: render all indicator results in Ticker Analyze → Technical Report and reuse the shared technical result for advice/final advice.
- Modify `tests/test_technical_analysis_indicators.py` or add `tests/test_technical_snapshot.py`: cover snapshot contents, missing data, and one-calculation behavior at the pure-function boundary.
- Modify/add page-adjacent tests only where existing test conventions support it; do not require Streamlit rendering tests for pure scoring behavior.
- Update `FOCUS.md` and `ai-context/current-status.md` after implementation and verification. Do not update `IMPLEMENTED.md`.

## Data Contract

Add a pure helper with a stable contract:

```python
build_technical_snapshot(df, short_ma, long_ma) -> dict
```

The returned dictionary contains:

- `data`: the enriched OHLCV DataFrame used by the chart; calculations happen once.
- `signals`: existing scorer-compatible records `[index, canonical_name, display_value, trend]` for all available voting indicators; ADX is represented for display but excluded from voting by existing metadata.
- `report`: one display record for each of the eight indicators, including `indicator`, `dimension`, `role`, `value`, and `trend`; unavailable values use `Unknown`/`N/A` rather than failing the page.
- `adx_value`: the single latest numeric ADX value or `None`.

The helper must calculate ATR, Bollinger, OBV, ADX, MA, MA cross, RSI, and Stochastic once per snapshot. It must reuse the already calculated ADX value instead of calling a second full ADX calculation merely to read the latest value.

### Task 1: Build the Shared Snapshot and Remove Ichimoku

**Files:**
- Modify: `app/commons/technical_analysis.py`
- Test: `tests/test_technical_snapshot.py`

**Interfaces:**
- Consumes: OHLCV DataFrame with `date`, `open`, `high`, `low`, `close`, and `volume`; selected MA periods.
- Produces: the `build_technical_snapshot()` dictionary described above.

- [x] Write failing tests for all eight report records, dimension/role mapping, scorer-compatible signals, ADX display-but-no-vote behavior, and missing/short data returning `Unknown`/`N/A` without raising.
- [x] Run the focused RED test in the project container and confirm failure because `build_technical_snapshot` does not exist.
- [x] Implement the smallest helper by composing the existing indicator calculators and trend classifiers. Keep indicator formulas unchanged.
- [x] Remove `calculate_ichimoku()` from the technical-analysis implementation surface.
- [x] Run the focused snapshot tests and verify one enriched DataFrame is returned with no duplicate ADX calculation inside the helper.
- [x] Run the existing indicator, grouping, scoring, and ADX tests to confirm no regression.

### Task 2: Technical Analyze Page UI

**Files:**
- Modify: `app/pages/technical_visualization.py`
- Test: focused pure snapshot tests from Task 1; manual Streamlit smoke check with PostgreSQL-backed data.

**Interfaces:**
- Consumes: `build_technical_snapshot()` and the existing `fetch_data()` cache.
- Produces: cached snapshot, default-open Overview, one detail tab per indicator, and one selected indicator visualization.

- [x] Add a session-state snapshot key scoped by ticker, timeframe, lookback, and selected MA pair. Keep raw OHLCV caching separate so changing the chart selection never refetches data.
- [x] Replace the current hardcoded/placeholder indicator layout with tabs ordered `Overview`, `MA`, `MA Cross`, `RSI`, `Stochastic`, `ADX`, `OBV`, `ATR`, `Bollinger Bands`; Overview is first so Streamlit opens it by default.
- [x] Make the chart selector a single `selectbox`; keep candlestick and volume rows permanently visible and render only the selected indicator as an overlay or additional panel.
- [x] Render MA and MA cross on the price row; render RSI, Stochastic, ADX, OBV, ATR, or Bollinger in one additional panel. Do not render multiple indicator panels simultaneously.
- [x] Populate Overview and detail tabs from the cached snapshot, not by recalculating indicators inside tab bodies. Show final trend, latest value(s), dimension, voting/gate role, and relevant existing thresholds.
- [x] Show ADX gate status separately from the score: `ADX < 20 → trend direction × 0.5`, `ADX >= 20 → full trend weight`, unavailable ADX → `Gate not applied`.
- [x] Preserve existing clear-cache behavior and show safe `Unknown`/insufficient-history messages.
- [x] Remove the Ichimoku tab and placeholder text.
- [x] Verify automated UI contracts, snapshot reuse boundaries, short-data handling, module compilation, and Streamlit runtime health. Initial browser automation was unavailable; later headless Chrome smoke covered rendered MA and RSI states.

### Task 3: Analyze Page and API/Shared Workflow

**Files:**
- Modify: `app/commons/common_functions.py`
- Modify: `app/pages/analyze_visualization.py`
- Test: `tests/test_common_functions.py`, `tests/test_analyze_trend_classification.py`, and a focused technical-report test where supported.

**Interfaces:**
- Consumes: the shared snapshot from Task 1.
- Produces: current technical report records, expanded scorer input, existing technical advice text/trend/score, and Final Advice using the existing matrix.

- [x] Change `analyze_ticker()` to build one snapshot for its existing technical timeframe and MA pair.
- [x] Preserve existing result keys and advice thresholds; add only display-safe technical report/gate data needed by the UI and shared API workflow.
- [x] Expand the scorer input with the new voting indicators while leaving ADX excluded by existing metadata and applying the existing gate once.
- [x] Update `synthesize_all_advice()` to reuse technical records already present in `stats_data`; retain a compatibility fallback for existing callers/tests that provide only the legacy stats dictionary.
- [x] Replace the separate Technical Report fetch/calculation in `analyze_visualization.py` with the report generated by `analyze_ticker()`.
- [x] Render all eight indicators in the Technical Report, including ADX's gate role and status, without changing the existing Technical Advice message contract.
- [x] Ensure Final Advice receives the expanded technical trend key and continues using `generate_final_advice()` unchanged.
- [x] Keep Portfolio Analyze's output columns and parallel worker limit unchanged; it now reuses the expanded technical score through `analyze_portfolio_ticker()`.
- [x] Test statistical advice, technical advice, ADX boundary/missing behavior, Final Advice matrix compatibility, and current-path duplicate-fetch protection.

### Task 4: Historical Path Performance Protection

**Files:**
- Modify: `app/pages/analyze_visualization.py` only if needed to preserve historical behavior and avoid duplicate work.
- Test: existing Analyze/historical scoring tests plus a deterministic performance-oriented helper test if a pure helper is introduced.

- [x] Keep the existing historical technical-context score behavior unchanged unless a safe precomputed/as-of implementation is verified; the user-requested expansion applies to the current Technical Report and current Technical Advice.
- [x] Do not call new indicator trend classifiers on every historical `sub_df` prefix. If historical expansion is later required, first create a full-series precomputed trend table and use date-index/as-of lookups.
- [x] Preserve the current binary-search date alignment and ADX missing-data behavior.
- [x] Confirm the new current-analysis snapshot does not trigger another unbounded historical query.
- [x] Run a modest synthetic benchmark proving dropdown selection and current snapshot reuse are constant with respect to tab count, and that no per-event new-indicator loop is introduced.
- [x] Replace historical event-prefix rescans with one behavior-preserving as-of score table and verify parity against the existing prefix implementation.

### Task 5: Verification and Documentation

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Do not modify: `IMPLEMENTED.md`

- [x] Run focused tests for snapshot/scoring behavior.
- [x] Run the full suite with `python -m unittest discover -s tests -p "test_*.py" -v` and record the exact pass count. Docker result: 128/128 passed after splitting the two assertions that previously shared one line in `tests/test_validation.py:67`.
- [x] Run `git diff --check` and inspect the diff for accidental SQL, dependency, scaling, Docker, or API-contract changes.
- [x] Perform a PostgreSQL-backed manual smoke check of both pages: real MHP data rendered Analyze and Technical Analyze with all eight chart selections and zero AppTest exceptions/errors/warnings; unknown ticker `ZZZ` produced the expected safe warning; direct PostgreSQL snapshot smoke returned 8 reports and a non-empty analysis result.
- [x] Record performance observations and any remaining live-data validation gap in `FOCUS.md` and `current-status.md`.
- [x] Stop after this phase and wait for user review before unrelated indicator work or pandas-ta debt work.

Verification note: real PostgreSQL smoke fetched MHP data, built all eight
technical reports, and returned a non-empty analysis result. The malformed
validation test assertion was corrected and the full Docker suite now passes
128/128. Streamlit AppTest
rendered Analyze and the initial Technical Analyze page without app errors;
the string-valued MA pair widget now supports rerunning the page, and all eight
chart-selector options completed with zero exceptions, errors, or warnings. A
report-name alias regression found during this smoke was fixed and covered by a
focused test. Live API smoke returned HTTP 200 after replacing the unsupported
Plotly 5.20 Candlestick `hovertemplate` with supported `text`/`hoverinfo`
properties.
The actual export path returned 2,497 rows for one 10-year REE request in 27 ms;
eight sequential 5-year requests returned 9,968 rows in 170 ms. This was a
performance simulation only; multi-ticker query support was not added. The
existing `(ticker, date)` index is used, and no pagination or query guard change
was needed for these ranges.
Headless Chrome visual smoke inspected Technical Analyze MA and RSI states:
candlestick, volume, k VND labels, controls, and indicator tabs rendered with no
visible error state. AppTest covers all eight selector options. The historical
SQL query remains full-ticker by design; score processing is now linear in
history, and any date bound still requires a separately verified as-of design.
