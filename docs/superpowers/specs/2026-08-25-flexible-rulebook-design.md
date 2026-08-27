# Flexible Rulebook Design

**Date:** 2026-08-25  
**Status:** Approved design, amended 2026-08-26; implementation not started.  
**Scope:** Independent daily Swing research subsystem for portable long-only technical rulebooks.

## Goal, scope, and non-goals

Flexible Rulebook searches historical daily price data for one or more portable
rulebooks that meet demanding gross completed-trade evidence on a specific
ticker. It gives research recommendations only. It never sends an order,
creates/changes/closes a Position, or controls actual BUY/SELL trading.

Phase one supports:

- BUY/LONG only. One complete simulated trade is one BUY then one SELL.
- Earliest causal daily-bar entry; no intraday or real-time support.
- One or more BUY indicators, zero or more gates/filters, zero or more
  technical SELL indicators, optional ATR(14) price exits, fixed min_hold=3, and
  a definition-owned inclusive max hold from 4 through 64 bars.
- Automatic AND-only candidate combinations from a finite catalog.
- User changes to catalog-backed indicators/settings; adding an entirely new
  technical indicator requires code and tests.
- Discover from a source ticker, qualify same immutable rulebook independently
  on other tickers, then scan current named Group members.

Phase one must not alter Baseline/V3, schema-4 artifacts, Backtest Lab,
positions, validation, database schema, Docker, dependencies, or existing
V3 jobs. The only permitted V3 code reuse is a Flexible-owned adapter around
backtest_engine.data_quality.load_ticker_history. Named Group membership is
consumed by a Flexible-owned read-only parser of the existing Group JSON schema,
not by importing V3 result-store/group-resolution helpers. A Baseline/Flexible
selector inside Backtest is a later, separately approved phase.

Flexible owns its history-quality policy. It does not import V3 validation or
audit helpers: malformed required columns, date order/duplicates, non-finite or
non-positive OHLC, and negative volume are `invalid`; an OHLC ordering mismatch
above 1% of a bar's maximum OHLC or an adjacent close discontinuity of at least
15% is `display_only`; warnings alone remain usable. Every load requests the
calendar 15-year window ending at the frozen requested as-of date (29 February
maps to 28 February in the earlier year). `EvidenceSourceAnchor` is a
Flexible-owned immutable history contract with ticker, exact requested/actual
bounds, historical as-of, and ordered-prefix fingerprint; its durable storage
arrives with Flexible storage, not V3.

A history is a full calendar window when its first native bar is no more than
seven calendar days after the requested 15-year start. This admits ordinary
weekend/holiday openings without treating a materially later listing as 15-year
coverage. Otherwise its one native-bar chronological 65%/35% split applies.
`trade_dates_belong_to_partition()` owns only the date-boundary predicate;
Task 4 proves that each executor partition starts flat.

Every visible result says **Exploratory — gross** and labels training as
in-sample or test as out-of-sample. No UI/artifact copy may say profitable,
tradable, or statistically certified. Fees, tax, and slippage remain outside
the product.

A zero-result run is valid. No threshold may be weakened or search expanded
after results merely to produce a signal.

## Identity and portability

| Object | Identity | Rule |
|---|---|---|
| RulebookDefinition | rulebook_id | Portable canonical definition; excludes ticker, history, metrics, and result. |
| CatalogRevision | catalog_hash | Exact available predicates/settings used for a definition. |
| CandidateSpace | candidate_space_hash | Seed-free, lazily indexable canonical domain; hash includes catalog and mapping revision. |
| FrontierAssignment | assignment_hash | Discovery-only seeded traversal window over one CandidateSpace. |
| FeatureSnapshot | raw_history_fingerprint | Fresh validated ordered OHLCV source, exact source bounds/as-of, and quality revision. |
| FeatureBuildContract | feature_build_contract_hash | Frozen causal feature algorithm, warm-up/quality, numeric, raw-scale, and cache-schema semantics. |
| PrimitiveComponent | primitive_key | One reusable family/settings array for FeatureSnapshot plus FeatureBuildContract. |
| FeatureProfile | feature_profile_hash | Canonical requested set of primitive instances for a rulebook or definition collection. |
| FeatureBundle | feature_bundle_hash | Request-scoped assembled union of validated PrimitiveComponents; never evidence truth. |
| FeaturePlan | feature_plan_hash | Frozen ordered primitive requirements for one source/build-contract/profile union. |
| FeatureResolutionReceipt | receipt_id | `frpr_<SHA-256 of plan plus ordered PrimitiveKey/component-digest pairs>` used before a campaign evaluates a slot. |
| Evaluation | rulebook_id plus ticker plus source/split/build-contract fingerprint | One immutable historical train/test result. |
| SignalSet | signal_set_id | Detailed self-contained evidence for an evaluation. |
| Campaign | request_hash | Idempotent frozen discovery, qualification, or current-scan request. |

rulebook_id is frb_<SHA-256 of canonical semantic definition>. Any change to
predicate, setting, catalog, execution, split, or qualification threshold makes
new immutable evidence; split and threshold changes affect evaluation identity,
not a definition hash unless they are semantic execution inputs. A rulebook that
fails VCB remains reusable and may qualify FPT; no ticker result can delete or
globally reject it. A FeatureBuildContract change also creates new evaluation
evidence while preserving portable rulebook definition identity.

