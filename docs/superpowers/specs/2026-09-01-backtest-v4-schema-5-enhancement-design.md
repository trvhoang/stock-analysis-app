# Backtest V4 Schema-5 Evidence Integrity and Enhancement Design

**Date:** 2026-09-01

**Status:** Approved design; not implemented

**Scope:** Backtest V4 Swing and Mid-term schema-5 evidence, controlled entry
research, downstream validation safety, and exact-parity runtime work.

## Purpose

Backtest V4 currently produces schema-4 exploratory rulebook artifacts. A
read-only code, test, artifact, Docker, and PostgreSQL audit confirmed that the
candidate, DSR-treatment, and Top-3 contracts mostly match their approved
design, but also reproduced evidence-integrity defects that can change signal
dates, trade returns, candidate membership, and BUY eligibility.

Schema 5 repairs those defects before any strategy enhancement is evaluated.
It then evaluates one predeclared Swing experiment and one conditional
Mid-term experiment without allowing the already-observed historical test to
select a rule. Runtime optimization is last and must preserve exact traces.

This design does not declare any rulebook profitable, tradable, statistically
certified, or automatically promoted. Every visible result remains
**Exploratory — gross**.

## Authority and invariants

- Long-only BUY research only. Actual BUY and SELL decisions remain manual.
- One completed trade contains one simulated BUY and one simulated SELL.
- No fee, tax, slippage, market impact, or partial-fill model is added.
- Prices retain the existing BIGINT-times-1000 storage contract.
- Dynamic SQL remains bound through the existing project database helpers.
- `app/common_queries.py` and protected BIGINT/database boundaries remain
  unchanged.
- Existing schema-4 results are never parsed as schema 5 and never silently
  migrated.
- Existing manual and saved position history remains frozen historical data.
- No new dependency is required.

## Confirmed evidence behind the design

The audit reproduced the following material defects:

1. Mid-term ticker indicators use completed `W-FRI`, while VN-Index theme
   confirmation uses default `W-SUN`. A minimal fixture delayed the intended
   Friday theme by one week.
2. A historical source ending on Wednesday could emit a weekly bar labelled
   with the following Friday because the indicator builder defaulted to the
   current wall clock instead of the request cutoff.
3. The calendar 10-year/5-year split checks initial coverage but not terminal
   coverage. Truncated histories could therefore be labelled as a complete
   five-year test.
4. A long stop was filled at the configured stop even when the eligible bar
   opened below it. In the frozen sample, 158 Top-3 exits opened below their
   stop; the largest measured return distortion was 16.7019 percentage points.
5. A trade whose stop or target completed inside its partition was discarded
   if its full timeout horizon did not also fit. The approved resolution is to
   retain the completed in-partition trade.
6. Long history gaps are warnings only. VPL passed the existing clean audit at
   10.8% VN-Index-session coverage and could return `can BUY`.
7. Current replay validates the latest OHLC shape but reuses artifact-owned
   audit eligibility. Appended or corrected source history can therefore leave
   qualification evidence stale.
8. Local RSI, ATR, and ADX use an EWM approximation. The approved schema-5
   formula is exact SMA-seeded Wilder smoothing.

The diagnostic sample was `VCB, DHC, DSN, ELC, BVH, HAP, DRC, CSM` over the
available 15-year request. It is falsification evidence, not a representative
market claim. The existing five-year partition has been viewed repeatedly and
is no longer untouched evidence for this enhancement.

## Version and terminology contract

The product name remains **Backtest V4**. The persistence and evidence contract
becomes **schema 5**.

- Canonical rulebook IDs become `swing_rulebook_v5` and
  `midterm_rulebook_v5`.
- Serialized request types become `backtest_single_v5` and
  `backtest_batch_v5`.
- Canonical ticker/horizon filenames remain unchanged so each new run
  atomically replaces the current artifact.
- Schema-4 artifacts and visible job sidecars are overwritten with schema-5
  `requires_regeneration` terminal documents without parsing their payloads.
- Remaining internal V3 terminology is renamed only where the schema-5 code
  is already being changed. Unrelated historical documents are not rewritten.

## Schema-5 artifact contract

Every terminal artifact contains the existing ticker, horizon, requested and
effective ranges, split, candidates, treatments, training/test metrics, and
Top-3 identity, plus these mandatory schema-5 fields:

```json
{
  "schema_version": 5,
  "contract_version": "backtest_schema5_v1",
  "evaluation_label": "Exploratory — gross",
  "partition_labels": {
    "training": "in-sample",
    "test": "historical test — previously observed"
  },
  "audit_eligibility": {},
  "evidence_eligibility": {
    "status": "eligible",
    "eligible": true,
    "reasons": [],
    "common_as_of": "2026-08-28",
    "first_available_bar": "2011-09-01",
    "last_available_bar": "2026-08-28",
    "ticker_fingerprint": "<sha256>",
    "vnindex_fingerprint": "<sha256>",
    "observed_sessions": 3739,
    "expected_sessions": 3740,
    "coverage_ratio": 0.9997326203,
    "max_gap_sessions": 1
  }
}
```

`audit_eligibility` owns raw OHLC validity and price-anomaly findings.
`evidence_eligibility` independently owns source identity, freshness, session
density, and BUY safety. A result may remain displayable when evidence is
ineligible, but it cannot authorize `can BUY`.

`requires_regeneration` artifacts contain no candidates, split, or prior
metrics. Their evidence status is `unavailable`, and their reason identifies
schema amendment or source-fingerprint change.

## Source fingerprint and freshness

The fingerprint is SHA-256 over canonical ordered raw source tuples through
the artifact's common as-of date:

```text
ticker | date | open | high | low | close | volume
```

Dates use ISO format. Numeric fields use their database integer values before
display scaling. Rows are ordered by date and duplicate dates are invalid.
Ticker and VN-Index fingerprints are independent.

Current validation performs two comparisons:

1. Recompute the frozen-range fingerprint to detect corrections to historical
   rows.
2. Compare the current latest completed common bar with the artifact
   `common_as_of` to detect newly appended evidence.

Any mismatch atomically replaces the canonical result with a schema-5
`requires_regeneration` marker and returns `expired BUY`; no stale candidate is
replayed as eligible. A normal Collect Signals run regenerates the full
artifact.

The existing ingestion `ON CONFLICT DO NOTHING` policy is not changed by this
design. A future correction-aware ingestion workflow requires separate
approval. Schema 5 detects database history changes when they actually exist;
it does not invent correction provenance.

## Common as-of and session-density contract

For a single run, the common as-of is the latest completed daily bar shared by
the ticker and VN-Index within the request end. For a batch, it is calculated
once across the entire requested ticker union and VN-Index. Every source is
sliced to that date before fingerprinting or indicator construction.

Evidence density is measured from the ticker's first available bar through the
common as-of date, not from the beginning of the requested 15 years. Therefore
a newly listed ticker is not rejected merely for having less than five years
of history.

Evidence is eligible only when all of these are true:

- the latest ticker bar equals the batch common as-of;
- the ticker contains at least 95% of VN-Index session dates in its effective
  interval;
- no run of missing VN-Index sessions exceeds 20 consecutive sessions;
- raw audit eligibility is clean.

Failure is display-only and BUY-blocked with exact counts and reasons. The
database first row is labelled `first_available_bar`, not `listing_date`,
because official listing-date provenance is unavailable.

## Exact indicator formulas

### RSI

For period `p`, bar zero has no delta. Gains and losses from bars 1 through `p`
form the first simple-average seed at bar `p`. Subsequent values use:

```text
average_t = (average_(t-1) * (p - 1) + value_t) / p
```

Zero-loss and zero-gain behavior is explicitly tested. Swing retains RSI(9)
upcross 52; Mid-term retains RSI(14) upcross 65 for the corrected baseline.

### ATR

True range at bar zero is `high - low`. ATR period `p` is seeded at bar
`p - 1` with the simple average of the first `p` true ranges, then uses the
same Wilder recursion. ATR(14) remains frozen on the BUY signal bar.

### ADX and DMI

`+DM`, `-DM`, and true range are calculated causally. Their period-14 Wilder
averages are seeded at bar 13. `+DI`, `-DI`, and DX begin from that seed. ADX
is seeded at bar 26 with the simple average of the first 14 valid DX values and
then recursively smoothed.

The existing EMA definition remains unchanged. Alligator already uses an
SMA-seeded recursive SMMA and retains its approved periods and lags.

## Completed weekly clock

One Backtest-owned adapter constructs ticker and VN-Index weekly bars:

- frequency, label, and close are `W-FRI`;
- daily OHLCV is sliced to the common as-of first;
- a weekly label is retained only when that Friday is not later than the
  common as-of;
- both ticker and theme use the same returned dates;
- backward/as-of theme alignment cannot select a future weekly value.

Without an approved exchange calendar, a shortened holiday week is handled
conservatively: it is excluded until the period-ending Friday is not later
than the common as-of. The adapter never uses the wall-clock date to complete a
historical request.

## Split and boundary execution

A nominal 15-year request uses the calendar 10-year/5-year split only if both
effective endpoints cover the request within the existing seven-calendar-day
tolerance. Both the first and last effective dates are checked. Any other
history uses the existing chronological 65%/35% effective-date split.

