# Flexible Rulebook User-Authored Redesign

**Date:** 2026-09-15  
**Status:** Approved design decisions; implementation not started  
**Scope:** Selectively replace automated Flexible Rulebook discovery with a
user-authored, causally backtested rulebook workflow for Daily Swing and
completed W-FRI Mid-term.

## Goal

Flexible Rulebook must let a user define, save, evaluate, publish, and later
use an explainable technical rulebook against ticker history already stored in
the project database.

The redesign must:

- make rulebook creation the primary workflow;
- reuse trusted project calculations where their causal semantics and parity
  are proven;
- allow validated indicator parameters rather than a fixed catalog;
- preserve independent training and untouched-test evidence per ticker;
- keep published rulebook identity immutable and backstage;
- integrate published rules with Backtest without altering Standard rulebook
  semantics; and
- retire the current search, benchmark, activation, and campaign machinery
  only after replacement coverage passes.

## Non-goals

- No automatic candidate discovery or combinatorial optimizer.
- No real-time or intraday trading.
- No order placement or automatic Position mutation.
- No short selling.
- No statistical-certification or profitability claim.
- No fees, tax, or slippage.
- No nested arbitrary Boolean expression language.
- No mixed daily/weekly conditions inside one rulebook.
- No Fibonacci prediction, Ichimoku, PPO/MACD, Aroon, Choppiness, CMF, or
  other new indicator families in this redesign.
- No automatic parsing or migration of legacy Flexible Rulebook artifacts.
- No database-schema, credential, BIGINT scaling, `common_queries.py`, or
  Docker change.

Every result remains labelled **Exploratory — gross**.

## Current-state audit

The existing Flexible Rulebook is an automated research platform rather than
a rulebook builder. Its UI exposes Discover, Rulebook Library, Cross-ticker
Qualification, and Current Group BUY Scan. Its runtime includes a fixed
catalog, seeded candidate frontier, campaigns, subprocess workers, benchmarks,
activation policy, scope expansion, qualification, and timing-distinct Top 3.

The present feature engine supports only EMA, RSI, prior-extrema breakout,
relative volume, ATR, and ADX. `RulebookDefinition` is immutable and supports
BUY predicates, gates, filters, technical exits, ATR exits, and a bounded
timeout, but the UI cannot author one. History is hard-coded to 15 years and a
10y/5y or 65%/35% split. The executor is daily-only. Storage is immutable-only,
so it cannot represent editable drafts.

The following foundations are valuable and remain conceptually reusable:

- VN-Index calendar alignment and live Listed/Delisted checks;
- raw OHLCV validation and full-source fingerprints;
- component-level primitive caching with safe-miss behavior;
- canonical serialization and immutable hashes;
- flat-to-flat causal execution;
- completed-trade gross metrics; and
- atomic contained-path persistence.

## Product workflow

The page has three workspaces.

### 1. Rulebook Builder

The builder contains:

- display name and optional description;
- horizon: `Swing` or `Mid-term`;
- BUY conditions with `Match all` or `Match any`;
- zero or more entry gates/filters, all of which must pass;
- zero or more technical SELL conditions, any of which may trigger;
- optional ATR stop, target, or trailing exit;
- mandatory timeout from 4 through 64 native bars;
- fixed minimum hold of 3 native bars;
- inline parameter validation and a human-readable rule summary; and
- `Save draft`, `Validate draft`, and `Clone` actions.

A draft is mutable. Editing a published rule creates a new draft; it never
changes the published version.

### 2. Rulebook Backtest

The evaluator lets the user choose a draft or published rulebook, select one
or more currently Listed database tickers, choose the history range and
training ratio, and run a sequential bounded evaluation with progress.

Results are reported separately per ticker and partition. Each result shows:

- source range, native timeframe, source fingerprint, and split boundary;
- completed trade count;
- win rate, total gross return, mean gross return, and per-trade Sharpe;
- entry and exit events with signal/fill dates and exit reasons;
- insufficient-history, warm-up, no-signal, no-completed-trade, and data-quality
  warnings; and
- the exact rule summary and formula revisions used.

An evaluation never silently changes or tunes a rulebook. A zero-trade result
is valid evidence and remains visible.

### 3. Rulebook Library

The library lists Draft, Evaluated, Published, and Retired versions. `Evaluated`
is a derived badge for the current semantic digest, not a mutable lifecycle
state. It allows
the user to inspect evidence, edit or delete drafts, clone any version, publish
an evaluated definition, and retire a published version.

Publishing requires:

- structurally valid causal semantics;
- at least one completed train/test evaluation artifact; and
- explicit user confirmation.

Editing a draft changes its semantic digest and immediately removes the
`Evaluated` badge until that exact revision is evaluated. Evidence from the
older draft digest remains immutable history but cannot authorize publication
of the edited draft.

Publishing does not require a fixed win-rate, return, Sharpe, or trade-count
threshold. Low-sample and weak results remain plainly visible. Published
definitions are immutable; retiring one prevents new runs while preserving
historical references.

## Rulebook grammar

One rulebook uses exactly one native timeframe:

| Horizon | Native bars | Weekly rule |
|---|---|---|
| Swing | Daily VN-Index sessions | Not applicable |
| Mid-term | Completed W-FRI bars | Partial current week is excluded |

Entry semantics are:

```text
BUY event = (ALL or ANY selected BUY conditions) AND ALL selected gates
```

At least one BUY condition is required. Gates are optional. A state gate alone
cannot create an entry event.

Exit semantics are:

```text
SELL event = ANY selected technical SELL condition
              OR eligible ATR stop/target/trailing
              OR mandatory timeout
```

The grammar is intentionally bounded. It has no nested groups, free-form code,
or user-supplied formulas. Each predicate is selected from an indicator
registry with typed settings, supported roles, supported comparisons, warm-up,
and formula revision.

## Indicator registry

The registry is the single source of truth for both the builder and evaluator.
It defines family, formula revision, input series, timeframe compatibility,
roles, parameter schema, warm-up, output series, and valid predicates.

### Exposed families

| Family | Supported uses |
|---|---|
| SMA / EMA | Price above/below; fast/slow state; bullish/bearish cross; direction |
| RSI | Above/below; up/down cross; rising/falling over a validated lookback |
| Alligator | Bullish/bearish alignment; opening/closing; line cross; direction |
| ADX / DMI | ADX threshold/direction; `+DI` versus `-DI`; directional cross |
| Stochastic | `%K/%D` state and cross; overbought/oversold threshold; direction |
| Prior high/low breakout | Close crosses or remains beyond prior-N extrema |
| Relative volume | Current volume versus prior-N average; direction |
| OBV | Rising/falling and moving-average state/cross |
| ATR | Price exits and volatility gates; not a standalone BUY event |
| Bollinger Bands | Band/middle cross or state; percent-B; bandwidth threshold/direction |
| Supertrend | Bullish/bearish state, direction flip, and technical exit |

Only Bollinger Bands and Supertrend are additions to the agreed project-facing
indicator scope. Bollinger math already exists but must clear causal and parity
fixtures before registry exposure. Supertrend is a new local implementation.

### Formula requirements

- SMA is the arithmetic mean of the last N completed native closes. EMA uses
  the current Backtest `adjust=False` recurrence, hides its N-1 warm-up rows,
  and must clear parity fixtures before exposure.
- Alligator uses HL2 and the project exact SMA-seeded causal SMMA. Periods and
  offsets are settings; no forward plot displacement is read as present data.
- ADX, DMI, ATR, RSI, and Supertrend use the project exact SMA-seeded Wilder
  recurrence where applicable.
- Stochastic uses rolling high/low raw `%K`, an SMA-smoothed `%K`, and an SMA
  `%D`; all three periods are explicit settings.
- OBV begins at zero and cumulatively adds or subtracts raw volume from the
  completed close direction.
- Relative volume and breakout windows exclude the current bar from their
  baseline.
- Bollinger uses close, an N-bar rolling mean, sample standard deviation
  (`ddof=1`), user multiplier, bandwidth, and percent-B.
- Supertrend uses `basic_upper/lower = HL2 +/- multiplier * ATR(N)`. Its final
  bands carry the prior final band unless the new basic band tightens it or the
  prior close broke the prior band. At the first finite band, direction
  initializes bullish (`+1`) and Supertrend uses that final lower band.
  Direction thereafter flips bullish when close breaks the prior final upper band, flips
  bearish when close breaks the prior final lower band, and otherwise carries
  forward. A flip is recognized only at the completed bar close. This exact
  recurrence receives its own formula revision and golden fixture.
- A generic rising/falling predicate compares the current finite value with
  the value exactly N completed native bars earlier; equality is false. It is
  not an inferred slope. Alligator opening/closing compares the three-line
  spread over that same explicit direction lookback while retaining the
  requested bullish/bearish line order.
- Every rolling, cross, and direction predicate declares its warm-up and
  lookback. Missing warm-up produces `unavailable`, never `True`.
