# Flexible Rulebook Discovery Activation Design

## Purpose

Turn the existing Flexible Rulebook research engine into a usable, bounded
Discover workflow. It must remain evidence-first: no active policy, bad
benchmark evidence, source correction, or contract mismatch may produce a
Discover campaign.

The existing one-slot production benchmark remains proof-only. This design
adds direct fixed-cap-window proof, an explicitly approved activation policy,
an activated campaign boundary, and an actionable Streamlit workflow.

## Current verified state

- Flexible Core Tasks 1-7, Campaign Tasks 1-6, and the one-slot production
  benchmark exist.
- The production one-slot report requires 100 cold maximal-path samples for
  each configured ticker and seed. Its BenchmarkRecord deliberately exposes no
  discovery attempt cap.
- safe_default_scale_policy() remains zero attempts and the current Discover
  page has no submit handler. This is correct before activation evidence
  exists.
- No cap-length benchmark report, activation policy, or immutable Flexible
  signal-set evidence exists in production storage.

## Goals

1. Benchmark an exact fixed number of complete Discover attempts on real
   PostgreSQL history within the existing under-five-hour boundary.
2. Permit a real Discover campaign only after an operator explicitly activates
   eligible benchmark evidence.
3. Make the page usable: clear activation state, current-source preflight,
   cache choice, asynchronous campaign start, refresh, Cancel, Resume, and
   Continue.
4. Preserve existing immutable rulebook, evaluation, selection, receipt, and
   ledger evidence semantics.
5. Keep the benchmark, policy, and live campaign roles separate so proving a
   cap never requires an already-active cap.

## Non-goals

- No V3, Backtest Lab, positions, validation, SQL, BIGINT, Docker,
  credential, dependency, or protected-query changes.
- No automatic policy authorization, multi-worker operation, fast executor,
  append extension, or 100-200 ticker Discover activation.
- No UI editing of benchmark evidence or policies.
- No claim that a research result is certified, profitable, or tradable.

## Resolved source-scope policy

Active Discover uses the latest available history, not only the historical
date used by the benchmark.

Before every Start, Resume, or Continue, the runtime first reloads the exact
benchmark anchor range for that ticker at policy.benchmark_as_of. Its complete
FeatureSnapshot identity must equal the immutable source anchor in the active
policy. A correction, missing data, changed quality state, or changed
historical fingerprint blocks the action.

Only after the anchor matches does Start fresh-load the latest 15-year source,
assess data quality, construct a new native-bar split, inspect the indicator
cache, and freeze that exact source and split into the new campaign. Normal
new bars are therefore allowed. A campaign never silently switches to new
bars after submission: Resume and Continue require its exact persisted source,
receipt, split, and policy document.

The benchmark proves the execution envelope for its ticker and seed, not that
new data is valid research evidence. Each new campaign owns its own immutable
current source and train/test evidence.

## Immutable contracts

### Discovery runtime contract

Cap reports and policies carry one canonical DiscoveryRuntimeContract identity:

- catalog hash;
- FeatureBuildContract hash and FeatureProfile hash;
- CandidateSpace hash and algorithm version;
- frontier algorithm and stratification revisions;
- ExecutionContract, RuntimeBudget, and SelectionPolicy identities;
- engine revision and qualification revision.

The report also carries, for every benchmark ticker, the immutable source
anchor and the benchmark split identity. The per-ticker split is evidence of
the benchmark run; it is not incorrectly reused as a global split for a
later, current-data campaign. The current campaign recomputes its split using
the frozen split algorithm in DiscoveryRuntimeContract.

### Discovery timing events

The cap benchmark needs more than the current aggregate phase observer.
Discovery emits immutable timing events:

- SlotPhaseTiming(global_slot, phase, seconds) for entry-mask construction,
  training execution, and test execution. Training and test can be absent for
  a fast rejection, and their absence is explicit rather than represented as a
  fake zero.
- WindowPhaseTiming(phase, seconds) for selection and artifact/checkpoint
  writing, which occur once per cap window rather than once per slot.

The cap runner records the exact event sequence for diagnostics. Selection and
write are window finalization costs; they must never be labelled per-slot
costs or used to manufacture a one-slot cap calculation.

### Discovery cap sample

DiscoveryCapSample is a frozen canonical record for one isolated cold or warm
end-to-end cap window. It contains:

- ticker, seed, mode, sample_index, benchmark_as_of, cap_attempts, start_slot,
  and the full FrontierAssignment identity;
- a complete FeatureSnapshot source anchor and split identity whenever parent
  preflight obtained an eligible source;
- attempted, committed, next-slot, and uncommitted-slot counts;
- preflight, cap-window, and full sample wall-clock durations;
- per-slot timing events plus selection/write window timing;
- terminal state, safe error code, fresh benchmark-child RSS, client-side
  pool checkouts, cache bytes, and artifact bytes.