Discovery seed, source ticker, canonical candidate index, assignment window,
campaign, history, metrics, and result never contribute to rulebook_id. They
are reproducibility provenance for an evaluation, not rulebook semantics.
Primitive cache path, age, hit/miss state, and the user's reuse/recalculate
choice are operational provenance only: they never change rulebook_id,
evaluation identity, request_hash, candidate assignment, rank, or selection.
FeatureBuildContract is semantic evaluation provenance and does enter evaluation
and request identity; it is never silently substituted on Resume or Continue.
FeaturePlan is a deterministic derived execution input, never an editable user
choice. Its receipt is written before the first candidate commits so a resumed
or continued worker proves it is evaluating the same component bytes, not merely
the same named indicator revision.

Display aliases are non-authoritative. Immutable animal pool
animals-50-v1 is:

~~~
Aardvark, Albatross, Antelope, Badger, Bear, Beaver, Bison, Buffalo, Camel,
Capybara, Cheetah, Cobra, Crane, Dolphin, Eagle, Elephant, Falcon, Fennec,
Fox, Gecko, Giraffe, Hawk, Heron, Jaguar, Koala, Leopard, Lion, Lynx,
Meerkat, Mongoose, Otter, Owl, Panda, Panther, Penguin, Puma, Raven, Rhino,
Seal, Shark, Sloth, Tiger, Tortoise, Viper, Walrus, Whale, Wolf, Wombat, Yak,
Zebra
~~~

Panda-Lion is selected deterministically from the definition hash among 1,225
unordered animal pairs. It can collide and may change display policy; it is
never an equality key, artifact path key, or security boundary. Show short/full
rulebook hash beside it when ambiguity matters.

## Catalog and flexible rule grammar

Flexible accepts catalog configuration, not free-form Python or formulas.
Automatic search takes a finite submitted catalog snapshot. User edits make a
new catalog revision; an automatic run never secretly tunes a numeric setting.

~~~
BUY            = AND(one_or-more BUY predicates)
ENTRY          = BUY AND zero-or-more gates/filters
TECHNICAL_SELL = AND(one-or-more selected technical SELL predicates), or absent
PRICE          = zero-or-more ATR(14) stop/target/trailing exits
EXIT           = TECHNICAL_SELL OR PRICE exit OR mandatory timeout
~~~

Timeout is always present; min_hold is exactly 3; max_hold is an explicit
integer in [4, 64]. A manually composed rulebook uses the same grammar and
same qualification pipeline as an automatic candidate. Every enabled ATR stop,
target, or trailing multiplier is finite and strictly greater than zero. Every
rulebook with an ATR price exit owns fixed `atr-wilder-v1` ATR(14) in its
canonical definition; a no-price-exit rulebook owns no ATR primitive.

Catalog revision 1 has only these causal families:

| Role | Family | Causal input |
|---|---|---|
| BUY | EMA bullish cross | current/prior completed EMA values |
| BUY | RSI upcross | current/prior completed RSI values |
| BUY | prior-N-bar high breakout | current close and strictly prior highs |
| Gate/filter | EMA trend-up | completed close/EMA values |
| Gate/filter | relative volume | current volume and prior-only volume average |
| Gate/filter | ADX minimum | completed ADX |
| Technical SELL | EMA bearish cross | current/prior completed EMA values |
| Technical SELL | RSI downcross | current/prior completed RSI values |
| Technical SELL | prior-N-bar low breakdown | current close and strictly prior lows |
| Price SELL | ATR(14) stop, target, trailing stop | frozen signal ATR and prior state |

Alligator stays Baseline-only for automatic Flexible discovery in phase one.
Bollinger, Stochastic, MACD, OBV, Parabolic SAR, and future families require
a new catalog revision with causal tests and search-cost review.

The UI exposes allowed finite settings by family/role; it must not expose an
unbounded arbitrary formula field. CandidateSpace is canonically indexed over
non-empty AND subsets of submitted BUY instances, optional submitted
gate/filter instances, optional non-empty AND subsets of technical SELL
instances, and submitted price-exit/timeout variants. Discovery visits only
frozen FrontierAssignment slots; it never enumerates or materializes a canonical
prefix. A FeatureProfile resolves each required causal primitive component once
per ticker/source snapshot, reusing an already validated component or
calculating only the missing one; combinations compose their entry/technical-exit
masks lazily.

### Swing Catalog Revision 1

Catalog v1 is ordered fast-to-slow and caps automatic conjunctions at two BUY
predicates and two gates/filters. Fixed Wilder ATR(14) is not a search variable.
EMA BUY/gate pairs: `(3,8)`, `(5,13)`, `(5,21)`, `(8,21)`; RSI periods:
`5/9/14`, levels: `50/52/55`; breakout lookbacks: `10/20/40`.
Relative-volume windows: `5/10/20`, minima: `1.10/1.20/1.30`; ADX minima:
`15/20/25` on fixed Wilder ADX(14). Technical SELL mirrors BUY EMA/RSI/breakout settings. Timeout:
`10/15/22/30`. Frontier assignment remains seeded per ticker; this catalog order
never makes outcome data part of scheduling.

Automatic ATR price exit has one finite pair: static stop `2.0×` ATR(14) and
target `3.0×` ATR(14); trailing is absent. No-price-exit remains an allowed
automatic variant under the optional price-exit grammar.