- Parameter changes reuse compatible component arrays only when the component
  identity is unchanged. Threshold-only changes may reuse math and rebuild the
  predicate mask.

### Parameter validation

Each family owns explicit bounds. Initial safe bounds are:

- MA, breakout, Bollinger, OBV, and volume periods: 2–250 native bars;
- RSI, ATR, ADX, and Supertrend periods: 2–100 native bars;
- Stochastic K: 2–100; K smoothing and D: 1–20;
- Alligator periods: 2–100 and offsets: 0–50;
- RSI/Stochastic thresholds: greater than 0 and less than 100;
- ADX threshold: 0–100;
- Bollinger deviation multiplier: 0.1–5.0;
- relative-volume multiplier: 0.1–20.0;
- ATR/Supertrend multipliers: 0.1–20.0; and
- direction lookback: 1–20 native bars.

Fast/slow MA must satisfy `fast < slow`. Alligator period/offset combinations
must be positive, distinct where ordering is semantically required, and fully
recorded. Bounds reject mistakes; they do not prescribe profitable values.

## Causal execution

Execution is long-only, flat-to-flat, and permits one simulated open trade per
ticker/rulebook.

- A signal is formed after a completed native bar.
- BUY fills at the next native open.
- A technical SELL formed at a completed bar fills at the next native open.
- Signal, entry, and exit must all complete inside their evaluation partition.
- Each partition starts flat; boundary-crossing and incomplete trades are
  dropped.
- ATR is frozen on the BUY signal bar.
- Open gaps through an active stop/target fill at the open.
- Intrabar stop/target evaluates OHLC after eligibility; if both touch in the
  same bar, stop wins conservatively.
- `min_hold_bars` is fixed at 3 native bars.
- `max_hold_bars` is definition-owned, mandatory, and limited to 4–64 native
  bars.
- Timeout exits at the final eligible bar close.

A weekly native bar stores three distinct dates: its W-FRI bucket label, its
first actual VN-Index session, and its last actual VN-Index session. Signal and
close-exit dates use the actual last session; next-open fills use the actual
first session of the following completed bucket. A Friday label that is a
holiday must never be persisted as a fictional execution date.

These semantics extend the proven reference executor from daily bars to either
validated native frame. They do not reuse the old technical-exit AND mask.

## Database history and evaluation split

The evaluator reads only project database OHLCV through the existing retrying
engine path. Raw BIGINT price values remain raw internally and are divided by
1000 only at display boundaries.

All source rows are aligned to valid VN-Index sessions. A ticker whose latest
session differs from VN-Index is live Delisted and is excluded. Mid-term bars
are aggregated only from those aligned sessions into completed W-FRI bars.

Default evaluation range is all valid history available for that ticker. The
user may select a narrower supported date range, but the exact range becomes
evaluation provenance and never changes the published definition ID.

The default chronological split is 65% training and 35% untouched test. The
allowed training ratios are 50%, 55%, 60%, 65%, 70%, 75%, and 80%, based on
completed native bars. Indicator warm-up may read earlier causal bars, but test
trades cannot start before the test boundary. Metrics remain per ticker; no
pooled aggregate may conceal a weak ticker result.

Every fresh operation reloads and fingerprints its full selected source.
Compatible primitive-cache reuse remains a user-visible operational choice;
fingerprint or formula mismatch is a safe cache miss.

## Identity and persistence

### Draft

A mutable draft has a UUID, revision number, display name, description,
horizon, semantic definition, creation/update timestamps in
`Asia/Ho_Chi_Minh`, and state. Draft identity is not trading evidence.

### Published definition

A published ID is `frb2_<SHA-256>` over canonical semantic content only:

- horizon and native timeframe;
- entry operator;
- all predicates, roles, formula revisions, settings, and conditions;
- price and technical exits; and
- min/max hold and execution-semantic revision.

Ticker, history, split, metrics, names, notes, timestamps, cache state, and
display labels do not affect definition identity.

The UI shows the rulebook origin as `Standard` or
`Flexible · FR-<short-id>`. The short ID is an uppercase hash prefix. The
resolver must detect a collision and extend both colliding display prefixes
until they are unique. Persistence, joins, artifacts, validation, and Position
references always use the full hash backstage.

### Evaluation

An immutable evaluation records the full published or draft semantic digest,
ticker, source bounds/fingerprint, calendar fingerprint, native-bar frame,
indicator-build contract, execution contract, split, metrics, completed
trades, warnings, and result state. Editing a draft after evaluation does not
rewrite the old evaluation.