For a report with sample_count cold samples, the deterministic start slot is
sample_index multiplied by cap_attempts. A report rejects a request whose
final window would exceed CandidateSpace.size. The resulting windows are
disjoint and cover different frontier regions without relying on a random
runtime choice.

The duplicate identity is:

  (ticker, seed, mode, sample_index, benchmark_as_of, cap_attempts,
   assignment_hash)

A cold sample is complete only when its terminal state is completed, it has no
safe error or uncommitted slot, attempted_count and committed_count equal
cap_attempts, and next_slot equals start_slot plus cap_attempts. Fast rejected
candidates are valid committed slots. Training-only, interrupted, blocked,
completed_with_errors, and partial windows remain truthful diagnostic evidence
but cannot authorize a cap.

If parent source preflight itself cannot produce an eligible frozen source,
the diagnostic window records null source and split identities instead of
inventing an anchor. Such a window is necessarily incomplete and ineligible;
only a complete cold window requires non-null source and split identities.

### Discovery cap benchmark report

DiscoveryCapBenchmarkReport is a separate canonical schema. It contains:

- one fixed benchmark_as_of, cap_attempts, DiscoveryRuntimeContract identity,
  ordered unique ticker and seed tuples, and ordered samples;
- per-ticker immutable source anchors and benchmark split identities derived
  only when every completed cold sample agrees;
- canonical SHA-256 digest and schema revision.

Eligibility requires for every configured ticker and seed:

- at least 100 completed cold cap samples;
- every cold sample has the exact cap and no incomplete window;
- stable complete source anchor and stable split identity across every seed for
  the ticker;
- unique sample identity and valid disjoint deterministic start slots;
- p99(preflight_seconds) plus p99(cap_window_seconds) is within 16,200
  seconds, and p99(total_seconds) is within 17,700 seconds;
- all 100 cold samples, report assembly, cleanup, and any optional diagnostic
  warm samples fit inside one serial 17,700-second ticker budget.

The last condition is intentionally stronger than a per-sample four-hour
limit. With 100 cold samples, the average complete cold window must be roughly
177 seconds or less before overhead. If the requested cap cannot meet that
truthful condition, the runner writes an ineligible report and leaves
activation at zero. It never silently lowers the cap or shortens the required
cold count.

Warm samples are diagnostics only and never improve eligibility.

### Direct cap-bearing BenchmarkRecord

The cap-report conversion extends BenchmarkRecord with direct-window evidence:

- measured_discovery_attempt_caps is exactly (report.cap_attempts,);
- direct_cap_window_attempt_count equals report.cap_attempts;
- cold_p99_cap_window_seconds and cold_p99_total_seconds come from complete
  cold cap samples;
- maximal_slot_sample_count is at least 100 and worker_counts is exactly (1,).

validate_scale_policy() accepts a non-zero discovery cap only through this
direct-window branch. It requires the policy cap to equal the measured cap,
not merely be smaller than the largest cap, and checks the cap-window p99
deadline formula above. Existing one-slot BenchmarkRecords retain no measured
cap and cannot authorize Discover.

BenchmarkRecord gets a canonical identity payload and SHA-256 digest. The
activation policy stores this digest and recomputes it from the referenced cap
report on every load.

### Immutable activation policy and active pointer

ActivatedDiscoveryPolicy is a canonical immutable document containing:

- its schema/revision and policy digest;
- cap-report digest, canonical benchmark-record digest, and safe relative path
  to the immutable report;
- exact allowed ticker and seed tuples;
- DiscoveryRuntimeContract identity and per-ticker benchmark source
  anchors/split identities;
- the exact measured cap and worker_count = 1;
- non-empty operator identity, approval note, and activation timestamp.

Files below the benchmark directory are arranged as:

reports/<cap-report-digest>.json
policies/<policy-digest>.json
active-policy.json

The report and policy documents are immutable and idempotent: an existing
path is accepted only when its canonical bytes match. active-policy.json is a
small atomically replaced pointer containing policy_relpath and policy_digest.
It is the only mutable file.

The default pointer is /data/flexible-benchmark/active-policy.json, which is
inside the existing application data mount and outside the live Flexible
evidence root. A configured override is valid only when it resolves to an
absolute file outside app/Flexible-Rulebook.

New Start loads the active pointer and its referenced immutable policy on every
render. A submitted campaign persists activation_policy_digest in its semantic
request identity. Resume and Continue load that digest-named immutable policy,
not the current pointer, so later activation cannot silently alter or strand
an existing campaign. Missing or changed policy/report bytes block safely.

The loader validates canonical bytes, digest, contained relative paths,
referenced report, direct BenchmarkRecord, all contract identities, allowed
scope, and worker count. It returns (None, reason) on any failure; callers
then use safe_default_scale_policy() with zero attempts.

### Benchmark and activated campaign authority

