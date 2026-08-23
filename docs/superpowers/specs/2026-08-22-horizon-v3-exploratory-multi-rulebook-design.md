# Horizon Rulebook V3 — Exploratory Multi-Rulebook Design

**Date:** 2026-08-22  
**Status:** Implemented and verified on 2026-08-22.  
**Scope:** Replace V3 fixed-rulebook binary certification with schema-4 exploratory multi-rulebook evaluation.

## Supersession and objective

This design supersedes entry gates, PSR/DSR policy, binary certification,
schema-3 artifacts, and V3 consumers in:

- 2026-08-15-horizon-rulebook-signal-redesign-design.md
- 2026-08-21-horizon-rulebook-v3-gate-statistics-update-design.md

The isolated read-only research_optimizer remains unchanged. Raw-price storage,
indicator construction, completed-bar handling, weekly completion, ATR exits,
trade execution assumptions, database schema, and Position Info cost entry stay
unchanged.

Goal: persist every qualifying exploratory candidate, rank multiple distinct
rulebooks per ticker/horizon, and show gross in-sample and out-of-sample evidence
without calling an output profitable, tradable, or statistically certified.

## Candidate family

Each horizon keeps existing fixed indicator and execution parameters. Only entry
gate subset varies.

| Horizon | Fixed inputs | ADX minimum | Training n |
|---|---|---:|---:|
| Swing | Daily EMA(5/13), RSI(9) upcross 52, causal Alligator, prior-10-session 1.15x volume, ADX(14), ATR exits, 22-bar inclusive timeout | 17 | 5 |
| Mid-term | Completed W-FRI SMA(8/21), RSI(14) upcross 65, causal Alligator, prior-8-week 1.3x volume, ADX(14), ATR exits, 16-bar inclusive timeout | 20 | 5 |

Evaluate all fifteen non-empty subsets of these causal Boolean gates:

1. RSI upcross
2. joint MA/Alligator trend
3. volume
4. ADX

Missing/non-finite input is false. No parameter, threshold, hold length, or
subset is tuned after observing results. Rulebook IDs combine horizon and
lexically ordered gates, for example
swing_rulebook_v4__adx__joint_trend__rsi_upcross.

Every subset runs both no-background-theme and VN-Index AND background-theme
treatments. Schema-4 has no no-theme-only execution and no theme checkbox.

## Split, warm-up, and execution

A requested full 15-year range uses first 10 calendar years for training and
final 5 for test. If usable history does not cover that range, split effective
native-frame date span chronologically 65% training and 35% test. Persist split
method and actual native dates.

Build causal indicators once over full native frame. Test indicators may use
previous training bars as warm-up only. No trade state crosses split:

- Training starts flat. Keep only trades whose signal, entry, and exit precede
  test start.
- Test starts separately flat at test start. Keep only trades whose signal,
  entry, and exit are within test.
- Drop incomplete and crossing trades.

Independent partition execution prevents an omitted crossing trade from
suppressing a valid test entry.

## Statistics, candidate membership, and Top 3

A rulebook is an exploratory candidate when no-theme training n is at least 5.
This gives deterministic membership when theme yields few trades. Persist both
treatments for every candidate.

If both treatments have at least two finite training returns, calculate exact
two-Sharpe DSR values. DSR selects preferred_variant only:

1. Higher unrounded training DSR wins.
2. Exact DSR tie chooses no-background-theme.
3. If themed DSR cannot calculate, store DSR unavailable and choose no-theme.

DSR has no cutoff. It cannot rank rulebooks, certify a result, or use test
returns. PSR is removed from V3 calculations, persisted output, UI, and request
configuration.

Rank each candidate's preferred treatment by unrounded training values:

1. ordinary win_rate
2. gross profit_pct
3. unannualized Sharpe
4. lexical rulebook_id

First three form Top 3. Exact ties still hard-stop at three after lexical ID.
Test metrics never rank or select candidates.

