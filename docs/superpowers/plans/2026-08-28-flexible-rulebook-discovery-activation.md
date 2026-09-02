# Flexible Rulebook Discovery Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Unlock a policy-bound, fixed-cap Flexible Rulebook Discover workflow that remains disabled until an independently reviewed production cap benchmark is explicitly activated.

**Architecture:** Add direct cap-window evidence instead of trying to infer a multi-slot cap from the legacy one-slot timing model. Immutable digest-named report and policy documents are selected through a small active pointer. A dedicated activated-Discover boundary verifies an historical benchmark anchor, freezes fresh current history, and starts the existing one-worker campaign through a worker factory that receives the persisted campaign context.

**Tech Stack:** Python 3.12, dataclasses, stdlib argparse/json/hashlib/tempfile/subprocess, pandas/NumPy, Streamlit, existing Flexible Rulebook campaign/worker/storage modules, Docker stock_app, PostgreSQL read-only history loader.

## Global constraints

- Keep safe_default_scale_policy() at zero discovery attempts whenever activation is absent or invalid.
- A direct cap proof needs at least 100 completed cold cap windows per ticker and seed under one serial 17,700-second ticker budget.
- Initial activation is exactly one worker and one explicitly measured cap. No implicit cap, fast executor, append extension, or multi-ticker expansion.
- A new Start verifies the fixed benchmark anchor, then uses fresh current history and freezes it into its own campaign. Resume and Continue use only the exact frozen campaign source.
- Reports and policies are immutable by canonical digest. active-policy.json is the sole atomically replaceable pointer.
- The default active pointer is /data/flexible-benchmark/active-policy.json;
  any configured override must be an absolute path outside app/Flexible-Rulebook.
- An interactive Discover submission requires an immutable activation policy digest. Isolated benchmark requests intentionally do not.
- Use the existing bounded parameterized history loader and existing SQL/price rules. Do not change common_queries.py, BIGINT scaling, credentials, Docker files, V3, Backtest Lab, positions, validation, dependencies, or git state.
- No git staging, commit, reset, checkout, or branch action is part of this plan.

---

## File map

| File | Responsibility |
|---|---|
| app/flexible_rulebook/benchmark.py | Extend BenchmarkRecord with direct fixed-cap timing evidence while preserving one-slot non-authorization. |
| app/flexible_rulebook/search.py | Emit slot-addressed timing events for training/test work. |
| app/flexible_rulebook/service.py | Emit window-level selection/write timing and accept worker-resolved campaign cache context. |
| app/flexible_rulebook/cap_benchmark.py | Immutable cap sample/report contracts, eligibility, canonical I/O, and direct record derivation. |
| app/flexible_rulebook/cap_benchmark_runner.py | Read-only isolated cap-window benchmark runner and CLI. |
| app/flexible_rulebook/activation.py | Immutable policy, active pointer, report/record validation, and activation CLI. |
| app/flexible_rulebook/campaigns.py | Persist optional activation_policy_digest in new discovery identities while reading legacy manifests. |
| app/flexible_rulebook/worker.py | Pass WorkerRequest to the service factory. |
| app/flexible_rulebook/discovery_activation.py | Activated preflight, current-source freeze, worker service/source factories, and lifecycle wrappers. |
| app/flexible_rulebook/runner.py | Reuse generic worker primitives only; do not add a global policy gate. |
| app/pages/flexible_rulebook.py | Functional Discover preflight, status, cache choice, and lifecycle controls. |
| tests/test_flexible_rulebook_cap_benchmark.py | Cap contract and direct scale-policy tests. |
| tests/test_flexible_rulebook_cap_benchmark_runner.py | Isolated runner, timing events, disjoint slots, budget, and CLI tests. |
| tests/test_flexible_rulebook_activation.py | Immutable policy/pointer and anchor-scope tests. |
| tests/test_flexible_rulebook_discovery_activation.py | Activated preflight, worker context, authority, and lifecycle tests. |
| tests/test_flexible_rulebook_campaigns.py | Digest serialization and legacy-manifest compatibility tests. |
| tests/test_flexible_rulebook_page.py | Discover page state/action matrix tests. |
| docs/superpowers/reports/2026-08-28-flexible-rulebook-discovery-activation-verification.md | Docker and controlled-pilot evidence. |

### Task 1: Direct cap timing and immutable cap-report contract

**Files:**

- Modify: app/flexible_rulebook/benchmark.py
- Modify: app/flexible_rulebook/search.py
- Modify: app/flexible_rulebook/service.py
- Create: app/flexible_rulebook/cap_benchmark.py
- Create: tests/test_flexible_rulebook_cap_benchmark.py