CampaignRequest gains activation_policy_digest: str | None. It is None for
isolated benchmark-only requests and present for activated user Discover
requests.

submit_campaign() remains a generic persistence primitive so existing isolated
benchmarks can exercise the full campaign path before any policy exists.
submit_activated_discovery() is the only UI-facing submission boundary. It
requires a validated immutable policy, non-empty matching digest, exact
ticker/seed/cap/worker/contract scope, and a live evidence root. A benchmark
request is permitted only below an isolated root outside the live Flexible
evidence tree.

Legacy manifests without activation_policy_digest remain readable for audit but
cannot be started, resumed, or continued through the activated workflow.

### Cache and worker contract

Every user action performs the full source-anchor verification and fresh
current-source load before cache inspection. If source-compatible primitive
components are at most one day old, the page offers Reuse verified indicator
cache or Recalculate now. Missing, stale, incompatible, or corrupt components
force rebuild. The chosen value is persisted as campaign runtime provenance.

The worker factory must receive WorkerRequest, not only root. Its activated
factory reads the exact campaign manifest by campaign_id, validates the
activation policy digest, builds the catalog FeatureProfile, and resolves
components using the manifest cache_choice. The top-level source-loader
function opens a short-lived established read-only engine and reloads the
frozen source. No UI closure crosses the process boundary.

## Runtime flow

1. Operator runs the existing one-slot benchmark for non-authorizing context.
2. Operator selects an explicit cap, ticker, seed, and fixed benchmark_as_of.
3. The cap runner executes 100 disjoint cold cap windows per ticker/seed in
   isolated roots and writes a truthful immutable report.
4. The operator independently reviews the report. Only an eligible report can
   create an immutable policy and atomically update the active pointer.
5. Discover loads and validates the pointer/policy on every render. Invalid or
   absent activation shows zero attempts and an actionable reason.
6. Start verifies the policy benchmark anchor, fresh-loads current history,
   offers any valid cache choice, freezes a policy-bound CampaignRequest, then
   claims and spawns one worker without blocking the Streamlit request.
7. The worker re-verifies the frozen source/build/policy, writes receipt,
   ledger, definitions, qualified signal sets, item, and terminal selection
   evidence in existing order.
8. The page reads the manifest sidecar and offers Refresh, legal Cancel,
   Resume, or receipt-bound Continue. It clears stale preflight state whenever
   policy digest, ticker, seed, cache choice, or source identity changes.
9. Library, Cross-ticker Qualification, and Current Group BUY Scan consume
   only committed immutable evidence.

## UI behavior

Discover displays:

- policy state, active policy digest, benchmark report digest, fixed cap,
  allowed ticker/seed scope, and benchmark-as-of anchor;
- a normalized uppercase ticker selector restricted to the policy scope and a
  seed selector restricted to the policy scope;
- Preflight Discover followed by cache diagnostics and, only when needed, the
  explicit cache choice;
- Start Discover only after successful preflight;
- a campaign identifier, current state, assigned slot range, safe error
  message, and a manual Refresh control after submission;
- Cancel only for queued/running campaigns; Resume only for interrupted,
  cancelled, or blocked campaigns whose policy/source/receipt verify; Continue
  only for terminal contiguous windows with a verified next slot.

All research copy remains Exploratory — gross. The page never calls output
certified, profitable, tradable, or an order.

## Safety and error behavior

- A changed benchmark anchor, invalid current source, missing policy, corrupt
  pointer/report/policy, mismatched contract, invalid cache receipt, or
  out-of-scope ticker/seed blocks before campaign submission.
- Normal new bars create a new frozen campaign; they never mutate old evidence.
- Worker death/timeouts produce interrupted state and no forged completed
  evidence.
- An uncommitted window is completed_with_errors and has no selection snapshot.
- Policy replacement affects only new Starts. Existing policy-bound campaigns
  use their immutable referenced policy.
- All benchmark roots are isolated outside live evidence. The benchmark cannot
  publish rulebooks or signal sets.

## Verification contract

Implementation is complete only when Docker tests prove:

- canonical cap report round-trip, direct-window p99 validation, exact cap
  matching, source/split stability, duplicate rejection, and ineligible truth;
- disjoint sample-window scheduling, terminal budget handling, and isolated
  benchmark roots;
- immutable report/policy documents, active-pointer replacement, relative-path
  containment, digest/record validation, and old-policy Resume after pointer
  replacement;
- benchmark requests remain runnable with no policy, while all interactive
  activated submissions fail without valid policy authority;
- current-data Start requires a matching historical anchor, cache choice is
  honored in the worker, and Resume/Continue preserve the exact frozen source;
- page state/action matrix, including disabled reasons and stale-session
  invalidation;
- Library, Qualification, and Current Scan only consume committed evidence;
- full Flexible Docker suite, compilation, and CLI smoke tests pass.

The real production cap report and explicit activation remain operator actions.
No test fixture can unlock the page by itself.
