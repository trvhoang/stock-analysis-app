# Flexible Rulebook Campaigns and Current-Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax for tracking. Do not commit, stage, inspect, or run Git commands.

**Goal:** Add durable Flexible Rulebook campaigns, isolated bounded workers, cross-ticker qualification, truthful current Group BUY Scan, and standalone Streamlit page after the Flexible Rulebook core plan passes.

**Architecture:** Flexible owns a frozen request/manifest protocol, one coordinator, isolated worker module, and campaign artifacts. Workers never mutate a shared manifest. Every operation invocation fresh-validates its frozen source and FeatureBuildContract before using reusable per-primitive components; Resume/Continue never switch snapshots or feature semantics. Current scan applies only previously qualified exact rulebook × ticker pairs at one common completed-bar date; it does not rediscover or replay 15-year trades. The new sidebar page calls Flexible APIs only.

**Tech Stack:** Python 3.12 standard library subprocess/concurrency, pandas/NumPy already installed, Streamlit 1.32, unittest/AppTest, Docker.

**Status:** Tasks 1–6 complete and Docker-verified (2026-08-28). The
Cross-ticker Qualification controls were amended on 2026-08-28 to use
available immutable-rulebook and named-Group dropdowns (including existing
Unicode Group names); Discover remains
explicitly blocked with an actionable safe-state explanation. Task 5 recorded its
deterministic fixture evidence while intentionally retaining the safe default;
a separate production-scale benchmark is still required for any cap, worker,
or acceleration expansion (2026-08-27).
Task 1 durable contracts,
manifest persistence, reconciliation, and receipt-bound Continue are complete.
Task 2 has a concrete receipt-first DiscoveryService, a serialized
one-worker/watchdog boundary, safe fault classification/receipt-bound Resume
proof, cooperative cancellation, one-retry transient item handling, and safe
incompatible-checkpoint failure with lease release. Local worker, service,
discovery, and campaign evidence is 159/159 plus compilation. Docker rerun is
passes. Task 3 now adds the read-only group adapter, fresh all-member
preflight, unioned primitive profiles, explicit cache choice, independent
target qualification, and source-change isolation. The full Flexible Docker
suite passes 189/189 plus compilation. Task 4 common-as-of Current BUY Scan is
complete. Task 5 gate implementation and deterministic cold/warm fixture
evidence are complete; measured production-scale coverage remains required
before any cap or worker expansion.

**Production benchmark amendment (2026-08-28):** the separate runnable
production benchmark implementation now exists in
`2026-08-28-flexible-rulebook-production-benchmark.md`. It keeps Discover at
zero attempts, records full-path cold evidence only, applies a 4h55
ticker-wide budget, and cannot itself authorize a discovery cap. Host
verification passes; Docker server `24.0.6` also passes the focused 29/29
benchmark gate, container compilation, and CLI help. Any real PostgreSQL
evidence remains pending and cannot enable a cap by itself.
The follow-on full-unlock sequence is now frozen in
`docs/superpowers/specs/2026-08-28-flexible-rulebook-discovery-activation-design.md`
and
`docs/superpowers/plans/2026-08-28-flexible-rulebook-discovery-activation.md`.
Its implementation and Docker verification are complete as of 2026-08-30
(298 Flexible tests). The real cap-length evidence and explicit activation are
controlled operator actions still required before Discover can leave the
zero-attempt state. See
`docs/superpowers/reports/2026-08-28-flexible-rulebook-discovery-activation-verification.md`.
Depends on
docs/superpowers/plans/2026-08-25-flexible-rulebook-core.md, whose final gate
passes. Frozen request/manifest lifecycle contracts and source-verified Continue
cursors pass focused Docker evidence (15/15) plus compilation; local/Docker
worker, service, discovery, campaign, group, and current-scan evidence is 189/189 plus
compilation.

## Global Constraints

- Implement docs/superpowers/specs/2026-08-25-flexible-rulebook-design.md exactly.
- Do not start before core contracts/services/storage pass.
- Do not reuse BacktestBatchConfig, V3 pipeline, V3 persistence, V3 job runner,
  V3 N/A Group resolution, group-assignment helpers, V3 status paths, or V3
  can BUY wording.
- One initial Flexible worker only. A second worker requires benchmark evidence.
- 100–200 ticker current scans remain disabled until explicit benchmark-scale
  policy is written after measured pass; 100–200 discovery remains disabled.
- Discovery freezes a lazy CandidateSpace FrontierAssignment before work;
  resume reuses it and Continue advances its cursor. Qualification and current
  scan reject all discovery-assignment fields.
- Every ticker has a 16,200-second candidate-admission deadline and a
  17,700-second normal terminal deadline. Cache/source/build/test/write all
  count; the 18,000-second process watchdog is fail-safe only.