Catalog entries distinguish a reusable **feature spec** from a rulebook
**predicate condition**. Period/lookback/window settings belong to the feature
spec and enter PrimitiveKey; conditions such as RSI upcross level, ADX minimum,
or relative-volume threshold remain in the rulebook and create in-memory masks.
Changing only a condition therefore creates new definition/evidence but reuses
the same compatible cached base component.

## Causal execution contract

Prices remain raw BIGINT-derived values internally. UI output converts only at
the existing k VND boundary.

1. A BUY predicate true at completed close t queues BUY at raw open(t+1). If
   next bar is absent, it produces no completed trade.
2. Only one flat-to-flat position exists. BUY signals while open are ignored.
   A signal observed on an exit bar may queue next-bar entry.
3. For entry bar E, exits are prohibited on E, E+1, and E+2. First possible
   exit is E+3. Price-exit hits in those blocked bars are ignored; they never
   create a latent or backfilled exit.
4. A technical SELL true at close t queues raw open(t+1) only when that fill
   bar is within E+3 through the inclusive deadline. Therefore technical SELL
   signals at close E or E+1 are discarded, a signal at close E+2 queues raw
   open E+3, and a deadline-close signal cannot queue a post-deadline exit.
   A valid queued technical exit executes without recheck and has priority at
   its eligible raw open.
5. Definition-owned ATR(14) is frozen on BUY signal bar. Raw OHLC and raw-open fills remain integer
   DB units, while computed ATR thresholds retain full precision through
   comparison, fill, and return calculation. At an eligible bar without a
   queued technical exit, a gap through any enabled price threshold fills at raw
   open. Otherwise an intrabar threshold fills at its threshold. For a long
   position, the effective stop is the tighter enabled stop,
   max(static_stop, trailing_stop); if a stop and target both hit intrabar,
   stop-first applies.
6. Trailing high_water starts at entry price. Its threshold for bar t uses
   highs/ATR state through t-1 only, including highs accumulated during the
   blocked minimum-hold bars. Current high cannot raise the stop before current
   low is tested.
7. With max_hold=64, deadline is E+63. On deadline: queued technical exit at
   open, then price exits, otherwise raw-close timeout. A technical signal from
   E+62 may queue the deadline open; one observed at deadline close cannot.
8. Completed gross return is (exit_price / entry_price - 1) * 100. A win is
   strictly return > 0. No costs, tax, slippage, sizing, liquidity, or
   corporate-action adjustment is modeled.

## Split, qualification, rank, and sensitivity

Use latest available completed daily bars in a frozen history snapshot. A full
as-of-anchored 15-calendar-year selection uses a calendar cutoff exactly five
calendar years before as-of: test starts at the first available native bar on
or after that cutoff, and training ends at the preceding native bar. Never
invent a non-trading boundary date. Shorter usable history uses chronological
native-bar 65% training / 35% test. Persist requested cutoff, exact native
bounds, split method, row counts, and raw OHLCV fingerprint.

Build indicators once on full history. Test may use only earlier training bars
as causal indicator warm-up. Each partition starts flat:

- Training keeps a trade only when signal, entry, and exit all precede test.
- Test keeps a trade only when signal and entry are on/after test start and
  exit is inside test.
- Crossing/incomplete trades are dropped. Training state never blocks a test
  entry.

Persist unrounded n, win_rate, total_return_pct, mean_return_pct, and
unannualized per-trade Sharpe. Sharpe is null for fewer than two finite returns
or zero sample deviation. NaN or infinity is invalid metric data, never a rank
value.

Each immutable evaluation evidence record also carries typed ordered
`training_trades` and `test_trades` completed-trade tuples. They are evidence,
not definition identity: they never enter `rulebook_id`. Their counts must match
their partition metrics. Timing comparison reads only these tuples; it never
reconstructs intervals from aggregate metrics or performs an artifact lookup.

A threshold-qualified exploratory result needs all values in both training and
test:

~~~
n >= 12
win_rate >= 65.0
mean_return_pct >= 15.0
~~~

n >= 12 is an observation-count floor, not statistical certification. For a
10-year/5-year split, test needs at least 2.4 completed trades per year. A zero
result is valid. mean_return_pct is the unrounded arithmetic mean of completed
gross trade returns, never total or compounded return.

Audit/data-ineligible results remain visible but cannot become BUY setups.
Rank all threshold-qualified candidates by training-only, unrounded values:

1. win_rate descending;
2. mean_return_pct descending;
3. finite Sharpe descending, then null Sharpe;
4. lexical rulebook_id.

Test never selects/ranks/tie-breaks. It remains independent out-of-sample
evidence for eligibility and display.

Sensitivity compares two different rulebook definitions in one explicit
selection scope: identical ticker, raw source fingerprint, split bounds, and
execution revision. A mixed scope is invalid. It never compares a rulebook's
training trades with its own test trades. Compare training with training and test
with test only. Canonicalize left/right by lexical rulebook_id and sort completed
trades by `(entry_bar_ordinal, exit_bar_ordinal, trade_id)`. Holding intervals
are inclusive `[entry_bar_ordinal, exit_bar_ordinal]`; use this exact two-pointer
walk:

~~~
if left.exit_bar_ordinal < right.entry_bar_ordinal: mark left unmatched; advance left
elif right.exit_bar_ordinal < left.entry_bar_ordinal: mark right unmatched; advance right
else: pair the intervals; advance both
~~~

Thus equal endpoints overlap. Signal bars determine earlier/tie evidence only
after interval pairing. Persist both rulebook IDs, pairing-algorithm revision,
partition, paired/win/loss/tie/unmatched counts, median absolute trading-bar
lead among non-ties (null when no decisive pair), and the exact overlap numerator
and denominator plus a display ratio.