**Interfaces:**

- Produce these immutable event values:

~~~python
@dataclass(frozen=True)
class SlotPhaseTiming:
    global_slot: int
    phase: Literal["entry_mask", "training", "test"]
    seconds: float

@dataclass(frozen=True)
class WindowPhaseTiming:
    phase: Literal["selection", "write"]
    seconds: float
~~~

Search emits SlotPhaseTiming for entry-mask, training, and test work.
DiscoveryService emits WindowPhaseTiming for selection and write.
- Produce DiscoveryCapSample and DiscoveryCapBenchmarkReport.
- Produce benchmark_record_from_cap_report(report), read_cap_benchmark_report,
  write_cap_benchmark_report, and validate_cap_report.

- [x] **Step 1: Write failing contract tests.**

~~~python
def test_direct_cap_record_requires_the_exact_measured_cap():
    record = benchmark_record_from_cap_report(make_eligible_cap_report(cap_attempts=8))
    validate_scale_policy(
        ScalePolicy(max_discovery_attempt_count=8, worker_count=1,
                    benchmark_report_hash=record.benchmark_report_hash),
        record,
    )
    with self.assertRaisesRegex(ValueError, "exactly equal"):
        validate_scale_policy(
            ScalePolicy(max_discovery_attempt_count=7, worker_count=1,
                        benchmark_report_hash=record.benchmark_report_hash),
            record,
        )
~~~

Add tests for 99 cold windows, incomplete cap window, duplicate sample identity,
overlapping start slots, source-anchor/split disagreement, non-canonical bytes,
tampered digest, p99 direct-window deadline failure, total-ticker-budget
failure, and proof that benchmark_record_from_report() still exposes no cap.

- [x] **Step 2: Run the focused RED suite.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_cap_benchmark -v
~~~

Expected: import failures for cap contracts and direct-cap assertions.

- [x] **Step 3: Add the timing-event contract.**

Replace the unaddressed phase callback with events that retain global_slot.
Search emits training/test timings for the candidate that performed that work.
DiscoveryService emits selection/write only as window events. Do not record
missing training/test work as zero seconds.

- [x] **Step 4: Implement direct cap contracts and policy validation.**

Require sample start_slot = sample_index * cap_attempts and reject a window
outside CandidateSpace. Store complete FeatureSnapshot anchor and split
identity in every sample. Extend BenchmarkRecord with direct cap-window p99
fields and a canonical digest payload. In validate_scale_policy(), use the
direct-window branch only when the requested cap exactly equals the measured
cap; preserve the legacy zero-cap behavior for every one-slot record.

- [x] **Step 5: Run GREEN.**

Run the focused suite from Step 2. Expected: every cap contract test passes.

### Task 2: Isolated cap-window benchmark runner

**Files:**

- Create: app/flexible_rulebook/cap_benchmark_runner.py
- Create: tests/test_flexible_rulebook_cap_benchmark_runner.py

**Interfaces:**

CapBenchmarkRuntime mirrors the existing BenchmarkSampleRuntime seams but
measures a complete cap window:

~~~python
@dataclass(frozen=True)
class CapBenchmarkRuntime:
    catalog: CatalogRevision
    history_loader: Callable[[str, date], HistorySnapshot]
    feature_resolver: Callable[[HistorySnapshot, FeatureBuildContract,
                                FeatureProfile, Path,
                                Literal["reuse", "rebuild"]], FeatureResolution]
    campaign_executor: Callable[[CampaignRequest, Path], CampaignManifest]
    cache_is_complete: Callable[[HistorySnapshot, FeatureBuildContract,
                                 FeatureProfile, Path], bool]
    monotonic: Callable[[], float]
    rss_probe: Callable[[], int | None]
    pool_checkout_probe: Callable[[], int | None]
    worker_preparer: Callable[[CampaignRequest, FeatureResolution, Path], None]
    build_contract: FeatureBuildContract
    execution_contract: ExecutionContract
    runtime_budget: RuntimeBudget
    selection_policy: SelectionPolicy
    engine_revision: str
~~~