- New Discover/Qualification/Current Scan fresh-loads and fingerprints source
  before cache resolution. A verified compatible cache at age <=24 hours asks
  Reuse valid components/Recalculate all; expired/missing/corrupt/mismatched
  components rebuild automatically. The worker rechecks source, build contract,
  and age before execution; a changed source rejects the old choice as
  source_changed and unavailable frozen revision fails safely. Cache state never
  changes request hash or frozen work.
- Continue reads every semantic field from persisted parent, verifies same frozen
  source/build contract, then uses/rebuilds exact PrimitiveComponents without a
  prompt. The same verification applies to initial work, retry, and Resume. A
  source change blocks cursor advance as source_changed; Repeat latest is a new
  operation.
- Top 3 uses training-only rank plus training overlap_ratio >= 0.75 hard
  duplicate exclusion; test metrics/timing remain evidence only.
- Flexible reads named Group JSON through its own minimal read-only parser. It
  must not import `backtest_engine.result_store`, `list_groups`, or any V3
  group-resolution helper.
- Group membership is frozen at submit and read-only; preserve frozen order.
- All current scan members must share the same latest completed bar date.
- no_current_setup only follows successful current evaluation of every
  historically qualified exact rulebook for that ticker.
- Output must say Exploratory — gross and BUY setup — next-session open model;
  never trading advice, profitable, tradable, or certified.
- All artifacts are Flexible-only, hash-addressed, atomic, and contain no
  credentials or tracebacks.
- Do not modify common_queries.py, BIGINT scaling, get_engine_with_retry,
  credentials, Docker, dependencies, database schema, V3, positions, or Git.

---

## File map

| File | Responsibility |
|---|---|
| app/flexible_rulebook/campaigns.py | Request/manifest schemas, state transitions, request hash, safe error codes. |
| app/flexible_rulebook/runner.py | Submit/poll/cancel/resume, global lease, isolated subprocess lifecycle. |
| app/flexible_rulebook/worker.py | Module entry point running one coordinator request. |
| app/flexible_rulebook/group_adapter.py | Direct read-only named Group JSON parser; no V3 helper import or N/A behavior. |
| app/flexible_rulebook/current_scan.py | Common-as-of preflight and qualified-pair latest-bar evaluation. |
| app/flexible_rulebook/benchmark.py | Measured benchmark schema and scale-policy validator. |
| app/pages/flexible_rulebook.py | Standalone radio-workspace Streamlit page, cache decision UI, and injected test seams. |
| app/main.py | Adds Flexible Rulebook sidebar route only. |
| tests/test_flexible_rulebook_campaigns.py | Durable request/manifest/idempotency/recovery states. |
| tests/test_flexible_rulebook_runner.py | Worker lifecycle, retry/cancel/resume/lease behavior. |
| tests/test_flexible_rulebook_group_adapter.py | Named Group read-only snapshot behavior. |
| tests/test_flexible_rulebook_current_scan.py | Common-as-of and truthful BUY/no-setup state. |
| tests/test_flexible_rulebook_benchmark.py | Scale gate and benchmark artifact validation. |
| tests/test_flexible_rulebook_page.py | AppTest page copy, controls, no V3 wiring. |
| FOCUS.md, ai-context/current-status.md | Durable task completion and benchmark status. |

### Task 1: Durable campaign contracts, request hash, and manifest transitions

**Files:**

- Create: app/flexible_rulebook/campaigns.py
- Create: tests/test_flexible_rulebook_campaigns.py

**Consumes:** Flexible core contracts/storage.

**Produces:**

~~~python
CampaignState = Literal["queued", "running", "cancelling", "cancelled", "blocked",
                         "interrupted", "completed", "completed_with_errors", "failed"]
HistoricalItemState = Literal["queued", "running", "retry_pending", "qualified",
                              "no_qualified_candidate_within_budget", "time_budget_exhausted",
                              "frontier_exhausted_no_qualified_candidate", "data_ineligible",
                              "source_changed", "failed", "cancelled", "not_started_budget_limited"]

@dataclass(frozen=True)
class CampaignRequest: ...
@dataclass(frozen=True)
class CampaignManifest: ...
@dataclass(frozen=True)
class SelectionSnapshot: ...
@dataclass(frozen=True)
class FeatureResolutionReceipt: ...
def request_hash(request: CampaignRequest) -> str: ...
def create_manifest(request: CampaignRequest) -> CampaignManifest: ...
def transition(manifest: CampaignManifest, target: CampaignState) -> CampaignManifest: ...
def continue_discovery(parent: CampaignManifest, *, verified_source: HistorySnapshot) -> CampaignRequest: ...
~~~

- [x] **Step 1: Write RED idempotency/state tests.**

~~~python
def test_hash_changes_for_budget_or_definition_not_timestamp():
    request = _request()
    self.assertEqual(request_hash(request), request_hash(replace(request, submitted_at="later")))
    self.assertNotEqual(request_hash(request), request_hash(replace(request, per_ticker_budget=99)))