Keep one-sided centered moving-block bootstrap only as information. Block size
stays 20. At n <= 20, persist p_value null with explicit N/A status; do not
calculate degenerate one-block p-value. At n > 20, persist exact p-value,
labelled informational. It never blocks, rejects, or certifies.

Every visible surface uses **Exploratory — gross**. Training says
**Exploratory — gross, in-sample**. Test says
**Exploratory — gross, out-of-sample**. Fees, tax, and slippage stay outside
product. No product text may say profitable, tradable, or statistically
certified.

## Schema-4 and regeneration

One current artifact exists per ticker/horizon:

backtest-result/ticker-signals/<TICKER>/<TICKER>_signals_<horizon>.json

Terminal state is success, empty, failed, or requires_regeneration.

A success document has fixed inputs, audit metadata, requested/effective ranges,
split dates, every exploratory candidate, and ordered top_rulebook_ids. Each
candidate contains selected gates, rulebook_id, preferred_variant, both treatment
records, and exact train/test metrics. Training records contain DSR selection
data and p-value status. Test records contain gross metrics and p-value status.

Empty means no no-theme training subset reaches n 5. Failed means source or
execution error. Requires_regeneration records superseded policy and no
candidate evidence.

Existing schema-3 treatment files are never read, parsed, migrated, replayed, or
fallback evidence. Filename-only invalidation creates canonical schema-4
requires_regeneration document per ticker/horizon and overwrites old
per-treatment files with schema-4 regeneration markers.

Old request/status sidecars are also identified by filename only, then
overwritten as terminal schema-4 requires_regeneration markers. Workers refuse
these markers. UI renders Regenerate under amended rulebook.

## Reads, actions, and frozen positions

View Signals reads canonical schema-4 artifacts only. It presents Top 3
rulebooks per ticker/horizon, both treatments, and train/test labels. Full
persisted candidate list is not a BUY surface.

Validate replays only preferred treatment of a Top-3 rulebook. Companion
treatment remains visible evidence but cannot independently create BUY draft.
Its monitoring score uses only that rulebook's selected ticker gates, with
equal weights. When preferred treatment is VN-Index AND, VN-Index confirmation
is one additional equally weighted monitoring factor. It must not score
unselected gates or affect literal entry, ranking, DSR selection, or BUY
eligibility.
Literal entry is necessary but not sufficient: fresh audit other than clean makes
candidate display-only and buy_eligible false.

New position references use schema version 4 plus ticker, horizon, rulebook_id,
preferred_variant, the frozen exploratory candidate, and audit_eligible. The
position store independently rejects an audit-ineligible signal-backed BUY;
existing schema-3 and older references remain readable as frozen
P&L/manual-management history only.

## Boundaries and acceptance

A fresh audit runs per ticker. Indeterminate/invalid audit results remain visible
but block BUY. VN-Index source failure writes one failed ticker/horizon aggregate
because both treatments are mandatory.

Do not change common_queries.py, BIGINT scaling, get_engine_with_retry,
credentials, Docker, database schema, dependencies, research_optimizer, or V2
deletion policy. Parent Horizon Tasks 8--9 retain their own tracker and explicit
V2-deletion gate.

Acceptance checks:

1. Evaluate exactly 15 gate subsets, each with both treatments.
2. Enforce split boundaries and causal-only test warm-up.
3. Persist every no-theme training candidate with n >= 5; persist none below.
4. Use DSR only for treatment selection and no-theme fallback.
5. Rank exactly by training win rate, profit, Sharpe, then lexical ID.
6. Store p-value N/A at n <= 20; never gate on p-value.
7. Replace stale artifacts/jobs with filename-only schema-4 markers.
8. Block BUY for audit-ineligible results while keeping display.
9. Enforce exploratory gross wording, no PSR, no certification language.
10. Pass focused Backtest Docker tests, compilation, and fresh schema-4
    evidence before rerunning parent Task 7. Validate Positions remains blocked
    until parent Tasks 7--9 finish.
