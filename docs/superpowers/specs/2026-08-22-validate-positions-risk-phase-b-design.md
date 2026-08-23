# Validate Positions Risk — Phase B Design

## Status

Approved design, 2026-08-22. This document supersedes only the deferred Phase B
section of `2026-08-16-validate-positions-risk-and-trade-rows-design.md`.
Phase A remains complete. Implementation requires a separate approved Phase B
plan.

## Purpose and boundary

Validate Positions gives manual, after-session risk advice for selected OPEN
positions. It never submits orders, closes a position, adds a SELL reason, or
changes the existing ATR/holding SELL monitor.

Only OPEN schema-4 saved-set positions and OPEN positions without a saved set
are selectable. Pre-schema-4/V2 saved-set records remain historical P&L data:
they stay `N/A` in Current Positions and have no Validate Positions UI,
evaluation, artifact read, migration, or compatibility path. Historical files
are retained; this is not a data-deletion task.

## Run contract

- A run selects one through five eligible OPEN positions, processes them in
  selection order, and continues after a per-position failure.
- Inputs are persisted database bars only. There is no current-date,
  intraday, or real-time calculation.
- All assessable inputs must share one latest completed trading-bar date. A
  ticker or required VNINDEX series that does not match that date fails its
  own row; no calculation mixes dates.
- Successful assessed rows share the one run header `As of: DD/MM/YYYY`.
  When no row can be assessed, no misleading as-of date is shown.
- Cached rulebook frames use `(ticker, horizon, shared_as_of_date)`. Cache
  reuse never changes sequential processing, the five-position cap, or error
  isolation.
- Every numeric calculation uses raw BIGINT prices. Conversion to k-VND is UI
  display only.

## Evaluation routing

### Schema-4 saved-set position

Use the one frozen schema-4 reference: its horizon, selected gates, preferred
treatment, stored entry match level, and saved signal date. Rebuild current
facts from the frozen rulebook; do not load a current artifact or any legacy
artifact. A themed frozen treatment requires the matching current VNINDEX
facts.

T+0, T+1, and T+2 do not trigger evaluation. T excludes the signal day: the
next completed ticker session is T+1. Those rows return `T+3 required`, write
nothing, and retain their existing BUY risk text. At T+3 or later, evaluate
the saved horizon.

### No-signal position

Evaluate fresh Backtest-owned, no-theme facts for both Swing and Mid-term. For
each horizon, inspect all four current V3 gates:

1. `rulebook_adx_gate`
2. `rulebook_joint_trend_pass`
3. `rulebook_rsi_upcross`
4. `rulebook_volume_gate`

The displayed suggestion contains both horizon scores; the risk level is the
worse of the two. This is not a V2 fallback.

## Score formulas

All component values and the final score are clamped to `[0, 100]`. Round the
final score to two decimals before assigning its label, then render it to one
decimal place in the persisted display text.

### Signal-backed position

Let `E` be actual BUY price, `S` frozen stop loss, `C` current raw close, `A`
current raw ATR, `B` native holding bars, and `M` frozen maximum holding bars.
All are positive raw values and `E > S` is required.

```text
stop_proximity = clamp(100 * (E - C) / (E - S))
atr_exposure  = clamp(100 * A / (E - S))
holding       = clamp(100 * B / M)
base          = 0.55 * stop_proximity + 0.25 * atr_exposure + 0.20 * holding
```

At or below the stop loss, the final score is `100`. A close at or above BUY
produces zero stop proximity.

At T+3 or later, calculate:

```text
strength_drop = clamp(saved_match_level - current_match_level)
elapsed_time  = clamp(100 * completed_sessions_after_signal / denominator)
denominator   = 22 for Swing; 80 for Mid-term (16 weeks × 5 sessions)
score         = clamp(base + 0.30 * max(strength_drop, elapsed_time))
```

`current_match_level` uses the frozen selected gates and frozen preferred
treatment, including VNINDEX only for a themed reference. No time component
exists before T+3 because no evaluation is triggered then.

### No-signal position

For each horizon:

```text
score = 100 - (100 * passed_current_gates / 4)
```

The position's overall level is its worse horizon score. The BUY risk text
always shows both per-horizon suggestions.

## Labels and persistence

| Score | Label |
|---:|---|
| `0 <= score <= 40` | `low` |
| `40 < score <= 60` | `medium` |
| `60 < score <= 80` | `high` |
| `80 < score <= 100` | `very` |

Persist exactly one optional position field, `risk_suggestion_text`. It is a
display string only: no as-of date, score components, or history is stored.

- Successful assessment overwrites it with one line per assessed horizon,
  `<Horizon>: <score with one decimal>% - <label>`; a no-signal assessment
  stores separate Swing and Mid-term lines.
- Missing or invalid required risk input overwrites it with `Unavailable`.
- T+3 skip writes nothing.
- Editing BUY price or BUY date, or reopening a CLOSED position, clears it to
  `N/A`. Editing quantity preserves it. Closing preserves a non-`N/A` value,
  which Current Positions renders struck through.

## Validate Positions result surface

The result table is:

```text
Ticker | Evaluation | Risk suggestion | Result
```

`Evaluation` is the saved horizon or `Swing + Mid-term`. Exact Result values:

- `Updated`
- `Unavailable — risk score missing/invalid.`
- `Failed — assess failed.`
- `T+3 required`

Risk is informational only. Existing ATR/holding SELL advice remains the only
SELL advice.

## Unavailable versus failure

Required missing or invalid price, ATR, stop, holding, saved entry context,
signal date, current gate fact, theme fact, or raw history produces
`Unavailable — risk score missing/invalid.`. It is not a crash and does not
block later rows. Unexpected replay, storage, or database errors produce
`Failed — assess failed.` and also do not block later rows.

## Required implementation evidence

The implementation plan must require RED/GREEN unit and AppTest coverage for:

- all formula components, clamping, T+3 boundary, score bands, two-decimal
  classification, and one-decimal suggestion rendering;
- schema-4 saved routing, no-signal two-horizon routing, legacy non-selection,
  and no artifact reads;
- shared-latest-bar enforcement, themed VNINDEX requirement, cache reuse,
  five-position cap, selection order, and continue-on-error;
- exact result text, persistence overwrite/skip/invalidations, and CLOSED
  strike-through rendering;
- raw BIGINT-only math and no risk-derived SELL reason.

## Out of scope

- Intraday/realtime data, market-clock guessing, and current-date assessment.
- Position-risk history, orders, auto-SELL, or changes to ATR exits/SELL rules.
- Legacy artifact reading, conversion, migration, compatibility, or deletion.