For Top 3 distinctness, use **training timing only**. Let `paired_count` be
the training pair count and `training_n` each candidate's completed training
trade count. Define:

~~~
overlap_numerator = paired_count
overlap_denominator = min(left.training_n, right.training_n)
hard near-duplicate iff 4 * overlap_numerator >= 3 * overlap_denominator
~~~

The denominator is non-zero because threshold-qualified candidates have
training `n >= 12`. Signal lead, wins/losses/ties, test timing, and test metrics
are displayed evidence only; none changes the duplicate predicate.

Selection policy `timing-distinct-top3-v1` greedily walks the already ranked
training list. It accepts the highest-ranked candidate as the representative,
then accepts a later candidate only if it is not a hard near-duplicate of **any**
accepted representative (every comparison must be `<0.75`). A rejected candidate remains threshold-qualified,
persisted, portable, and available for cross-ticker qualification; it records
`timing_near_duplicate`, its blocking representative, and pair evidence. If it
matches more than one representative, record the greatest overlap ratio, then
the earlier training rank, then lexical rulebook_id. Training rank chooses the
representative; the policy hard-stops at three and never backfills duplicates.
Fewer than three means exactly that fewer hard-distinct qualified rulebooks
were found in the assigned search. Test pairwise sensitivity is persisted only
as evidence for the selected representatives.

Do not materialize an all-qualified pairwise matrix. The greedy pass compares a
candidate to at most the three selected representatives and memoizes only those
training pair records; test compares only final selected pairs (at most three).
This keeps distinctness bounded while preserving the exact policy.

## Discovery, reusable features, test freeze, and artifacts

Training discovery can retrospectively use completed outcomes to identify
candidates. It never introduces future data into a predicate.

### Fresh source and indicator-cache protocol

Every new Discover, Qualification, and Current Group BUY Scan first reloads its
bounded raw OHLCV source from the database, runs data-quality validation, and
hashes the complete ordered `ticker/date/open/high/low/close/volume` sequence.
Date/count/max-date checks alone are forbidden because a same-date historical
correction is possible.

A frozen FeatureBuildContract canonically contains the causal feature algorithm
revision, cache schema, warm-up policy, quality policy, numeric runtime revision
(including NumPy/pandas behavior and Flexible numeric implementation), raw price
scale, and (when enabled) append-extension algorithm/state revisions;
it deliberately excludes requested primitive instances. Its
hash belongs to Evaluation, SignalSet, and Campaign identity. A PrimitiveKey is SHA-256 of the
FeatureSnapshot identity, FeatureBuildContract hash, and exactly one primitive
family/settings instance (for example `rsi/14` or `ema/13`). Each persisted
PrimitiveComponent manifest records that canonical key, a canonical component
digest over every numeric array and causal state value, dtype/shape/date order,
and successful Asia/Ho_Chi_Minh calculation timestamp. Recalculating the same
key must reproduce the same component digest; a mismatch is
`FEATURE.NONDETERMINISTIC_BUILD`, leaves the old cache intact, and writes no
new evaluation under that contract.

FeatureProfile is a requested set of primitive instances, not one all-or-nothing
cache key. A request-scoped FeatureBundle assembles validated components. Thus a
later combination/profile that adds EMA(21) reuses compatible cached RSI(14),
EMA(13), etc., and calculates only the missing component. Persistent cache never
stores raw source truth, candidate masks, exit plans, trades, metrics,
qualification, ranking, or test results. Those remain in-memory and are rebuilt
for each evaluation.

A persisted component contains a parameterized base series and causal auxiliary
state, not a rulebook condition. For example, cached RSI(14) is reused by every
RSI threshold/cross predicate; threshold masks are composed only in memory. This
keeps disk reuse broad without turning a cached predicate result into evidence.

The initial implementation uses a full rebuild for a newly appended/corrected
source fingerprint. An optional `append_extension_v1` may later derive a new
component from a verified old-prefix component only when: fresh raw OHLCV proves
the old ordered prefix exactly; the frozen FeatureBuildContract declares a
stream-state schema for that primitive; and its output digest matches a full
rebuild on deterministic fixtures and representative benchmark data. It always
writes a new PrimitiveKey/receipt and falls back to full rebuild on any mismatch.
The parity proof is a test/benchmark enablement gate, not a full rebuild repeated
inside every production append extension.
It is never allowed for a correction, changed contract, missing stream state, or
solely because a cache is young. Thus the optimization can improve append-heavy
workloads without weakening fresh-source evidence or continuation reproducibility.

The UI preflight returns fresh FeatureSnapshots and a per-build-contract
component CacheOffer; their source fingerprints and FeatureBuildContracts enter
the request before a campaign exists. Every initial invocation, retry, Resume,
and Continue uses one common `verify_frozen_source()` step before any cache load
or ledger/cursor advance. It fresh-loads the frozen bounds, validates the exact
source fingerprint and FeatureBuildContract, and then remeasures every component
age. If source differs it returns `source_changed`; if the required historical
feature revision is unavailable it fails safely with
`FEATURE.REVISION_UNAVAILABLE`; neither may apply an old cache choice or advance
the cursor. If source/contract match, a Resume/Continue rebuilds missing/expired
components from the frozen source without a prompt. For a Current Group BUY Scan
this second preflight covers every frozen member before any member evaluates, so
a changed member blocks the all-or-nothing common-as-of scan. Qualification
records only the changed target and continues eligible independent targets.