### Storage layout

New writes use a separate namespace under the existing contained Flexible
root:

```text
Flexible-Rulebook/v2/drafts/{draft_uuid}.json
Flexible-Rulebook/v2/definitions/{full_rulebook_id}.json
Flexible-Rulebook/v2/evaluations/{full_rulebook_id}/{ticker}/{evaluation_id}.json
Flexible-Rulebook/v2/cache/primitives/...
```

Draft updates use atomic replace with an expected revision to prevent lost
updates. Published definitions and evaluations are immutable create-or-verify
writes. Corrupt, escaping, mismatched, or unsupported documents are safe
misses/errors and are never partially trusted.

The project `app` directory is bind-mounted by the current Docker Compose
configuration, so this package-relative root is host-persistent without a
Docker change.

## Backtest integration

Collect Signals keeps **Standard** as its default mode.

When Flexible is selected:

- only Published, non-Retired definitions compatible with the selected
  horizon are selectable;
- the user may select one or more definitions;
- each ticker × rulebook evaluates independently and runs sequentially through
  the existing bounded batch workflow;
- no Flexible rule changes or ranks the Standard schema-5 rulebooks;
- an adapter projects Flexible current signals into the shared signal catalog
  and UI contracts; and
- View Signals, Validate Signals, and saved-position references display
  `Flexible · FR-<short-id>` while storing the full immutable ID backstage.

Standard results display `Standard`. Existing Standard artifacts and behavior
remain unchanged. Flexible artifacts use a distinct schema/kind and a strict
adapter; they must not masquerade as Standard schema-5 evidence.

### Flexible Validate Signals mapping

Flexible candidates reuse exactly three existing user-facing classifications:

- `Closely Match`: more than 85% of required supportive facts hold;
- `Nearly Match`: at least 65% and no more than 85% hold; and
- `No Match`: below 65%, or the progressive trend state is Weakening or
  Invalidated. The old Weak category is absorbed into No Match.

The Validate Signals UI exposes only these three options for both origins.
Existing Standard artifacts and scoring remain unchanged; any raw Standard
`weak` value is normalized to `No Match` only in the shared display/filter
projection.

There are no raw distance-to-threshold ratios. A condition contributes a
supportive fact only through its registry-owned causal state. After an entry
cross, support may continue only while the resulting relation remains true,
for example RSI at or above its upcross level or fast MA above slow MA.

For an `ALL` BUY group, every BUY condition is a fact. For an `ANY` BUY group,
the group is one fact that holds when at least one member supports. Every gate
is one additional required fact. The percentage is the count of supportive
facts divided by required facts, calculated from exact Booleans and retained
unrounded for classification.

`can BUY` requires all of the following independently of the monitoring
percentage: a real observed entry event, a Fresh or On-going progressive state,
the definition's registry-owned post-event support expression, and every
required gate still supporting entry. This support projection never fabricates
a second entry event; it only tests whether the observed event remains live.
Nearly Match can never manufacture BUY eligibility.

## Selective replacement and legacy policy

### Retain and refactor

- `contracts.py`: canonical scalar/JSON/hash utilities; replace definition and
  result contracts with v2 lifecycle contracts.
- `history.py`: calendar/listing/quality/fingerprint foundations; make range
  and split configurable and native-timeframe aware.
- `features.py` and `primitive_cache.py`: component cache model; replace fixed
  family branching with registry-driven builders.
- `execution.py`: reference state machine; generalize to validated native bars
  and SELL-OR semantics.
- `metrics.py`: completed-trade metrics only; retire qualification/rank/Top 3.
- `storage.py`: contained atomic helpers; add mutable revisioned drafts and v2
  immutable definitions/evaluations.
- `service.py`: replace discovery/qualification orchestration with draft,
  evaluation, publication, and catalog services.

### Retire after replacement verification

- `activation.py`
- `benchmark.py` and `benchmark_runner.py`
- `cap_benchmark.py` and `cap_benchmark_runner.py`
- `campaigns.py`
- `catalog.py`
- `current_scan.py`
- `discovery_activation.py`
- `runner.py`
- `scope_expansion.py`, `scope_expansion_runner.py`, and
  `scope_expansion_worker.py`
- `search.py`
- `worker.py` and `worker_contract.py`
- old Discover, qualification, scan UI, and their behavior-specific tests

`group_adapter.py` may be retained only as a read-only bridge for database
ticker/group selection if its contract still matches Group Manager; otherwise
it is retired with the old workflow.

### Legacy artifacts and documents

