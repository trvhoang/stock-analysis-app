# Backtest Compact Strategy Revamp Design

**Status:** Design decisions approved; specification review pending.

## Goal

Make the Backtest engine produce trustworthy per-ticker signal sets when a
pre-registered compact strategy qualifies, while correctly returning `null`
when none does. Resolve the opaque 270-combination search, prove trade-pair
correctness, and prevent duplicate rolling-window events from inflating
certification inputs.

## Evidence and Problem Statement

VCB has valid-looking raw score activity: the production 15-year Mid-term
probe found 50 no-theme and 37 VN-Index `AND` crossings for its all-dimension
baseline. The fresh themed job nevertheless persisted an empty certification
document. A separate simulation also finds candidate entries, but it is not a
production oracle: its current trace still uses one-bar Mid-term timeouts and
some Swing exits earlier than the engine's native hold contract.

The next design must therefore prove production trade execution and
certification boundaries before changing values. It must not tune to VCB;
VCB is a canary inside a frozen multi-ticker universe.

## Scope

Included:

- Database-only historical-price audit and frozen eight-ticker universe.
- Causal Williams Alligator indicator for Backtest-only strategy evaluation.
- Three fixed compact strategies, one hard ADX eligibility rule, and one
  actual-trade event per signal date.
- Explicit statistical gate semantics and per-ticker full-history
  certification using at least 30 unique completed trades.
- Calibration/holdout evidence, production-versus-golden trade traces, and
  focused regression tests.

Excluded:

- External corporate-action, adjusted-price, order-flow, or market-cap data.
- Changes to BIGINT storage, SQL delta CTEs, Docker, credentials, dependencies,
  or automated trading.
- A guarantee that every ticker produces a signal set.

## Non-Negotiable Contracts

- Prices remain raw BIGINT in storage and engine math. UI conversion stays
  outside SQL and engine calculations.
- The price audit uses only `trading_data`. It can identify suspicious
  discontinuities but cannot prove historical adjustment. Any indeterminate
  ticker is excluded, not warning-labelled and retained.
- Swing stays daily: entry is the next daily-bar open; SL/TP first become
  eligible at entry plus three daily bars; timeout uses the existing inclusive
  Swing hold rule.
- Mid-term stays weekly end-to-end: indicators, ATR, signal, entry, exit, and
  timeout all use weekly OHLCV; exits first become eligible on the next weekly
  bar; timeout is inclusive at bar 16.
- The public variants remain no-theme and VN-Index `AND`. Theme confirmation
  remains an additional causal eligibility condition, never a short signal.
- All strategies are long-only. Every completed event is one implicit equal
  volume BUY and SELL pair.

## Frozen Universe and Time Split

The audit freezes exactly eight clean tickers before any strategy measurement:

1. VCB is always included as the canary.
2. From remaining clean tickers with complete coverage from 2011-08-09 through
   2026-08-09, choose the two highest and two lowest total-return tickers using
   only data through 2020-12-31.
3. Choose the three tickers whose same pre-2021 total return is closest to the
   eligible-universe median.
4. Ties sort by ticker symbol. The selection query, selected names, source-row
   counts, and audit results are persisted in the evidence report before any
   strategy result is viewed.

The requested date bounds are calendar bounds. Full terminal coverage means a
ticker reaches the latest in-range trading session present in the current
database, rather than requiring a row on a weekend or holiday end date.

The pre-2021 period is `2011-08-09` through `2020-12-31`; the holdout is
`2021-01-01` through `2026-08-09`. The split evaluates rule stability. Final
per-ticker certification uses the complete 15-year unique-trade sequence only
after rules are frozen; its artifact must disclose that full-history scope.

### Recorded Implementation-Plan Override

The approved implementation plan controls current diagnostic evidence where it
conflicts with this original design: calibration ends `2020-12-31`, holdout
starts `2021-08-09`, and `2021-01-01` through `2021-08-08` is deliberately
excluded from partition reports. Full-history certification remains unchanged.

## Database-Only Price Audit

For every universe candidate, inspect raw OHLCV continuity, duplicate dates,
positive values, OHLC ordering, missing-session gaps, and factor-like close
discontinuities. A factor-like discontinuity is a close-to-previous-close move
of at least 15% on an established ticker; its date, price ratio, volume ratio,
and intraday range are recorded. Because current database columns contain no
corporate-action metadata, the audit cannot explain such a move. Any candidate
with one or more factor-like discontinuities is indeterminate and excluded.

This deliberately permits false-clean histories (for example, a fully
back-adjusted series with no visible discontinuity). The report must state this
ceiling; it must not claim adjusted-price proof.

## Compact Strategy Rulebook

Each strategy applies independently to Swing and Mid-term frames. It has one
stable identity and no generated indicator subsets, threshold grid, or
soft/hard ADX variant.