Before a ticker evaluates any discovery slot, qualification rulebook, or current
scan pair, the coordinator atomically persists the derived FeaturePlan and a
FeatureResolutionReceipt containing every resolved PrimitiveKey and component digest.
Resume and Continue re-resolve that exact plan after frozen-source verification;
cache eviction is acceptable only if a rebuild reproduces every receipt digest.
A missing historical build contract, missing plan, or any digest difference is
`FEATURE.REVISION_UNAVAILABLE` or `FEATURE.NONDETERMINISTIC_BUILD` as applicable,
with no cursor advance or mixed evidence.

For a new operation, one or more verified required components at age `<= 24
hours` causes an explicit choice: **Reuse verified indicator cache** (reuse valid
components and calculate only missing/expired ones) or **Recalculate now**
(calculate every required component). Completion timestamps and age comparison
use Asia/Ho_Chi_Minh time. Exact 24 hours is in the prompt branch. The worker
remeasures age after source verification: a component that crossed 24 hours or
became negative/clock-skewed rebuilds automatically without a second prompt. If
no required component is fresh, all are missing/expired/mismatched/corrupt, a
temporary file/lease is invalid, a write fails, or free-space reserve would be
violated, build the affected component uncached; cache failure is never data
failure or no-result. A cache read uses `allow_pickle=False`; wrong schema/key/
digest/dtype/shape/date order is a safe miss. Cache choice is operational and
never changes semantic identity.

If `append_extension_v1` is separately enabled, a `<=24h` old component may be
offered under **Reuse verified indicator cache** only after the exact-prefix and
stream-state checks above; **Recalculate now** always forces a full build. A
failed extension falls back to a full build and reports that fallback, never to a
stale component or data failure. An age over 24 hours never offers extension.

### Frozen stratified discovery and untouched test

1. Build a seed-free canonical CandidateSpace from submitted catalog. Its
   candidate_space_hash includes catalog plus candidate-space mapping revision;
   it is lazily indexable and never materialized as all definitions or IDs.
2. Before any candidate outcome is read, freeze a discovery-only
   FrontierAssignment with a structural stratification revision, non-empty
   stratum quotas, global slot order, attempt_count, and candidate admission
   deadline. Strata cover BUY predicate count/family, gate count, technical-exit
   configuration, ATR price-exit configuration, and max-hold bucket. Quotas are
   pre-outcome round-robin allocations across non-empty strata; no metric,
   source outcome, cache warmth, or test value changes them.
3. Within each stratum of size `N_i`, local slot `s` maps to canonical member
   `(a_i*s + b_i) mod N_i`; `a_i`/`b_i` derive only from frontier_seed,
   candidate-space hash, source ticker, stratum ID, and frontier algorithm
   version, with `gcd(a_i, N_i)=1`. Persist all coefficients and quotas. No
   candidate repeats before its stratum is exhausted. This samples broad
   structural regions without claiming an exhaustive or global-best search.
4. Run only frozen slots. Safe early rejection may remove an invalid canonical
   definition, exact duplicate predicate configuration, or a training entry-mask
   upper bound below 12. Partial returns, partial Sharpe, test values, and
   outcome-driven "domination" may never prune or reallocate the schedule.
5. A candidate passing all training thresholds is frozen immediately and run once
   on untouched test before the next training slot. Test work is reserved in the
   same immutable schedule and can never expand/tune/reorder later training
   slots. Both-side passes enter training rank and timing-distinct selection.

Different source tickers use different reproducible traversals, but overlap
across tickers is permitted: a definition may fail VCB and work FPT. Assignment
derivation never uses source fingerprint, training outcome, test values, or
metrics. Ordinary Discover uses visible stable `frb-default-seed-v1`; an exact
duplicate opens existing evidence. Only explicit New Sample creates and shows a
new persisted seed before submit.

Changing catalog, definition, FeatureBuildContract, execution, split, threshold,
selection policy, history fingerprint, structural stratification, or fixed
time/candidate budget creates new evaluation/campaign evidence; never overwrite
or merge prior evidence. A timing/cache operational event alone does not.

`resolve_flexible_root()` returns one contained absolute output root and passes it
unchanged to page, coordinator, worker, manifest, and storage. Development
default is the absolute `app/Flexible-Rulebook` directory derived from the
Flexible package location, never process CWD:

~~~
app/Flexible-Rulebook/
  cache/v1/primitives/pc_<primitive-key>.npz
  rulebooks/frb_<definition-hash>.json
  campaigns/<campaign-id>/manifest.json
  campaigns/<campaign-id>/items/<ordinal>-<ticker>.json
  campaigns/<campaign-id>/features/<ticker>-<feature-plan-hash>.json
  campaigns/<campaign-id>/ledger/<ticker>/chunk-<n>.json
  campaigns/<campaign-id>/selections/<selection-snapshot-id>.json
  signal-sets/frb_<definition-hash>/<ticker>/<set-id>.json
  current-scans/<campaign-id>/<ordinal>-<ticker>.json
~~~

