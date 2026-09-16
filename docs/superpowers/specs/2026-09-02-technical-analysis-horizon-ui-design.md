# Technical Analysis Horizon UI Design

**Date:** 2026-09-02  
**Status:** Implemented and verified

## Goal

Simplify Technical Analysis to two required inputs: ticker and horizon. One
Analyze action builds a horizon-consistent technical snapshot while preserving
the current raw-data view, candlestick/volume chart, indicator chart selection,
overview, and indicator detail tabs.

## Scope

- Remove all Technical Analysis controls from the sidebar.
- Render Ticker, Horizon, Analyze, and the existing clear-cache utility in the
  main page.
- Horizon choices are `Swing` and `Mid-term`.
- Use up to 100 completed native bars; users cannot change the lookback cap.
- Preserve existing result presentation and add Alligator to the chart and
  detail views.
- Do not change Analyze page, API behavior, Backtest rulebooks, SQL schema,
  BIGINT storage, dependencies, or other pages.

## Horizon Contracts

### Swing

- Native bars: daily.
- MA: EMA(5/13).
- RSI: exact causal RSI(9).
- Alligator: causal SMMA periods jaw/teeth/lips `8/5/3`, shifted `5/3/2`.
- ADX and ATR: exact SMA-seeded Wilder(14).

### Mid-term

- Native bars: completed `W-FRI` only; an incomplete current week is excluded.
- MA: SMA(8/21).
- RSI: exact causal RSI(14).
- Alligator: causal SMMA periods jaw/teeth/lips `13/8/5`, shifted `8/5/3`.
- ADX and ATR: exact SMA-seeded Wilder(14).

Stochastic(10/3/3), OBV, and Bollinger(20, 2) retain existing Technical
Analysis formulas and run on the same horizon-native bars. Existing MA and MA
Cross results remain. Alligator is the only new indicator; relative volume and
other Backtest gates are not added.

## Architecture

Add a Technical-Analysis-owned horizon adapter. It will reuse immutable
Backtest schema-5 configuration and indicator-frame functions for MA,
Alligator, RSI, ADX, and ATR. It will then enrich that same native frame with
the existing Stochastic, OBV, and Bollinger calculations.

The existing `build_technical_snapshot()` contract remains unchanged for
Analyze/API consumers. A separate horizon snapshot entry point prevents this UI
change from altering their behavior.

Data remains fetched through a parameterized, ticker-bounded query and an
`engine.raw_connection()`. Prices remain raw through horizon construction and
are divided by 1000 only at the Technical UI output boundary.

## UI Flow

1. User enters ticker and selects Swing or Mid-term in the main page.
2. Analyze validates and uppercases ticker, fetches required daily source rows,
   builds up to the latest 100 native bars, and caches the snapshot by ticker,
   horizon, and fixed-lookback contract.
3. Before a successful analysis, no result-navigation control is shown.
4. After success, the page retains:
   - raw-data expander;
   - candlestick and volume chart;
   - one result-only chart-indicator selector;
   - Overview plus indicator detail tabs.
5. Alligator becomes an overlay chart and a detail tab alongside existing
   indicators.

The result-only chart selector changes presentation only; it never triggers a
new data fetch or indicator calculation.

## State and Errors

- Cache keys include ticker, horizon, and fixed lookback so stale controls
  cannot display a prior snapshot.
- Changing ticker or horizon hides old results until Analyze succeeds.
- Empty/invalid ticker and missing history show a clear warning and retain no
  stale result.
- Fewer than 100 available native bars remain usable. Indicators without enough
  warm-up data show `Unknown`/`N/A`; no incomplete week is substituted.
- Analysis fails safely only when no native bar can be formed.
- Clear cache removes only `tech_*` state.

## Verification

- UI test proves no `st.sidebar` input area exists and only Ticker/Horizon are
  analysis inputs.
- Horizon contract tests prove fixed mappings and the 100-bar maximum.
- Mid-term fixture proves incomplete current week is excluded and dates are
  completed Fridays.
- Parity tests compare MA, Alligator, RSI, ADX, and ATR columns with Backtest
  schema-5 output for identical source data and cutoff.
- Snapshot tests prove Stochastic, OBV, Bollinger, and Alligator appear in
  overview/details and Alligator chart traces render.
- Regression tests prove legacy `build_technical_snapshot()` and Analyze/API
  callers remain unchanged.

## Known Boundary

This page reports technical evidence only. Horizon selection does not run a
Backtest, select a rulebook candidate, or provide automated trading advice.