def test_discovery_hash_changes_for_seed_algorithm_or_start_slot(): ...
def test_discovery_hash_changes_for_candidate_space_mapping_version(): ...
def test_hash_changes_for_runtime_strata_or_selection_policy_not_cache_choice(): ...
def test_request_hash_includes_feature_plan_but_not_cache_path_age_or_receipt_storage_event(): ...
def test_qualification_and_current_scan_reject_frontier_assignment(): ...
def test_continuation_links_parent_and_uses_persisted_next_slot(): ...
def test_time_budget_exhausted_is_distinct_historical_item_state(): ...
def test_terminal_campaign_writes_selection_snapshot_from_committed_chain_only(): ...
def test_completed_assignment_window_snapshot_never_claims_global_search(): ...

def test_manifest_rejects_invalid_terminal_transition():
    with self.assertRaises(ValueError):
        transition(create_manifest(_request()), "completed")
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_campaigns -v
~~~

Expected: campaign module absent.

- [x] **Step 3: Implement canonical manifest.**

Include operation, frozen members, group snapshot, exact raw source
fingerprint/bounds/as-of, split/catalog/engine/execution/threshold revisions,
rulebook IDs, FeatureBuildContract hashes, derived FeaturePlan hashes, budgets, parent/origin request,
ticker items, state, lease epoch, progress, and safe error summary. Discovery
also freezes candidate-space hash/size/algorithm version,
frontier_algorithm_version, frontier_seed, source ticker, start_slot, effective
attempt_count, assignment hash, persisted affine coefficients, attempted slot
ranges, next_slot, uncommitted slot, chain-attempted count, unsearched count,
runtime/admission/terminal deadlines, structural stratification revision/quotas,
and timing-distinct selection policy. Ordinary Discover uses visible stable
`frb-default-seed-v1`; only explicit New Sample changes seed before submit.
Record cache event/age/path/choice only as runtime provenance; source snapshot
and build-contract identity are hashed. Exclude timestamp,
elapsed/progress/retry/cancel fields and cache path/age/choice from request hash.
FeatureResolutionReceipt content is not a request input because it is produced
after deterministic resolution; persist its ID/digest in the manifest before a
ticker's first slot can commit. Resume/Continue require the same receipt digest
after fresh frozen-source verification, or fail safely without cursor advance.
Permit only documented state transitions; completed cannot resume,
blocked/interrupted/cancelled can. A completed discovery continues only through a
linked request using its persisted next_slot, never by silently restarting the
frontier prefix.

`continue_discovery` may use only a parent whose committed training slots and
frozen test candidates are terminal. It copies every parent semantic field and
sets only parent ID, new execution-window ID, and `start_slot=parent.next_slot`.
It must reject edited page values, unresolved slot/test work, changed source
fingerprint, or incompatible parent revision. A cache preference cannot be a
Continue input.

At every terminal discovery window, build a new immutable SelectionSnapshot from
the complete committed qualified-evaluation chain through that window. Include
scope, selection/pairing revisions, ordered evaluation/ledger digest, ranking,
selected IDs, rejected blocker relations, and integer overlap numerator/
denominator. It is partial when the frozen search has time/candidate remaining.
Do not write selection rank or blocker into an immutable signal set/ledger row.
Its scope state is `partial_window`, `complete_assigned_window`, or
`frontier_exhausted`; only `frontier_exhausted` may state that search was global.
A Continue recomputes and writes a successor snapshot; it never mutates parent
artifacts.

- [x] **Step 4: Add crash-reconciliation tests.**