`cache/` is not a rulebook library, signal-set, download, or evidence-discovery
input. It uses a contained hash-only path, same-directory temporary file,
flush/fsync/atomic replace, and an immutable-key lease. A reader sees only a
validated old/new complete PrimitiveComponent; stale lease recovery has a bounded
wait then computes uncached. Phase one has one global worker and no destructive
cache eviction. Before write, require `shutil.disk_usage(root).free >=
component_bytes + 512 MiB`; otherwise skip the cache write and continue
uncached. Production durability of both cache and evidence remains unresolved
until a persistent output mount is separately approved; this design does not
change Docker. The page reports **Persistence: unverified development storage**
until a durable root is separately approved, and may promise reuse only while
that storage survives.

Panda-Lion/set-of-signal-01.json is display-only projection, never canonical
storage. Each schema_version 1 signal-set JSON is self-contained: immutable
definition/catalog/execution, ticker/source fingerprint/quality, split,
train/test metrics, qualification, causal signals/trades, exit reasons/raw
prices/returns, FeatureBuildContract, EvidenceSourceAnchor, campaign hash, engine
revision, and Asia/Ho_Chi_Minh timestamps.
Persist detailed trades only for qualifying or
explicitly saved sets; compact ledgers preserve every rejected/evaluated
definition. Each ledger row persists candidate-space hash/size, canonical index,
global/stratum slot, assignment hash/version/coefficients/quota, seed
fingerprint, and immutable candidate outcome.

Top-3 membership is not immutable signal-set metadata. Every terminal discovery
request writes an immutable campaign-chain **SelectionSnapshot** under its own
campaign. It contains selection scope, selection-policy and pairing-algorithm
revisions, an input ledger/evaluation digest, exact pair numerators/denominators,
training rank, representative/blocker relations, and selected IDs. A linked
Continue re-evaluates selection from all committed qualified evaluations in its
parent chain and writes a new snapshot; it never edits parent signal sets,
ledgers, or snapshots. A snapshot records one explicit scope state:
`partial_window` when an assigned window stopped before all of its slots commit,
`complete_assigned_window` when its frozen assignment window completed but the
CandidateSpace remains unsearched, or `frontier_exhausted` only after the entire
CandidateSpace completed without error. The first two are never final/global
claims. The Library may show the latest chain snapshot while retaining every
historical snapshot.

A discovery manifest persists the runtime budget/deadlines, elapsed work time,
attempted slot ranges, next_slot, uncommitted slot if interrupted, and
unsearched count, never a materialized list of unsearched IDs. The slot stream
is committed contiguously; therefore `chain_attempted_count == next_slot` only
when that invariant verifies, otherwise the manifest is failed. Its threshold
funnel persists frontier size, frozen quota, attempted count, training n/win/
threshold passes, frozen/tested counts, test n/win/threshold passes,
threshold-qualified count, timing-duplicate count, and selected hard-distinct
count plus the immutable SelectionSnapshot ID. It also records cache provenance
and timing diagnostics without making them semantic identity.

Use temporary file, flush, fsync, atomic replace. Write ticker artifact before
manifest checkpoint. Resume reconciles verified orphan artifacts; missing or
corrupt claimed artifact is failure, never success.

## Campaigns and current Group BUY Scan

Separate operation types:

1. Discover portable definitions on source ticker.
2. Cross-ticker qualify frozen definitions on target ticker(s).
3. Current Group BUY Scan of already-qualified definition × ticker pairs.

Campaign states are queued, running, cancelling, cancelled, blocked,
interrupted, completed, completed_with_errors, and failed. `blocked` means
shared DB/storage outage, not 200 false ticker errors. `interrupted` is a stale
lease/dead worker and is resumable. `failed` is a request/manifest invariant
failure.

Historical ticker state is queued, running, retry_pending, qualified,
no_qualified_candidate_within_budget,
time_budget_exhausted, frontier_exhausted_no_qualified_candidate,
data_ineligible, source_changed, failed, cancelled, or
not_started_budget_limited. `time_budget_exhausted` means the fixed wall-clock
window ended before the frozen attempt quota or frontier was completed; it is
never relabeled `no_qualified_candidate_within_budget`. The frontier-exhausted
state is allowed only after every candidate in the frozen CandidateSpace has a
non-error terminal training outcome and every frozen test candidate has a
non-error terminal test outcome; otherwise budget/error state remains.
Current scan state is
current_setup_found, no_current_setup, no_historically_qualified_rulebook,
blocked_common_as_of, source_changed, data_stale, data_invalid,
current_evaluation_failed, cancelled, or not_evaluated.

One coordinator owns manifest writes. Workers write only isolated item artifacts
or return result. Retries apply once to classified transient DB/I/O failures,
not invalid data/settings/candidate rejection. Cancellation is cooperative at
safe checkpoint. A heartbeat/lease prevents duplicate resumes.

request_hash canonically includes operation, frozen ordered members, exact raw
source fingerprint/bounds/as-of and history/split, catalog/engine revision,
definition hashes, FeatureBuildContract hashes, budgets, execution,
thresholds, runtime budget, structural-stratification revision/quotas, and
timing-distinct selection policy. Discovery additionally includes
candidate-space hash, candidate-space algorithm version, frontier algorithm
version, frontier_seed, source ticker, start_slot, and attempt_count.
Qualification and current scan reject frontier-assignment fields. It excludes
timestamp, elapsed time, cache event/path/age/choice, progress, retry, and
cancel fields. Source snapshot identity is hashed; only cache operational
metadata is diagnostic. Same running request attaches; same completed request
opens evidence.