~~~python
def run_cap_benchmark(
    *,
    tickers: Sequence[str],
    as_of: date,
    seeds: Sequence[str],
    cap_attempts: int,
    cold_samples: int,
    output: Path,
    warm_samples: int = 0,
    ticker_budget_seconds: int = TERMINAL_SECONDS,
    runtime: CapBenchmarkRuntime | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> DiscoveryCapBenchmarkReport:
    pass
~~~

For a sample index i, build FrontierAssignment with start_slot =
i * cap_attempts and attempt_count = cap_attempts. cold_samples must be at
least 100.

- [x] **Step 1: Write failing runner tests.**

~~~python
def test_cold_samples_cover_disjoint_deterministic_cap_windows():
    report = run_cap_benchmark(
        tickers=("VCB",), as_of=date(2026, 8, 28),
        seeds=("frb-default-seed-v1",), cap_attempts=8,
        cold_samples=100, output=output_path(), runtime=deterministic_runtime(),
    )
    starts = [sample.start_slot for sample in report.cold_samples("VCB", "frb-default-seed-v1")]
    self.assertEqual(starts, [index * 8 for index in range(100)])
~~~

Add isolated-root tests for one exact cap campaign, full source re-load in the
worker, partial/timeout truth, no live evidence publication, serial remaining
deadline propagation, process-group termination, warm diagnostics, and CLI
exit code 2 after a truthful ineligible report.

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_cap_benchmark_runner -v
~~~

Expected: import failures for the new runner.

- [x] **Step 3: Implement a cold cap window.**

Use a fresh isolated root and process group for every sample. Parent preflight
fresh-loads the fixed as-of source, resolves a cold feature store, creates one
cap-sized campaign request with activation_policy_digest = None, and starts
the real worker. Capture source/split/assignment/counts/timing events only
after the worker terminal manifest is read.

When source preflight itself cannot obtain an eligible source, write an
incomplete diagnostic sample with null source/split identity and a safe source
failure code. Never fabricate an anchor; null identities cannot meet complete
cold-window eligibility.

- [x] **Step 4: Implement report assembly and bounded CLI.**

Run cold then optional warm samples serially under one deadline per ticker.
On expiry, append truthful exhausted samples for the remaining identities,
write the ineligible report atomically, and return exit code 2. Require
absolute output outside the live Flexible root, explicit unique tickers/seeds,
fixed ISO as-of, positive cap, and cold_samples >= 100.

- [x] **Step 5: Run GREEN.**

Run Task 1 and Task 2 focused suites. Expected: all pass without a PostgreSQL
write or a live Flexible artifact.

### Task 3: Immutable activation policy and active pointer

**Files:**

- Create: app/flexible_rulebook/activation.py
- Create: tests/test_flexible_rulebook_activation.py
- Modify: app/flexible_rulebook/__init__.py

**Interfaces:**

~~~python
def activate_cap_report(
    report_path: Path,
    benchmark_directory: Path,
    *,
    allowed_tickers: Sequence[str],
    allowed_seeds: Sequence[str],
    approved_by: str,
    approval_note: str,
) -> ActivatedDiscoveryPolicy:
    pass

def load_active_policy(path: Path | None = None) -> tuple[ActivatedDiscoveryPolicy | None, str]:
    pass

def load_policy_by_digest(directory: Path, policy_digest: str) -> ActivatedDiscoveryPolicy:
    pass
~~~

- [x] **Step 1: Write failing activation tests.**

~~~python
def test_policy_pointer_replacement_does_not_change_old_campaign_authority():
    first = activate_report(report_a(), benchmark_directory(), allowed_tickers=("VCB",))
    second = activate_report(report_b(), benchmark_directory(), allowed_tickers=("FPT",))
    self.assertNotEqual(first.policy_digest, second.policy_digest)
    self.assertEqual(load_policy_by_digest(benchmark_directory(), first.policy_digest), first)
~~~

Add report canonical-copy tests, idempotent immutable write, different-content
collision rejection, pointer digest/path traversal rejection, tampered derived
record digest, missing historical anchor, profile/runtime/selection-contract
mismatch, worker_count != 1, and unmeasured cap rejection.

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_activation -v
~~~

Expected: import failures for activation contracts.

- [x] **Step 3: Implement immutable report/policy storage.**

Copy or write the validated cap report as reports/<digest>.json only if
canonical bytes match. Write policies/<digest>.json with hard-link-style
idempotence; atomically replace only active-policy.json. Persist the complete
DiscoveryRuntimeContract, direct record digest, allowed scope, source-anchor
map, benchmark-split map, exact cap, and approval metadata.

- [x] **Step 4: Implement validation and CLI.**

The loader resolves only contained relative paths, re-reads report bytes,
re-derives the direct BenchmarkRecord, recomputes current static runtime
contract, and fails closed. The CLI has explicit report, benchmark-directory,
allowed ticker/seed, operator, and approval-note arguments. It cannot write
to the live evidence tree.

- [x] **Step 5: Run GREEN.**

Run the focused activation suite plus Task 1. Expected: immutable policy
documents and an atomic active pointer behave deterministically.

### Task 4: Activated campaign boundary and worker context

**Files:**

- Create: app/flexible_rulebook/discovery_activation.py
- Modify: app/flexible_rulebook/campaigns.py
- Modify: app/flexible_rulebook/worker.py
- Modify: app/flexible_rulebook/benchmark_runner.py
- Create: tests/test_flexible_rulebook_discovery_activation.py
- Modify: tests/test_flexible_rulebook_campaigns.py
- Modify: tests/test_flexible_rulebook_worker.py

**Interfaces:**

~~~python
def preflight_activated_discovery(
    engine: object,
    ticker: str,
    seed: str,
    policy: ActivatedDiscoveryPolicy,
    *,
    root: Path,
    now: datetime,
) -> ActivatedDiscoveryPreflight:
    pass

def submit_activated_discovery(
    preflight: ActivatedDiscoveryPreflight,
    *,
    cache_choice: Literal["reuse", "rebuild"],
    root: Path,
) -> str:
    pass

def activated_discovery_service(request: WorkerRequest) -> DiscoveryService:
    pass

def activated_discovery_source_loader(expected: FeatureSnapshot) -> HistorySnapshot:
    pass
~~~

- [x] **Step 1: Write failing authority and worker-context tests.**

~~~python
def test_benchmark_discovery_needs_no_policy_but_ui_submission_does():
    benchmark_campaign_id = submit_campaign(benchmark_request(), isolated_root())
    self.assertTrue(benchmark_campaign_id.startswith("fcmp_"))
    with self.assertRaisesRegex(ValueError, "activation policy"):
        submit_activated_discovery(preflight_without_policy(), cache_choice="rebuild", root=live_root())
~~~

Add tests that worker service construction receives campaign_id, honors
manifest.cache_choice, rejects a policy digest mismatch, verifies benchmark
anchor before a fresh-current load, freezes a new current split/source, blocks
changed anchor, preserves old manifest readability, and rejects legacy
manifests from activated Resume/Continue.

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_discovery_activation tests.test_flexible_rulebook_campaigns tests.test_flexible_rulebook_worker -v
~~~

Expected: new authority, source-anchor, and worker-context assertions fail.

- [x] **Step 3: Persist policy authority safely.**

Add activation_policy_digest: str | None to CampaignRequest identity. Its
absence is valid only for legacy/isolated benchmark use. Extend request
deserialization and linked-continuation frozen fields so old manifests still
read and new policy-bound chains preserve the digest.

- [x] **Step 4: Implement activated preflight and submission.**

Verify policy ticker/seed/runtime contract and the report-period source anchor
with the established loader. Then fresh-load current history, require eligible
quality, build current FeatureProfile/FeaturePlan/split/cache offer, assign
the exact measured cap, and construct a policy-bound CampaignRequest. Submit,
claim, and spawn exactly one worker only from submit_activated_discovery().

- [x] **Step 5: Pass WorkerRequest to service factories.**

Change worker.run_worker_request() to call service_factory(request). Adapt the
benchmark factory. The activated factory reads the named manifest, resolves
the immutable policy by its stored digest, validates its request, and uses the
persisted cache choice when resolving the feature store. The top-level source
loader reopens a short-lived established engine; no Streamlit callback is
serialized.

- [x] **Step 6: Implement lifecycle wrappers.**

Start new work only with the active pointer. Resume/Continue load the
manifest's immutable digest-named policy, then verify exact frozen source,
receipt, contract, and cursor before using existing generic runner operations.
An old policy remains usable for its campaign after active-pointer replacement.

- [x] **Step 7: Run GREEN.**

Run the suites from Step 2, benchmark tests, and existing runner tests.
Expected: benchmark and activated authority paths are separated; no unverified
campaign can publish evidence.

### Task 5: Functional Discover UI

**Files:**

- Modify: app/pages/flexible_rulebook.py
- Modify: tests/test_flexible_rulebook_page.py

**Interfaces:**

- Inject policy loader, activated preflight/submit/lifecycle functions, and
  campaign reader into render_flexible_rulebook_page() with existing callable
  defaults so AppTest can remain deterministic.
- Keep Rulebook Library, Cross-ticker Qualification, and Current Group BUY
  Scan unchanged except for consuming the existing committed evidence.

- [x] **Step 1: Write failing page tests.**

~~~python
def test_discover_requires_anchor_preflight_and_explicit_cache_choice_before_start():
    app = render_app_with_active_policy_and_reusable_cache()
    self.assertTrue(button(app, "Start Discover").disabled)
    click(app, "Preflight Discover")
    self.assertFalse(button(app, "Start Discover").disabled)
    self.assertTrue(selectbox(app, "Indicator cache").options)
~~~

Add tests for invalid/missing pointer state, active policy scope rendering,
uppercase ticker normalization, denied out-of-scope ticker, stale session state
after policy digest changes, policy anchor mismatch, campaign status row,
Refresh, legal Cancel, Resume with old immutable policy, Continue with a
contiguous terminal cursor, and disabled illegal actions.

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_page -v
~~~

Expected: active preflight and lifecycle assertions fail against the disabled
shell.

- [x] **Step 3: Implement stateful but non-authorizing UI.**

Load active policy every render. Show zero-attempt fallback and safe reason
when it cannot load. Scope dropdowns to allowed values. Preflight only on its
button, display cache diagnostics, require the offered cache choice, and start
through the activated boundary only. Store preflight state keyed by policy
digest, ticker, seed, source fingerprint, and cache choice; clear it when any
key changes.

- [x] **Step 4: Implement lifecycle display.**

After spawn, persist campaign_id in session state and read its manifest on
every render. Provide manual Refresh through st.rerun, not a blocking worker
watch. Render only legal action buttons and translate safe error codes into
plain operational text. Keep every result label Exploratory — gross.

- [x] **Step 5: Run GREEN.**

Run page, activated-discovery, campaign, worker, storage, and current-scan
suites. Expected: all Discover actions are policy-bound and other workspaces
remain read-only consumers of committed evidence.

### Task 6: Full verification and controlled production runbook

**Files:**

- Create: docs/superpowers/reports/2026-08-28-flexible-rulebook-discovery-activation-verification.md
- Modify: FOCUS.md
- Modify: ai-context/current-status.md
- Modify: docs/superpowers/plans/2026-08-25-flexible-rulebook-campaigns-and-current-scan.md

- [x] **Step 1: Run the full Docker gate.**

Run:

~~~text
docker exec stock_app python -m unittest discover -s tests -p "test_flexible_rulebook*.py" -v
docker exec stock_app python -m compileall -q flexible_rulebook
docker exec stock_app python -m flexible_rulebook.cap_benchmark_runner --help
docker exec stock_app python -m flexible_rulebook.activation --help
~~~

Expected: all Flexible tests pass, compilation passes, and both CLI help
commands exit without opening the database or writing evidence.

- [x] **Step 2: Run focused self-review.**

Verify direct-window timing is never represented as a one-slot calculation;
100 cold samples share the 17,700-second ticker budget; benchmark requests
remain isolated; pointer replacement preserves old campaign authority; current
source use requires a matching benchmark anchor; cache choice reaches the
worker; and no new SQL/dependency/protected-boundary change exists.

- [x] **Step 3: Write the operator runbook.**

Documented this exact sequence; it was executed for VCB on 2026-08-30:

1. Run the existing one-slot benchmark only for context.
2. Choose one explicit cap after reviewing that context.
3. Run the cap benchmark with one ticker, one seed, a fixed historical as-of,
   100 cold samples, and an output outside the live evidence root.
4. Inspect its eligibility, source anchors, direct timing, and serial ticker
   budget result.
5. Explicitly activate the report into the benchmark directory.
6. Open Discover, preflight the allowed ticker/seed, choose cache behavior,
   start one campaign, then inspect Library and downstream workflows.

An ineligible benchmark remains useful diagnostic evidence but cannot update
active-policy.json. Passing code tests alone does not unlock the page; the
operator must complete steps 3-5.

- [x] **Step 4: Update durable status truthfully.**

Record exact Docker test counts, source files changed, the real benchmark
report path/digest if one was run, active policy scope if one was activated,
and the stopped point if no production corpus was run. Do not mark activation
complete from fixture-only evidence.

- [x] **Step 5: Execute the controlled production benchmark and activation.**

VCB was run with seed `frb-default-seed-v1`, fixed cap 8, one worker, and 100
cold windows. The report was eligible with zero failures and was atomically
activated into `/data/flexible-benchmark`; Discover is now unlocked only for
that ticker/seed scope.

## Plan self-review

- Direct multi-slot evidence is covered by Tasks 1-2; no cap is inferred from
  one-slot evidence.
- Immutable policy, pointer replacement, and full contract/source scope are
  covered by Task 3.
- The separated benchmark and activated-campaign paths, source-anchor rule,
  worker cache context, and lifecycle semantics are covered by Task 4.
- Actual usable Discover controls are covered by Task 5.
- Docker verification and the unavoidable real operator benchmark/activation
  are covered by Task 6.
- No task introduces a dependency, raw SQL, Docker edit, V3 change, or git
  action.
