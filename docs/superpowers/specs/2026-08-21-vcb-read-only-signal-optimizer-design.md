# VCB Read-only Signal Optimizer — Design

**Status:** Approved design; implementation not started.  
**Scope:** VCB only, 15 years of DB history, research-only.  
**Non-goal:** Do not change canonical V3 rulebooks, Task 7, persistence,
artifacts, jobs, catalog, UI, positions, or DB data.

## Purpose

Search VCB historical signal-gate sets instead of evaluating only the one
predefined V3 combination. Produce one Markdown report identifying best
in-sample eligible set for each of win rate, total profit percentage, and
unannualized Sharpe.

Results use all available 15-year history in-sample. They are research
evidence, not predictive validation, a V3 certification result, or trading
advice.

## Candidate Universe

Evaluate Swing daily and Mid-term weekly independently. For each horizon,
enumerate every nonempty subset of these four existing Backtest-owned Boolean
gates:

1. RSI upcross
2. Joint MA/Alligator trend
3. Prior-only volume gate
4. ADX gate

Each of 15 subsets has two treatments: no-theme and VN-Index confirmation as
an additional AND condition. This creates 30 candidates per horizon and 60
candidates across the research run.

Candidate identity is ordered horizon, theme variant, and ordered selected
gate names. Missing or non-finite required inputs always block entry, even
when their corresponding signal gate is not selected.

## Shared Execution

Every candidate reuses the existing causal native-timeframe frame and V3
execution contract: next-native-open BUY, raw-BIGINT ATR(14) stop-loss and
take-profit, conservative stop-first resolution, one flat-to-flat trade at a
time, and horizon-owned exit timing and timeout. Indicator periods,
thresholds, ATR multipliers, hold limits, and BIGINT scaling remain canonical
and fixed.

The VN-Index frame is loaded once per horizon. A themed candidate is its
ticker-gate conjunction AND the existing causal theme eligibility; it never
changes ticker gate direction or acts as a separate entry signal.

## Eligibility and Statistics

Candidates with fewer than five completed exits are rejected as `min_n` and
cannot rank. The pre-statistical family is every same-horizon candidate with
`n >= 5`, before any PSR, DSR, or permutation result is considered.

Each candidate must pass all of:

- PSR at least `0.95`;
- DSR at least `0.95`, with the full same-horizon pre-statistical family as
  its observed trial family;
- existing centered moving-block permutation test with `p <= 0.05`, 1,000
  draws, seed 42, and block size 20.

Swing and Mid-term DSR families remain separate; daily and weekly candidates
are never mixed. Failed or non-computable statistics are explicit rejection
reasons. This research policy is intentionally stricter than V3's existing
no-theme PSR / themed pair-DSR policy, because selection searches multiple
candidates.

## Ranking and Ties

Rank only fully eligible candidates, separately per horizon, by:

1. win rate;
2. `profit_pct`, defined as existing Backtest sum of per-trade return
   percentages, not compounded equity return;
3. unannualized per-trade Sharpe.

Use exact unrounded stored metric values for ties. A candidate winning several
metrics is one shared winner with every won metric listed. All candidates tied
at the exact best value for a metric remain in the report. If a horizon has no
fully eligible candidate, report no winner and the rejection funnel.

## Report Contract

Write one Markdown file under `docs/superpowers/reports/`. It contains:

- run scope, in-sample warning, source bounds, raw row counts, and VCB audit;
- fixed execution and statistical settings;
- candidate counts by horizon and rejection reason;
- every fully eligible candidate with identity, `n`, win rate, profit,
  Sharpe, PSR, DSR, permutation p-value, and trial-family size;
- one winner section per horizon that consolidates shared winners and exact
  ties; and
- an explicit statement that no V3 artifact, job, DB, or configuration changed.

## Implementation Boundaries

Create an isolated research module with pure candidate enumeration, entry
construction, evaluation, ranking, and Markdown rendering. It may reuse V3
frame, theme, trade-sequence, and statistical primitives but must not weaken
or add mutable paths to `RulebookSpec`, `BacktestConfig`, current pipeline,
or persistence.

The execution entry point is an explicit manual research command, not a
Streamlit action or background job. It performs DB reads and writes only its
named Markdown report.

## Test Contract

- exactly 15 gate subsets and 30 treatments per horizon;
- missing input blocks every candidate entry;
- themed entry is strict AND and no-theme never loads theme data;
- every candidate uses unchanged native V3 execution;
- DSR family includes every same-horizon `n >= 5` candidate before statistical
  filtering and never mixes horizons;
- exact unrounded ties are retained and multi-metric winners consolidate;
- report records eligible and rejected candidates plus in-sample warning; and
- canonical V3 configs, artifacts, jobs, and DB writers are not called.