Training accepts only trades whose signal, entry, and exit are before the test
start. Test accepts only trades whose signal and entry are on or after the test
start and whose exit completes inside test. Indicators may use earlier bars
for causal warm-up.

Execution scans only through the earlier of the configured timeout or the last
bar in the active partition:

- retain a stop or target completed inside the partition even when the future
  timeout would lie outside it;
- emit timeout only when the configured timeout bar is inside the partition;
- otherwise drop the still-open trade;
- never carry position state across the boundary.

## Gap-safe execution

The long stop rule becomes:

```text
if eligible_bar.open < frozen_stop:
    exit_price = eligible_bar.open
elif eligible_bar.low <= frozen_stop:
    exit_price = frozen_stop
```

Take-profit continues to fill at the configured target when the eligible bar
reaches it, including a gap above target. This is conservative rather than
optimistic. If one bar reaches both stop and target, stop-first ordering
remains. Minimum exit offsets, ATR multipliers, and inclusive timeout values do
not change.

## Corrected baseline control

Schema 5 first regenerates the existing exploratory baseline under corrected
formulas and evidence semantics:

- all 15 non-empty subsets of joint trend, RSI upcross, volume, and ADX;
- no-theme and VN-Index-AND treatments;
- candidate membership from no-theme training `n >= 5`;
- DSR chooses the preferred treatment only, with no threshold;
- p-value remains informational at every `n` and unavailable at `n <= 20`;
- preferred training win rate, gross return sum, Sharpe, then lexical ID ranks
  Top 3;
- test metrics cannot change candidate membership, treatment, or rank.

These candidates are explicitly `baseline_control`. Directionless and
persistent-state subsets are retained only to establish the corrected control;
they are not automatically adopted by the staged research architecture.

## Staged research architecture

Research definitions separate three entry responsibilities:

1. **Setup:** mandatory persistent directional regime.
2. **Trigger:** mandatory causal one-bar BUY event.
3. **Confirmation:** zero or more optional filters.

ADX, relative volume, and VN-Index treatment cannot form standalone BUY
rulebooks. If ADX is later used directionally, its confirmation must also
require `+DI > -DI`.

Research outputs are immutable schema-5 evidence with
`candidate_role: research_only`. They do not enter View Signals, Validate
Signals, saved-signal selection, position advice, or canonical Top 3 until a
separate promotion design is approved. A zero-result experiment is valid.

## Swing experiment 1

Only the setup changes:

| Definition | Setup | Trigger |
|---|---|---|
| Control | EMA5 > EMA13 and Alligator lips > teeth > jaw | RSI(9) upcross 52 |
| Variant | EMA5 > EMA13 | RSI(9) upcross 52 |

Both no-theme and VN-Index-AND treatments are evaluated. Exact-Wilder ATR(14),
1.5x stop, 2.5x target, three-bar exit offset, 22-bar timeout, and every other
execution rule are frozen.

Control and variant trades are paired by deterministic first-overlap
two-pointer pairing on inclusive completed-trade intervals. The variant
advances only when all approved training conditions pass:

- at least five completed matched pairs;
- median BUY signal lead is at least one trading session;
- variant ranks ahead by win rate, gross return, then Sharpe;
- MAE, stop-loss rate, and maximum drawdown are each no worse;
- positive leave-one-calendar-year-out count is at least the control count.

For deterministic diagnostics, the inclusive pairing interval is entry date
through completed exit date. Signal lead is the control signal's native-bar
ordinal minus the variant signal's native-bar ordinal, so a positive value
means the variant fired earlier. MAE is the mean of each completed long
trade's non-negative maximum adverse excursion from entry through exit.
Maximum drawdown compounds chronological gross trade returns from equity 1.0
and reports the greatest peak-to-trough percentage decline.

## Mid-term experiment 1

This experiment cannot start until the corrected W-FRI baseline is regenerated
and verified.

| Definition | Setup | Trigger |
|---|---|---|
| Control | SMA8 > SMA21 and Alligator lips > teeth > jaw | RSI(14) upcross 65 |
| Variant | Same joint setup | prior close <= prior SMA8 and current close > current SMA8 |

Theme treatments and all exact-Wilder ATR/exit behavior remain frozen. The
variant advances only when all approved training conditions pass:

- it ranks ahead by win rate, gross return, then Sharpe;
- it trades in at least as many distinct training years;
- its largest single-year share of absolute gross P&L is no greater;
- its maximum drawdown is no worse;
- its positive leave-one-calendar-year-out count is at least the control
  count.

## Selection and evidence labels

Control-versus-variant selection uses the 10-year training partition only.
Leave-one-calendar-year-out runs diagnose concentration and cannot tune any
period, level, threshold, or exit.