~~~python
def test_orphan_verified_item_is_adopted_after_manifest_checkpoint_gap(tmp_path): ...
def test_manifest_claiming_missing_item_becomes_item_failure_not_success(tmp_path): ...
def test_continue_only_changes_parent_link_window_and_start_slot(tmp_path): ...
def test_continue_rejects_unresolved_slot_test_or_changed_frozen_source(tmp_path): ...
def test_cache_choice_is_diagnostic_and_never_changes_request_hash(tmp_path): ...
def test_feature_receipt_mismatch_prevents_resume_or_continue_cursor_advance(tmp_path): ...
def test_continue_new_higher_rank_rewrites_only_successor_selection_snapshot(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run campaign suite. Record manifest version and legal states.

### Task 2: Isolated runner, one-worker lease, retry, cancel, and resume

**Files:**

- Create: app/flexible_rulebook/runner.py
- Create: app/flexible_rulebook/worker.py
- Create: tests/test_flexible_rulebook_runner.py

**Consumes:** CampaignManifest, Flexible storage/service.

**Produces:**

~~~python
def submit_campaign(request: CampaignRequest, root: Path) -> str: ...
def read_campaign(campaign_id: str, root: Path) -> CampaignManifest: ...
def request_cancel(campaign_id: str, root: Path) -> None: ...
def resume_campaign(campaign_id: str, root: Path) -> str: ...
def continue_campaign(parent_campaign_id: str, root: Path) -> str: ...
def run_campaign(campaign_id: str, root: Path, service: CampaignService) -> CampaignManifest: ...
~~~

- [x] **Step 1: Write RED lifecycle tests.**

~~~python
def test_duplicate_running_request_attaches_instead_of_spawning_second_worker(tmp_path): ...
def test_cancel_stops_new_work_after_current_checkpoint(tmp_path): ...
def test_stale_lease_marks_interrupted_and_explicit_resume_uses_new_epoch(tmp_path): ...
def test_resume_reuses_exact_assignment_and_never_reallocates_slots(tmp_path): ...
def test_continue_creates_linked_request_without_same_source_slot_overlap(tmp_path): ...
def test_continue_uses_persisted_parent_not_editable_page_request(tmp_path): ...
def test_continue_rebuilds_same_source_expired_cache_without_prompt(tmp_path): ...
def test_continue_source_change_marks_source_changed_without_cursor_advance(tmp_path): ...
def test_new_request_source_change_between_ui_preflight_and_worker_start_rejects_choice(tmp_path): ...
def test_retry_resume_and_cancelled_resume_verify_frozen_source_before_cursor_advance(tmp_path): ...
def test_resume_rebuilds_expired_components_under_same_contract_without_prompt(tmp_path): ...
def test_resume_after_cache_eviction_accepts_only_identical_feature_receipt(tmp_path): ...
def test_continue_requires_parent_feature_plan_and_receipt_before_new_slot(tmp_path): ...
def test_resume_contract_revision_unavailable_fails_without_mixing_history(tmp_path): ...
def test_time_budget_exhaustion_keeps_uncommitted_slot_for_exact_continue(tmp_path): ...
def test_resume_rejects_candidate_space_mapping_version_mismatch(tmp_path): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_runner -v
~~~

Expected: missing runner/worker APIs.

- [x] **Step 3: Implement isolated coordinator.**

Spawn python -m flexible_rulebook.worker with serialized request path. Coordinator
is sole manifest writer. Use an atomic active-lease file and heartbeat.
ponytail: one global worker is an intentional phase-one ceiling; benchmark-backed
bounded pool is upgrade path. A worker writes item artifact first, then returns
or checkpoints manifest. Worker logs hold traceback; manifest has safe
DATA.*, SOURCE.*, and INFRA.* codes/messages only. Coordinator freezes every
source assignment before worker work begins; worker/resume must consume persisted
slots and never recompute a seed schedule or reallocate failed-source slots.
It validates persisted candidate-space hash/mapping version before resuming; a
mismatch is manifest-invariant failed, never source_changed or merged evidence.
Every worker starts one ticker's monotonic clock before source/cache preflight;
it passes the same deadline through FeatureStore, execution, selection, and
atomic write. At admission deadline it starts no slot; a safe checkpoint leaves
current work uncommitted and checkpoints `time_budget_exhausted` before normal
terminal deadline. The outer watchdog can terminate only a runaway worker and
must leave a recoverable interrupted manifest, never forge a terminal result.
Every initial invocation, retry, Resume, and Continue calls one shared
`verify_frozen_source()` before cache load, ledger write, or cursor advance. It
compares fresh frozen-bounds fingerprint and FeatureBuildContract to manifest
identity, remeasures component age, and either resolves/rebuilds exact components
without a prompt or returns source_changed/FEATURE.REVISION_UNAVAILABLE. It must
not update/overwrite old request to latest data or mix old committed slots with
corrected source outcomes. Before any candidate/ledger cursor commits, it writes
the exact FeatureResolutionReceipt for the persisted FeaturePlan. Resume or
Continue may rebuild after a cache miss/eviction only if every component digest
matches that receipt; otherwise it returns FEATURE.NONDETERMINISTIC_BUILD and
does not advance the cursor. Cache hit/miss, append-extension attempt, and fast
executor choice remain diagnostic and never alter the frozen schedule.

Resume stays within its original execution window and uses persisted unfinished
work. Continue creates a linked new under-five-hour window only after parent work
is terminal. Both consume persisted fields only; neither reads current form
fields or silently moves cursor across data.

- [x] **Step 4: Add fault classification tests.**

~~~python
def test_shared_db_failure_blocks_campaign_without_200_data_invalid_items(tmp_path): ...
def test_one_transient_item_failure_retries_once_then_campaign_completes_with_errors(tmp_path): ...
def test_invalid_catalog_is_terminal_failed_without_retry(tmp_path): ...
def test_deadline_counts_cache_load_train_test_selection_and_write(tmp_path): ...
def test_watchdog_failure_never_skips_a_slot_or_claims_no_qualified_candidate(tmp_path): ...
def test_source_or_contract_failure_never_relabels_item_no_result_or_retries_with_latest(tmp_path): ...
def test_receipt_difference_never_mixes_old_slots_with_new_feature_bytes(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run runner suite. Record cancellation and retry semantics.

### Task 3: Read-only Group snapshot and cross-ticker qualification batches

**Files:**

- Create: app/flexible_rulebook/group_adapter.py
- Modify: app/flexible_rulebook/service.py
- Create: tests/test_flexible_rulebook_group_adapter.py
- Modify: tests/test_flexible_rulebook_service.py

**Consumes:** Existing named Group JSON schema only, core qualify_rulebook_for_ticker.

**Produces:**

~~~python
@dataclass(frozen=True)
class FrozenGroup:
    group_name: str
    group_id: str
    members: tuple[str, ...]
    source_updated_at: str

def resolve_named_group_dir() -> Path: ...
def snapshot_named_group(group_name: str, *, group_dir: Path | None = None) -> FrozenGroup: ...
def preflight_group_feature_components(engine, group: FrozenGroup,
                                       definitions: Sequence[RulebookDefinition],
                                       root: Path, now: datetime) -> Mapping[tuple[str, str], FeaturePreflight]: ...
def qualify_rulebooks_for_group(engine, rulebook_ids, group: FrozenGroup, request: CampaignRequest) -> CampaignManifest: ...
~~~

- [x] **Step 1: Write RED snapshot tests.**

~~~python
def test_named_group_snapshot_is_read_only_and_ignores_v3_na_resolution():
    snapshot = snapshot_named_group("BANK", group_dir=_group_root())
    self.assertEqual(snapshot.members, ("FPT", "VCB"))
    self.assertFalse(_assignment_helper_was_called())

def test_group_mutation_after_submit_does_not_change_campaign_members():
    request = _group_request(("FPT", "VCB"))
    _mutate_group_to(("FPT",))
    self.assertEqual(create_manifest(request).frozen_members, ("FPT", "VCB"))

def test_group_preflight_fresh_loads_every_member_before_offering_cache_reuse(): ...
def test_group_adapter_does_not_import_or_call_v3_result_store_helpers(): ...
def test_group_adapter_resolves_existing_group_directory_from_app_path_not_cwd(tmp_path): ...
def test_one_batch_cache_choice_never_prompts_members_serially(): ...
def test_two_rulebooks_with_different_profiles_produce_per_contract_offer_map(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_group_adapter tests.test_flexible_rulebook_service -v
~~~

Expected: no Group adapter/batch qualification API.

- [x] **Step 3: Implement read-only adapter and bounded qualification.**

Parse the documented named Group JSON directly with a minimal Flexible-owned
schema reader; do not import `result_store`, call `list_groups`, or inherit
V3 `N/A` semantics. Reject blank, dash, and N/A selection. Snapshot ordered
normalized members and revision metadata in request. `resolve_named_group_dir()` derives the existing
`app/backtest-result/ticker-group` location from the Flexible package path, never
from CWD; tests may inject a group directory.
Each target receives exact frozen definition independently;
VCB nonqualification cannot prevent FPT evaluation. Default qualification group
limit remains 15 until its benchmark policy permits more. Before a batch is
created, fresh-load/fingerprint every target, group selected definitions by their
FeatureBuildContract and required primitive union, and produce a preflight map
keyed `(ticker, contract_hash)`. The page asks once per displayed contract group
to reuse valid <=24-hour components/calculate missing or recalculate all; expired/
missing/corrupt/source-mismatched entries rebuild automatically. The choice map
is operational provenance only, never a request-hash field or target eligibility
decision.

- [x] **Step 4: Add target-state tests.**

~~~python
def test_source_fingerprint_change_marks_only_that_target_source_changed(tmp_path): ...
def test_candidate_invalidity_is_ledger_rejection_not_target_failed(tmp_path): ...
def test_cache_hit_or_rebuild_never_changes_group_order_or_requested_targets(tmp_path): ...
def test_cache_failure_does_not_make_target_data_ineligible_or_no_result(tmp_path): ...
def test_changed_target_between_ui_preflight_and_worker_start_is_source_changed(tmp_path): ...
def test_shared_rsi14_component_is_reused_across_two_qualified_rulebook_profiles(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run Group/service suites. Record default group limit and target state map.

### Task 4: Common-as-of current BUY Scan evaluator

**Files:**

- Create: app/flexible_rulebook/current_scan.py
- Create: tests/test_flexible_rulebook_current_scan.py

**Consumes:** FrozenGroup, core history/features, qualified signal-set registry.

**Produces:**

~~~python
@dataclass(frozen=True)
class CommonAsOfPreflight: ...
def preflight_common_as_of(engine, members: tuple[str, ...]) -> CommonAsOfPreflight: ...
def preflight_current_scan_features(engine, preflight: CommonAsOfPreflight,
                                    qualified: Sequence[RulebookEvaluation],
                                    root: Path, now: datetime) -> Mapping[tuple[str, str], FeaturePreflight]: ...
def scan_current_setup(engine, request: CampaignRequest, root: Path) -> CampaignManifest: ...
~~~

- [x] **Step 1: Write RED truthfulness tests.**

~~~python
def test_mismatched_latest_dates_block_whole_group_and_list_laggard():
    result = preflight_common_as_of(_engine({"FPT": "2026-08-21", "VCB": "2026-08-20"}), ("FPT", "VCB"))
    self.assertEqual(result.state, "blocked_common_as_of")
    self.assertEqual(result.lagging_tickers, ("VCB",))

def test_stale_or_unqualified_ticker_never_becomes_no_current_setup(): ...
def test_common_asof_preflight_happens_before_any_cache_resolution(): ...
def test_current_scan_uses_one_batch_cache_decision_after_fresh_fingerprint(): ...
def test_current_scan_profiles_are_grouped_by_contract_and_share_matching_components(): ...
def test_current_scan_persists_all_feature_receipts_before_any_member_evaluates(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_current_scan -v
~~~

Expected: current scan module absent.

- [x] **Step 3: Implement exact current evaluation.**

Preflight latest completed bar for every frozen member before evaluating any.
At common as-of, fresh-load/fingerprint then resolve one full history/FeatureStore
per ticker/FeatureBuildContract union, apply only compatible historically
qualified definitions, and evaluate latest causal BUY predicate. Before current
features build, verify each SignalSet EvidenceSourceAnchor over its exact old
range: an appended bar is allowed only on an exact old-prefix match; correction,
unavailable old range, or moving start boundary requires requalification. Cache
reuse requires exact current source/contract match; a stale/corrupt cache rebuilds
and cannot become data_stale/no setup. Do not rerun train/test trade sequence or
discovery. Output current_setup_found only for valid/audit-eligible qualified
pair and model entry next session open.
After the all-member source recheck, persist a FeaturePlan/FeatureResolutionReceipt
per member/build contract before evaluating any current pair. A digest mismatch
or unavailable frozen build blocks the entire common-as-of scan rather than
mixing component bytes across members.
Before worker evaluation, re-preflight every frozen member against the request
fingerprints; any mismatch blocks the entire scan as source_changed and evaluates
none, preserving all-or-nothing common as-of.

- [x] **Step 4: Add compatibility/no-setup tests.**

~~~python
def test_corrected_history_requires_requalification_not_old_buy_setup(tmp_path): ...
def test_no_current_setup_requires_every_qualified_definition_successful(tmp_path): ...
def test_appended_bar_keeps_qualification_but_reports_evidence_age(tmp_path): ...
def test_cache_miss_or_write_failure_never_reports_no_current_setup(tmp_path): ...
def test_receipt_difference_blocks_whole_current_scan_before_any_pair(tmp_path): ...
def test_common_asof_source_mismatch_blocks_before_evaluating_any_member(tmp_path): ...
def test_member_change_after_ui_preflight_blocks_whole_scan_before_cache_reuse(tmp_path): ...
def test_append_is_allowed_only_when_old_evidence_prefix_matches(tmp_path): ...
def test_same_date_correction_or_moving_old_boundary_requires_requalification(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run current-scan suite. Record all-or-nothing common-as-of policy. Local and
Docker Flexible gates pass 189/189 plus compilation. Current scan writes
common-as-of, source/evidence-anchor, feature-receipt, and current result
artifacts; display-only and cache/receipt failures cannot become no setup.

### Task 5: Scale benchmark artifact and explicit scale policy

**Files:**

- Create: app/flexible_rulebook/benchmark.py
- Create: tests/test_flexible_rulebook_benchmark.py
- Create: docs/superpowers/reports/2026-08-25-flexible-rulebook-benchmark.md

**Consumes:** Campaign runner/current scan.

**Produces:**

~~~python
@dataclass(frozen=True)
class BenchmarkRecord: ...
@dataclass(frozen=True)
class ScalePolicy:
    max_current_scan_tickers: int
    max_discovery_attempt_count: int
    worker_count: int
    benchmark_report_hash: str

def validate_scale_policy(policy: ScalePolicy, record: BenchmarkRecord) -> None: ...
~~~

- [x] **Step 1: Write RED gate tests.**

~~~python
def test_default_policy_rejects_group_larger_than_fifteen(): ...
def test_policy_requires_matching_completed_benchmark_hash_for_two_workers(): ...
def test_discovery_policy_never_allows_more_than_fifteen_without_separate_record(): ...
def test_discovery_policy_requires_cold_p99_proof_for_fixed_attempt_cap(): ...
def test_discovery_cap_uses_maximal_train_test_write_slot_not_training_only_mean(): ...
def test_discovery_cap_subtracts_cold_preflight_p99_and_requires_one_hundred_maximal_slots(): ...
def test_policy_rejects_if_p99_cannot_finish_before_admission_and_terminal_deadlines(): ...
def test_fast_executor_cannot_enable_without_reference_parity_record(): ...
def test_append_extension_cannot_enable_without_prefix_and_full_rebuild_parity_record(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark -v
~~~

Expected: benchmark module absent.

- [x] **Step 3: Implement safe default gate.**

Default max current scan is 15 and worker_count is 1. A policy larger than 15
requires completed benchmark record containing actual 20/100/200 target
measurements, cold/warm p50/p95/p99 phase/total time, peak RSS, component-cache
bytes/hit/miss/partial-reuse coverage, DB connections, output bytes, retry/error totals, resume, duplicate-submit,
source-change, cache invalidation, and common-as-of result. Discovery benchmarking
also records candidate-space size, frozen strata/quotas, assigned/admitted/
completed/uncommitted/frozen-test counts, test work, cursor behavior, searched
fraction, entry-upper-bound rejections, FeaturePlan/receipt verification,
reference-versus-fast executor trade parity/work counters, append-extension
attempt/accept/fallback counts, and `time_budget_exhausted` behavior. The policy
derives a fixed cap from cold p99 **maximal slot** evidence (training plus an
eligible frozen test, selection/checkpoint, and write) that leaves the 4h30
admission boundary and 4h55 terminal deadline intact. It subtracts cold p99
source/feature preflight, requires at least 100 complete maximal-slot samples,
and budgets every admitted slot as maximal; warm cache may not raise it. A fast
executor or append extension remains disabled unless its own record
proves exact parity and a material measured improvement; fallback behavior is
always recorded. Do not auto-enable from a guessed threshold: policy is written
only after explicit review of recorded measurements. Discovery remains limited
until its separate benchmark record exists.

- [x] **Step 4: Run representative benchmark after tests pass.**

Run a deterministic cold/warm single-ticker discovery fixture first, including
the dense-entry/maximal-slot path and reference/fast parity corpus, then a
20-ticker representative current-scan fixture. Record actual results only; do
not invent timing, choose an attempt cap, enable append extension, or enable
100/200 if the container fails memory/time/resume criteria.

Checkpoint 2026-08-27: a synthetic 20-ticker current-scan fixture measured
0.473677s cold and 0.166481s warm in Docker, with 20 receipts and 20 immutable
result artifacts. A deterministic FPT-shaped discovery fixture then completed
100 cold plus 100 warm legal maximal train/test/selection/write samples:
cold p99 total 0.133270s and warm p99 total 0.110010s. Both fixtures exclude
production DB/source-load and resource telemetry, so they are evidence only;
they do not create a `BenchmarkRecord` or authorize a cap/worker/fast-path
expansion. See `docs/superpowers/reports/2026-08-25-flexible-rulebook-benchmark.md`.

- [x] **Step 5: Run GREEN and update status.**

Run benchmark suite. Publish report with measured totals and current scale gate.

### Task 6: Standalone Flexible Rulebook Streamlit page and navigation

**Files:**

- Create: app/pages/flexible_rulebook.py
- Modify: app/main.py
- Create: tests/test_flexible_rulebook_page.py

**Consumes:** Campaign runner, core service, current scan, benchmark policy.

**Produces:**

~~~python
def render_flexible_rulebook_page(
    engine,
    *,
    root: Path | None = None,
    root_resolver=resolve_flexible_root,
    service_factory=...,
    runner=...,
    group_snapshot_fn=...,
    cache_preflight_fn=...,
    rerun_fn=...,
) -> None: ...
~~~

- [x] **Step 1: Write RED AppTests.**

~~~python
def test_main_routes_to_standalone_flexible_rulebook_page(): ...
def test_page_has_discover_library_qualify_and_current_scan_sections(): ...
def test_current_scan_copy_uses_next_session_model_not_v3_can_buy(): ...
def test_page_does_not_import_or_call_backtest_pipeline(): ...
def test_duplicate_discover_uses_stable_default_seed_and_attaches(): ...
def test_new_sample_displays_new_persisted_seed_before_submit(): ...
def test_page_uses_single_radio_or_selectbox_workspace_not_eager_tabs(): ...
def test_verified_component_at_or_under_24h_requires_explicit_reuse_or_recalculate_choice(): ...
def test_expired_mismatched_or_corrupt_component_auto_rebuilds_without_prompt(): ...
def test_enabled_append_extension_is_labeled_reuse_only_and_recalculate_forces_full_build(): ...
def test_running_campaign_shows_feature_plan_receipt_status_without_exposing_cache_paths(): ...
def test_page_uses_resolved_absolute_root_not_current_working_directory(): ...
def test_continue_has_no_editable_source_seed_catalog_or_cache_choice(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_page -v
~~~

Expected: page/route absent.

- [x] **Step 3: Implement page controls and rendering.**

Add sidebar option Flexible Rulebook only. Use one `st.radio` or selectbox
workspace selector, never `st.tabs`, because all Streamlit tab bodies execute.
Render the four design workspaces:

1. Discover: permanent `Exploratory — gross. Manual research; no orders.`;
   source ticker; finite catalog snapshot; candidate-space size; benchmark-backed
   fixed cap/runtime preview; visible seed initialized to `frb-default-seed-v1`;
   New Sample creates/displays `uuid.uuid4().hex`; and fresh source/cache
   preflight before a campaign exists. A compatible <=24h component offer becomes
   an inline blocking Reuse valid components / Recalculate all panel; neither is
   silently selected. Label per-contract partial reuse/count of missing
   components and Persistence: unverified development storage. Once resolution
   completes, show a concise `Feature plan verified` receipt status without
   exposing cache paths or digests. If worker source,
   contract, or cache age recheck differs, render the safe state and require a
   new preflight rather than applying stale choice. Lock draft input while a
   campaign runs. If the library has no Flexible definitions or signal-set
   evidence, name the configured root, explain the benchmark-gated Discover
   state, and state that legacy V3 artifacts are excluded.
2. Rulebook Library: page/filter immutable definitions/evaluations. Show alias
   plus short/full ID, feature profile, source/split, both train/test gross
   metrics, training rank, selection scope state, selection status, duplicate
   blocker/75% overlap, and
   artifact/detail/download links. Keep rejected near-duplicates retrievable in
   a collapsed evidence section.
3. Cross-ticker Qualification: select available immutable IDs and one ticker or
   named Group from read-only selector options, preview frozen members, then
   render a preflight table grouped by ticker/build contract and one batch
   component-choice per group. No V3 N/A/group helper is called.
4. Current Group BUY Scan: named Group only; show common-as-of preflight first,
   one cache table/choice next, then compatible qualified-pair results. Positive
   output is exactly BUY setup — next-session open model, manual research, not
   trading advice.

Running capsules show source/cache phase, HCM timestamp, elapsed/remaining
window, training attempted/assigned, frozen/tested, stratum coverage, threshold
funnel, selected hard-distinct count, artifact, safe error code, cancellation,
resume, and precise `time_budget_exhausted` state. Continue derives from only
persisted parent values and creates a linked campaign from next_slot; duplicate
Discover attaches to exact request rather than replaying its prefix. Polling
never reopens a cache choice. Use no forms that mutate Positions, Backtest, V3
groups, or actual trading.

- [x] **Step 4: Add cached-status/filter tests.**

~~~python
def test_status_filters_never_replay_campaign_work(): ...
def test_blocked_common_as_of_displays_laggards_and_no_buy_conclusion(): ...
def test_scale_gate_explains_200_ticker_scan_is_disabled_before_benchmark(): ...
def test_continue_discovery_uses_next_slot_and_displays_within_budget_scope(): ...
def test_cache_preflight_choice_is_not_reopened_during_status_polling(): ...
def test_group_component_table_has_one_action_per_contract_with_mixed_coverage(): ...
def test_time_budget_progress_never_claims_global_search_progress(): ...
def test_library_pagination_alias_collision_and_duplicate_evidence_are_read_only(): ...
def test_library_reads_latest_chain_selection_snapshot_without_mutating_signal_set(): ...
~~~

- [x] **Step 5: Run final focused gate and completion review.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_contracts tests.test_flexible_rulebook_history tests.test_flexible_rulebook_catalog tests.test_flexible_rulebook_features tests.test_flexible_rulebook_primitive_cache tests.test_flexible_rulebook_execution tests.test_flexible_rulebook_metrics tests.test_flexible_rulebook_search tests.test_flexible_rulebook_storage tests.test_flexible_rulebook_service tests.test_flexible_rulebook_campaigns tests.test_flexible_rulebook_runner tests.test_flexible_rulebook_group_adapter tests.test_flexible_rulebook_current_scan tests.test_flexible_rulebook_benchmark tests.test_flexible_rulebook_page -v
docker exec stock_app python -m compileall -q flexible_rulebook pages/flexible_rulebook.py main.py
~~~

Expected: all focused tests and compilation pass. Then run implementation review,
update FOCUS/current-status, and publish an evidence report with actual totals.
Do not claim 100–200 support until Task 5 policy is backed by measured evidence.

## Campaign plan self-review

- Coverage: durable jobs, frozen-source Continue/cache exception, seeded
  stratified frontier idempotency, under-five-hour timing, retry/cancel/resume,
  Group portability/cache batch preflight, common as-of/no false no-setup,
  p99 scale gate, timing-distinct library evidence, and standalone UI each have
  own task and test gate.
- Failure safety: shared outage is blocked, source correction is
  requalification/source_changed where required, cache failure is uncached
  rebuild, persisted assignment prevents repeat search slots, deadline leaves an
  uncommitted exact cursor, and per-target failure never becomes market-wide
  absence.
- Deliberate ceiling: one global worker/default 15 target Group uses a
  ponytail comment and has an explicit benchmark upgrade path.
- No V3 coupling: page and worker never consume V3 pipeline/status/artifacts;
  Group adapter is read-only named-group lookup only. The page uses radio/select
  workspaces rather than eager Streamlit tabs and contains no Position/trade
  action.