**Resume** restarts the same interrupted/blocked/cancelled execution window
from its persisted checkpoint and may not change its assignment. **Continue**
is a linked new discovery request only after its parent has no unresolved
training slot or frozen test candidate. It retains every parent semantic field:
ticker, raw source fingerprint/snapshot bounds, catalog/candidate-space/mapping,
seed, stratification/quotas, execution, split, thresholds, selection policy,
FeatureBuildContract, and runtime/candidate budget. It changes only parent link,
start_slot/next frozen window, and execution-window identity; it must not read
editable current-page values. A user-triggered **Repeat latest** is instead a
fresh operation on a fresh source snapshot and follows the normal cache policy.

Every initial invocation, retry, Resume, and Continue calls the same
`verify_frozen_source()` protocol from the cache section. A source mismatch
becomes `source_changed` with no ledger/cursor advance; matching source rebuilds
missing/expired components under the frozen FeatureBuildContract without a
prompt. A catalog, candidate-space, assignment, execution, split, threshold,
selection-policy, or FeatureBuildContract mismatch is a manifest-invariant
failure: mark campaign failed, never merge evidence, and require a new campaign.

Current Group BUY Scan snapshots named Group membership read-only. It must not
use V3 N/A membership or any group-assignment helper. Preflight requires every
member have the same exact latest completed bar date. Mismatch blocks entire
scan as blocked_common_as_of, lists laggards, and evaluates none; never use
per-ticker dates or an older fallback date. After that date preflight, it fresh
loads/fingerprints each member before cache resolution. Requested definitions
are grouped by their immutable FeatureBuildContract and required primitive union;
the manifest persists a cache-decision map keyed by `(ticker,
feature_build_contract_hash)`. One table offers Reuse valid components/calculate
missing or Recalculate all per build contract; expired/missing/mismatched/corrupt
components rebuild automatically. It never prompts serially per ticker or uses
cache state to return no setup. After the all-member source recheck, it persists
one FeaturePlan/FeatureResolutionReceipt per member/build contract before any
current pair evaluates; a receipt mismatch blocks the full common-as-of scan.

current_setup_found requires exact historically qualified definition × ticker,
compatible FeatureBuildContract, valid/audit-eligible current source, all
latest-bar causal BUY predicates true at frozen common as-of, and next session
open model. Every historical SignalSet persists an EvidenceSourceAnchor: exact
requested/actual source bounds, historical as-of, and an ordered raw OHLCV prefix
fingerprint over that evaluated range. Before current evaluation, reload and hash
that exact old range. An appended current bar is append-safe only when the stored
prefix fingerprint matches exactly; it preserves old evidence and displays its
qualified-through/evidence age. Any correction, missing old range, or moving
rolling-window boundary that prevents prefix proof requires requalification.
no_current_setup occurs only after all qualified definitions ran successfully
and none triggered. Unavailable/stale/invalid/unqualified/cancelled/failed rows
are never relabeled no setup.

## Performance, UI, and acceptance

Search is combinatorial. A sample broad grid can exceed 123 million definitions
and per-bar timeout variants can exceed 1.2 billion. Exhaustive discovery is
prohibited for every ticker, not merely 100–200 ticker Groups. The observed
existing V3 path is not a Flexible benchmark and must not be extrapolated into a
candidate promise or capacity claim.

### Per-ticker time and execution budget

Every historical ticker execution has a normal wall-clock limit of **17,700
seconds (4 hours 55 minutes)**, measured by `time.monotonic()` from fresh source
preflight/cache resolution until its terminal item artifact and manifest
checkpoint are durable. Queue time is displayed separately and excluded. The
frozen request uses:

~~~
candidate_admission_deadline_seconds = 16_200  # 4h 30m
normal_terminal_deadline_seconds    = 17_700  # 4h 55m
outer_worker_watchdog_seconds       = 18_000  # only runaway cleanup
~~~

At 4h30 no new candidate begins. An in-progress candidate/test checks the
monotonic deadline at bounded executor checkpoints and either commits its
complete atomic outcome or leaves its slot uncommitted for exact resume. The
worker writes a normal `time_budget_exhausted` item by 4h55. The 5-hour watchdog
is a fail-safe only, never a success path or a reason to skip a slot. Source
load, quality/fingerprint, cache load/build/write, training, frozen test,
timing-distinct selection, artifact writes, and retries all count. A Group runs
sequentially with one worker; the UI displays the worst-case aggregate as the
sum of its frozen per-ticker windows.

Candidate count is a fixed request input selected by a benchmark-backed
DiscoveryPolicy before work. Cache warmth may reduce elapsed time but must not
increase slots, quotas, tests, or the request hash. At deadline the result says
which slots/strata were searched, never global best/no outperformer. Only a
fully exhausted error-free CandidateSpace may state it found no qualified
candidate in that catalog. The policy must derive its cap from cold p99 cost of
a maximal slot (training, an eligible frozen test, selection/checkpoint, and
write), not a training-only mean. It subtracts cold p99 source/feature preflight
from the 4h30 admission window, budgets every assigned slot as if it needs that
maximal path, and retains the 25-minute terminal reserve. A p99 cap is invalid
without at least 100 complete maximal-slot samples and their recorded sample
count.

### Reuse architecture and benchmark proof

Each ticker holds raw integer OHLCV arrays plus one FeatureStore. Parameterized
primitive arrays/causal auxiliary state are calculated once; in-memory predicate
Boolean masks and candidate masks are lazy AND compositions. Candidate loops
must not issue a DB call, deep-copy a DataFrame, reset/reindex pandas data, or
allocate a candidate-by-bar matrix.
The Flexible state executor consumes raw NumPy arrays and checks deadline only
at bounded chunks, not via a high-overhead callback on every operation.