Completed gross P&L belongs to the exit calendar year. Absolute-P&L
concentration is the largest absolute net yearly gross-return sum divided by
the sum of absolute net yearly gross-return sums; a zero denominator returns
zero. A leave-one-year-out result is positive only when the retained gross
return sum is strictly greater than zero. These diagnostics use no test data
for acceptance.

The selected definition and immutable ID are frozen before opening the
five-year partition. That partition is always labelled
**historical test — previously observed** and cannot promote or reject the
definition. Only observations accumulated after the freeze date can be called
**untouched test**.

No rule is statistically certified. DSR retains its narrow role of selecting
no-theme versus VN-Index-AND for the same definition.

## Position and SELL-advice semantics

For schema-5 saved signals, loss of a one-bar BUY trigger does not itself mean
`can SELL`.

An OPEN position uses:

- frozen stop/target and holding-time conditions;
- explicit technical-exit predicates when the adopted rulebook defines them;
- separately defined setup/confirmation deterioration when the adopted
  rulebook defines it.

The corrected baseline defines no new technical SELL predicate, so its OPEN
positions use the existing frozen price/holding rules without treating a
consumed entry event as deterioration. Manual P&L-only positions retain their
approved risk path.

## Runtime design

Runtime work follows semantic verification. It may replace internal loops but
not contracts:

1. vectorize moving-block permutation while preserving seed, blocks, null
   distribution, and p-value exactly;
2. replace row-object trade scans with array-index execution while preserving
   every signal, entry, exit, price, reason, and source window;
3. optimize SMA-seeded recursive smoothing with exact numeric parity;
4. measure end-to-end p50/p95 time and peak memory before considering ticker
   parallelism.

The current sequential batch contract remains until those optimizations pass
and database/memory concurrency is measured. Primitive-mask caching is not
added because the audit found no repeated sequences in the profiled VCB run.

## Failure and recovery behavior

- Invalid raw OHLC writes a schema-5 failed artifact and remains BUY-blocked.
- Ineligible density remains displayable with exact reasons but BUY-blocked.
- Missing VN-Index evidence fails the paired-treatment run; no no-theme-only
  artifact is invented.
- Source mismatch writes `requires_regeneration` atomically.
- A partial artifact or temporary-file failure never replaces the last valid
  terminal document.
- Research experiment failure cannot mutate canonical baseline artifacts.
- Runtime parity failure retains the reference implementation.

## UI contract

- View Signals reads canonical schema 5 only.
- Every result remains **Exploratory — gross**.
- Training is labelled `in-sample`.
- The existing fixed test is labelled `historical test — previously observed`.
- `untouched test` appears only for post-freeze evidence.
- Evidence status and regeneration reason are visible.
- Ineligible/stale results never offer an eligible BUY action.
- Research-only experiment evidence is kept outside product signal selection
  until a separate promotion approval.

## Implementation order and gates

1. Exact formulas and independent golden fixtures.
2. Shared common-as-of/W-FRI clock.
3. Honest split, completed-partition exits, and gap-safe stops.
4. Source fingerprints and evidence-density eligibility.
5. Schema-5 persistence, regeneration, readers, UI, and validation safety.
6. Separate entry trigger from OPEN-position SELL advice.
7. Corrected real-data baseline and frozen evidence report.
8. Staged research contracts and training-only selection.
9. Swing experiment; conditional Mid-term experiment.
10. Exact-parity runtime optimization.
11. Full Docker verification and practical database evidence.

No later gate starts while an earlier correctness or schema gate is failing.
Research cannot automatically promote a rulebook. Runtime work cannot alter a
trade trace, metric, rank, or artifact.

## Required verification

The implementation must include independent tests for:

- exact RSI, ATR, ADX, DMI, and Alligator seeds;
- ticker/theme W-FRI identity and historical cutoffs;
- full-start/full-end calendar coverage and 65%/35% fallback;
- completed in-partition exit retention and crossing rejection;
- stop gaps, target gaps, collision, offset, and timeout;
- source fingerprint append/correction and atomic invalidation;
- recent listings, 95% density, 20-session gaps, and common as-of;
- schema-4 rejection and schema-5 regeneration markers;
- DSR, p-value, candidate membership, and exact Top-3 ordering;
- entry/SELL separation for OPEN positions;
- first-overlap pairing, annual concentration, MAE, drawdown, and leave-one-year-out metrics;
- reference-versus-optimized trace and artifact parity;
- View, Validate, Current Positions, worker, and batch progress behavior.

Final verification uses Docker's canonical Backtest gate, full project
discovery, compilation, protected-boundary diff inspection, and read-only
PostgreSQL pilots. Implementation and product promotion each require separate
explicit approval.