| ID | Indicators | Entry score | Trend-strength gate |
|---|---|---:|---|
| `ma_cross_rsi_obv` | MA Cross, RSI, OBV | upward crossing through 60 | ADX >= 20 |
| `alligator_rsi_obv` | Williams Alligator, RSI, OBV | upward crossing through 60 | ADX >= 20 |
| `consensus_rsi_obv` | MA Cross, Williams Alligator, RSI, OBV | upward crossing through 60 | ADX >= 20 |

For each strategy, map existing causal trend labels through the existing 0--4
score mapping, take the unweighted mean of only its listed indicators, and
multiply by 25 to obtain a 0--100 score. ATR is removed from entry scoring; it
remains the sole existing ATR(14) SL/TP risk input. OBV remains the existing
causal OBV trend classifier.

Williams Alligator is Backtest-only so existing Technical Analyze/API scoring
does not change. It uses close-price SMMAs seeded by the first simple average:

```
smma[t] = (smma[t - 1] * (period - 1) + close[t]) / period
```

The Jaw, Teeth, and Lips periods are 13, 8, and 5. At bar `t`, its causal
values are `jaw_smma[t - 8]`, `teeth_smma[t - 5]`, and `lips_smma[t - 3]`.
The label is `Up` only when `Lips > Teeth > Jaw`, `Down` only when the reverse
holds, and `Sideways` otherwise. No future-shifted display value may enter the
signal frame.

## Actual Trade Event Contract

Signals are generated once over each chronological native-timeframe frame.
One event key is `(ticker, horizon, theme_variant, strategy_id, signal_date)`.
Exactly one next-bar entry and one later SL, TP, or timeout exit are calculated
for that key. The same actual signal may not become multiple events merely
because it falls in several overlapping rolling windows.

Rolling date windows remain available for calibration/holdout reporting, but
they do not create or duplicate TradeEvents. A period report includes only
completed events whose signal and exit are both inside that period. This avoids
using a later period's bars to score an earlier period.

## Certification Gates

Certification examines only the three fixed strategies for the matching
ticker, horizon, and theme variant. It requires all of:

- At least 30 unique completed full-history trade pairs for that ticker.
- Deflated Sharpe at or above the explicit `dsr_cutoff`, initially `0.95`.
- Moving-block permutation p-value at or below explicit
  `permutation_alpha`, initially `0.05`.

Calibration and holdout diagnostics are mandatory evidence, not an additional
per-ticker pass/fail certification gate. A five-year Mid-term holdout can have
too few unique completed trades for a stable ticker-level statistic. Any
proposal to change a numerical gate from that evidence requires a separate
explicit approval before production values change.

`dsr_cutoff` and `permutation_alpha` are separate configuration fields. They
must not be derived from one another. Initial numerical values are retained
while correctness is repaired. The implementation plan may measure alternative
values only on the frozen pre-2021 universe. It must stop and request approval
with the full multi-ticker calibration/holdout report before changing either
production value.

The DSR trial set contains the three fixed strategies, not the former 270
subset/threshold/ADX candidates. `certify_top_sets()` may still rank qualified
strategies separately for win rate, profit, and Sharpe. If no strategy passes,
the persisted metric values remain `null`.

## Validation and Acceptance Evidence

The implementation must create deterministic synthetic tests and read-only
database reports for every phase:

1. **Price audit:** valid, indeterminate, and false-clean-ceiling fixtures;
   deterministic eight-ticker selection snapshot.
2. **Indicator contract:** Alligator seed, causal lag, label states, and
   future-row mutation proof; existing MA Cross/RSI/OBV labels unchanged.
3. **Strategy scores:** exactly three stable IDs, no generated subsets or ADX
   mode grid, fixed score-60 upward crossing, and hard ADX suppression.
4. **Trade parity:** golden daily and weekly traces assert signal date,
   next-open entry, raw ATR SL/TP levels, minimum-hold rejection, SL-first
   ambiguity, and inclusive timeout. The production trace must match the
   approved contract before simulated results are compared.
5. **Unique events:** overlapping calibration windows cannot create duplicate
   event keys; period partition excludes boundary-crossing exits.
6. **Statistics:** unique `n`, three-trial DSR input, independent alpha,
   per-ticker `n >= 30`, null certification, and qualified metric ranking.
7. **Live-safe evidence:** one read-only report records each frozen ticker's
   audit state, calibration/holdout metrics, event counts, rejection funnel,
   and VCB canary trace. No job or current signal file is overwritten during
   diagnostic measurement.

## Success Criteria

The work succeeds only when every listed contract has focused test evidence,
the full frozen-universe report is reproducible from current database data,
and per-ticker artifacts contain a qualified compact strategy only when it
passes the stated gates. A VCB non-null result is not a success criterion;
VCB `null` remains correct if it fails those gates.