The reference daily state machine is authoritative. A benchmark-gated
event-driven fast path may enumerate true entry indices and reuse an exact
technical/price exit plan for the same source, receipt, masks, and exit
configuration, but it may not skip a bar that can affect a fill or trailing
state. It is enabled only after deterministic trade-for-trade parity with the
reference engine, including raw fill price, dates, exit reason, and return; any
unsupported configuration or parity failure falls back to the reference path.

An in-memory byte-bounded LRU (initial ceiling 128 MiB) may retain composed
masks, exit plans, and exact execution memo entries for the current ticker only.
An execution memo key includes source fingerprint, FeatureResolutionReceipt
digest, partition bounds, entry-mask digest, technical-exit mask digest,
price-exit configuration, min/max hold, and execution revision. It may reuse
identical observed behaviour, but every distinct definition still receives its
own ledger/evidence row. The persistent cache remains individual validated
PrimitiveComponents assembled into ephemeral FeatureBundles; no candidate or
result cache is permitted in phase one.

Before enabling a DiscoveryPolicy or increasing it, run cold and warm
representative ticker benchmarks. Record raw reload/fingerprint, cache
preflight/hit/miss/build/write, primitive/mask/exit/execution memo hit counts,
FeaturePlan/receipt verification, partial-component reuse versus full rebuild,
append-extension attempted/accepted/fallback counts, entry-upper-bound
rejections, reference-versus-fast-path parity and work counters,
p50/p95/p99 maximal-slot/training/test/write/total durations,
RSS/cache bytes, candidate slots admitted/completed before 4h30, test reserve,
artifact size, DB connections, source-change/retry/resume behavior, and terminal
time-budget behavior. A p99-based fixed cap, not an optimistic mean, must leave
the 4h30 admission boundary and 25-minute durable-finalization reserve intact.
The first implementation must prove this with a representative cold path before
the page enables production Discover. No Hyperband/successive-halving or
outcome-adaptive quota is allowed in phase one because it changes candidate
semantics and reproducibility.

Start one worker under current roughly 1.92 GiB Docker capacity. Benchmark
before enabling two; never assume V3 `worker_count=6` is a real worker pool.
Keep 100–200 ticker discovery disabled until its own measured scale policy.
Enable 100–200 ticker Current Group BUY Scan only after its separate benchmark
records the same safety/correctness evidence and common-as-of behavior.

### Standalone Streamlit page

Add one sidebar route, **Flexible Rulebook**. It owns four workspaces selected
with a radio/selectbox, not `st.tabs`, so inactive heavy workspaces do not run:

1. **Discover** — permanent `Exploratory — gross. Manual research; no orders.`
   label; source ticker; finite Catalog Builder/snapshot; lazy candidate-space
   and fixed-time/candidate-policy preview; visible seed; explicit New Sample;
   source/cache preflight; and the inline Reuse/Recalculate decision before any
   campaign exists. While running, form inputs lock and the active capsule shows
   phase, cache event, HCM timestamps, elapsed/remaining time, training
   attempted/assigned, frozen/tested, structural coverage, threshold funnel,
   artifact, safe error code, cancel/resume, and `time_budget_exhausted` truth.
   Continue reads only its persisted parent; it exposes no editable source,
   catalog, seed, build contract, or cache choice. Show persistence as unverified
   development storage unless a durable root is separately approved.
2. **Rulebook Library** — paged/filterable immutable definitions and evaluated
   evidence. Show animal alias plus short/full hash, catalog/profile, source and
   split, both train/test gross metrics, training rank, selected representative
   number, duplicate blocker/overlap ratio, and download/detail links. Rejected
   timing duplicates remain visible in a collapsed evidence view.
3. **Cross-ticker Qualification** — immutable rulebook IDs plus a ticker or
   named Group. Freeze and display target members before submit. A cache
   preflight table is grouped by ticker/build contract and makes one batch
   reuse-valid-components/recalculate-all choice per group; V3 `N/A` and V3
   Group helpers are absent.
4. **Current Group BUY Scan** — named Group only; common-as-of preflight before
   any evaluation; all compatible qualified pairs; one cache decision table;
   per-ticker outcome and exact common as-of. A positive line says only
   **BUY setup — next-session open model**, manual research, not trading advice.

No UI writes a Position, submits a V3 job, changes a Backtest rulebook, treats
a cache error as data stale/no setup, or claims profitable, tradable, or
statistically certified.

Acceptance requires portable immutable definitions; fresh-source-validated
per-primitive reuse under frozen FeatureBuildContracts; FeaturePlan/receipt
proof across frozen Resume/Continue; an explicit 24-hour new-request cache
choice and source/age recheck; lazy seeded structurally stratified discovery; a
strict under-five-hour ticker window with maximal-slot p99 caps; causal
reference execution plus parity-gated fast-path optimization; native-bar partitions;
both-side 12/65/15 evidence; training-rank representatives with `>=75%`
training-overlap distinctness; immutable campaign-chain SelectionSnapshots;
append-safe EvidenceSourceAnchor proof; V3 isolation; truthful
resume/failure/cancellation/time exhaustion; common-as-of blocking; and
benchmark-gated scale. Production cache/evidence durability remains unresolved
until a persistent output mount is separately approved.