Current v1 definitions, signal sets, ledgers, campaigns, caches, benchmark
policies, and activation pointers remain read-only and invisible to v2. They
are not parsed, migrated, moved, or deleted automatically. Historical design
and plan files receive a clear **Superseded by 2026-09-15 user-authored
redesign** banner. Actual legacy-data deletion requires a separate explicit
destructive approval.

## Error handling and observability

- Invalid drafts show field-level errors and are never evaluated or published.
- No valid database history, invalid VN-Index calendar, Delisted status,
  insufficient native bars, and source changes have distinct user messages.
- One ticker failure does not erase successful ticker results from the same
  request; every item records its terminal state.
- Progress reports source loading, feature resolution, execution, metrics, and
  persistence.
- Atomic writes leave no partially valid document.
- Full internal IDs and trace details remain available in collapsed diagnostics
  and logs, not primary UI labels.

## Performance model

The redesign removes the 123-million-definition search. Runtime is bounded by
selected tickers × selected user definitions rather than an automatic
candidate frontier.

- Load/fingerprint each ticker once per operation.
- Build each unique primitive/settings component once per ticker/source.
- Reuse components across predicates and rulebooks through exact digests.
- Build Boolean masks in memory; never persist masks as truth.
- Group compatible requested definitions by source/timeframe/profile.
- Run ticker batches sequentially to bound memory; expose progress and item
  failures.
- Do not add a vectorized fast executor until reference-parity and benchmark
  tests prove identical completed trades.

## Test and rollout gates

Implementation uses TDD and cannot retire old logic until these gates pass:

1. Registry contract and parameter-bound tests for every exposed family.
2. Golden causal indicator fixtures, including Bollinger and Supertrend.
3. Exact daily and completed-W-FRI timeframe fixtures with no partial week.
4. Predicate tests for state, cross, direction, ALL/ANY entry, ALL gates, and
   ANY exits.
5. Reference-execution fixtures for next-open entry/exit, min hold, gaps,
   stop-first collision, trailing state, timeout, split boundaries, sparse and
   dense signals.
6. Adjustable split and warm-up tests for all allowed ratios.
7. Draft optimistic-update, immutable publish/evaluation, short-ID collision,
   corrupt-file, contained-path, and atomic-write tests.
8. Database/listing/calendar integration tests without changing source rows or
   BIGINT scaling.
9. Builder, Backtest, Library, progress, and error-message UI tests.
10. Standard/Flexible adapter tests proving Standard remains default and
    unchanged, full IDs remain backstage, and View/Validate/Position references
    resolve correctly.
11. Legacy quarantine tests proving v2 neither reads nor mutates v1 artifacts.
12. Focused package suite, affected Backtest/Position suite, and full project
    regression before deleting retired source/tests.

Rollout order is foundation and contracts, registry/features, execution and
evaluation, storage/lifecycle, three-workspace UI, Backtest adapter, then
legacy code retirement and documentation supersession.

## Self-critique and controlled risks

- User-selected rules can overfit. Separate untouched-test evidence, immutable
  evaluations, no automatic tuning, and explicit gross labels reduce but do
  not remove that risk.
- No fixed performance threshold means Published does not mean good. The UI
  must say Published, never Qualified, Profitable, or Tradable.
- Adjustable splits enable cherry-picking. Each evaluation therefore preserves
  its ratio and boundary, and comparisons must not silently mix them.
- Technical indicators are often correlated. The builder must show selected
  roles and a warning for obvious same-family duplication, but it must not
  silently reject a structurally valid user choice.
- Mid-term next-open means the open of the next completed native week's first
  actual trading session, while the signal uses the prior completed week's last
  actual session. W-FRI labels remain bucket identity only. Tests must make
  this mapping explicit, including Friday holidays.
- Bollinger and Supertrend reuse can drift if UI and rulebook calculations call
  different functions. Registry-owned builders and parity fixtures must make
  one formula authoritative.
- Short IDs are presentation only. Collision extension and full backstage
  identity are mandatory.
- Legacy code deletion is high-risk because tests and `__init__` exports are
  extensive. Retirement occurs last, from a proven import/reference inventory,
  not as the first cleanup action.

## Completion definition

The redesign is complete only when a user can create and save a valid draft,
evaluate it against Listed database tickers with reproducible train/test
evidence, publish an immutable version, select it from Collect Signals as a
Flexible rulebook, view and validate its signals with an unambiguous short ID,
and preserve a full immutable Position reference—all while Standard remains
the default and its existing regression suite remains unchanged.
