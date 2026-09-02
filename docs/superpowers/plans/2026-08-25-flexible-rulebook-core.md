# Flexible Rulebook Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax for tracking. Do not commit, stage, inspect, or run Git commands.

**Goal:** Build isolated, deterministic Flexible Rulebook core services that define portable Swing rulebooks, discover finite causal candidates, evaluate them in frozen train/test partitions, and persist reusable evidence.

**Architecture:** New app/flexible_rulebook package owns all contracts, fresh-source validation, frozen feature-build semantics, reusable primitive components, daily array execution, metrics, structurally stratified search, and storage. It reads raw history only through a Flexible-owned adapter around existing bounded loader; it does not call V3 pipeline, models, indicators, persistence, job runner, or artifact readers. Campaigns/UI arrive in the dependent plan.

**Tech Stack:** Python 3.12, pandas, NumPy already available in project, SQLAlchemy Core/text through existing loader, unittest, Docker.

**Status:** Tasks 1–8 complete and verified (2026-08-28). Task 3 catalog,
causal FeatureStore, request-scoped resolution receipt, and safe persistent
computed-component cache are implemented (2026-08-27). Task 4 reference
executor and its inert identity-bound, benchmark-gated event-plan guard are
implemented (2026-08-27). Host and canonical Docker focused Flexible suites
pass 73/73 and compilation passes. Catalog v1 fixes the automatic ATR variant
at stop 2.0×, target 3.0×, no trailing (plus allowed no-price-exit). Task 6 is
complete (2026-08-27): seeded structural strata,
frozen quotas, continuation-safe affine traversal, deadline truth, compact
rejections, and frozen train/test typed evidence. Core Docker gate passes 80/80
plus compilation. Task 7 is complete: immutable Flexible-only definitions,
signal sets, receipt-bound provenance ledgers, verified Continue selection
chains, and cache-excluding signal-set traversal pass the full Flexible Docker
gate (96/96) plus compilation. Campaign manifest/resume cursor wiring belongs
to the dependent Campaigns and Current Scan plan.

**Task 5 completion (2026-08-26):** immutable partition trade evidence,
selection-scope validation, first-inclusive-overlap two-pointer timing evidence,
exact 75% training duplicate filtering, and deterministic training-only Top 3
selection are implemented. Focused Flexible Docker gate passes 56/56 and
compilation passes. Task 4 execution parity coverage and Task 6 discovery
coverage are complete.

**Catalog v1 lock (2026-08-26):** fast-first Swing values are EMA `(3,8)`,
`(5,13)`, `(5,21)`, `(8,21)`; RSI periods `5/9/14`, levels `50/52/55`;
breakouts `10/20/40`; relative-volume windows `5/10/20`, minima
`1.10/1.20/1.30`; fixed ADX(14) minima `15/20/25`; mirrored technical exits; timeout
`10/15/22/30`; fixed ATR(14). Automatic conjunctions cap BUY and gate/filter
subsets at two each. Task 3 catalog/cache is implemented from this exact
snapshot.

**Correctness remediation (2026-08-28):** complete cache hits now assemble raw
arrays without recalculating indicators; OHLC quality ratios exclude volume;
discovery deadline counters preserve the global cursor; ticker and group
qualification require an explicit valid cache choice and the frozen request
split/plan hashes; audit-only targets remain data-ineligible instead of being
reported as no-candidate. Signal-set reads verify path, receipt, anchor, and
skip corrupt legacy entries. Continue recomputes Top 3 from all committed
qualified evidence in the verified parent chain. The focused Flexible Docker
gate passes 219/219 plus compilation.

## Global Constraints

- Implement docs/superpowers/specs/2026-08-25-flexible-rulebook-design.md exactly.
- Daily Swing only; long-only; next-open entry; minimum hold exactly 3; max hold 4..64.
- All predicates must be causal; no future value reaches a live predicate.
- Full selected 15 years split 10y/5y; shorter usable history splits 65%/35%.
- Keep only completed trades fully inside train or test; test gets causal training warm-up but starts flat.
- Both train and test must satisfy n >= 12, win_rate >= 65, mean_return_pct >= 15 for threshold qualification.
- Rank only training win_rate, mean_return_pct, Sharpe, lexical rulebook_id. Select up to three greedily hard-distinct representatives using training overlap_ratio >= 0.75; never backfill a near-duplicate.
- Preserve all candidate definitions in compact ledger; detailed signals/trades only for qualified or explicitly saved sets.
- Candidate space must stay lazy; discovery assignment is seeded, reproducible,
  ticker-specific, and never changes rulebook identity.
- A request freezes exact candidate count, structural stratum quotas, frozen test behavior, runtime budget, and selection policy before results. Cache warmth, train outcomes, and test outcomes never reallocate slots or quotas.
- Per ticker use monotonic candidate admission deadline 16,200 seconds and normal terminal deadline 17,700 seconds; the outer 18,000-second worker watchdog is fail-safe only. Source/cache/feature/test/write time all count.
- Fresh-load and fingerprint ordered raw OHLCV before every new operation. A <=24-hour compatible cache is a user choice only; age never proves cache validity. Continue has the frozen-source exception from the design.
- Persist individual primitive components only; never persist candidate masks, execution plans, trades, metrics, or rankings as cache.
- Candidate loop uses raw NumPy arrays and bounded memory; no DB call, pandas deep copy/reset/reindex, or candidate-by-bar matrix.
- Use raw BIGINT-derived prices internally; UI scaling is outside this plan.
- Timezone is Asia/Ho_Chi_Minh.
- Never modify common_queries.py, data-preparation scaling/retry, V3 source/artifacts, positions, database schema, Docker, dependencies, or credentials.
- No Git action, commit, staging, reset, or Git command.

---

## File map

| File | Responsibility |
|---|---|
| app/flexible_rulebook/__init__.py | Explicit public core API only. |
| app/flexible_rulebook/contracts.py | Frozen dataclasses, canonical JSON/hash, safe enum/state values, animal alias. |
| app/flexible_rulebook/catalog.py | Catalog revision 1 predicate metadata and finite definition validation. |
| app/flexible_rulebook/history.py | Bounded Flexible history adapter, quality outcome, SHA-256 fingerprint, split. |
| app/flexible_rulebook/features.py | Causal raw-array FeatureStore, primitive arrays/masks, lazy mask composition. |
| app/flexible_rulebook/primitive_cache.py | Validated per-component preflight, atomic primitive-cache read/build/write, request-scoped bundle assembly. |
| app/flexible_rulebook/execution.py | Flat-to-flat next-open BUY/SELL state machine and completed trade records. |
| app/flexible_rulebook/metrics.py | Partition metrics, threshold qualification/rank, pair timing, hard-distinct Top 3 selection. |
| app/flexible_rulebook/search.py | Lazy CandidateSpace, stratified seeded time-bounded discovery, frozen test candidates, compact ledger rows. |
| app/flexible_rulebook/storage.py | Flexible-only schema-1 documents and atomic artifact/ledger writes. |
| app/flexible_rulebook/service.py | Single-ticker discovery and cross-ticker qualification orchestration. |
| tests/test_flexible_rulebook_*.py | Focused RED/GREEN contract coverage. |
| FOCUS.md, ai-context/current-status.md | Task progress and stopping point after every completed task. |

### Task 1: Immutable contracts, canonical identity, and animal aliases

**Files:**

- Create: app/flexible_rulebook/__init__.py
- Create: app/flexible_rulebook/contracts.py
- Create: tests/test_flexible_rulebook_contracts.py

**Consumes:** Standard library dataclasses, hashlib, json, datetime, pathlib.

**Produces:**

~~~python
@dataclass(frozen=True)
class RulebookDefinition: ...
@dataclass(frozen=True)
class ExecutionContract: ...
@dataclass(frozen=True)
class EvaluationSplit: ...
@dataclass(frozen=True)
class RuntimeBudget: ...
@dataclass(frozen=True)
class FeatureProfile: ...
@dataclass(frozen=True)
class FeatureBuildContract: ...
@dataclass(frozen=True)
class PrimitiveKey: ...
@dataclass(frozen=True)
class FeaturePlan: ...
@dataclass(frozen=True)
class FeatureResolutionReceipt: ...
@dataclass(frozen=True)
class SelectionPolicy: ...
@dataclass(frozen=True)
class PartitionMetrics: ...
@dataclass(frozen=True)
class RulebookEvaluation: ...
def canonical_json(value: object) -> str: ...
def rulebook_id(definition: RulebookDefinition) -> str: ...
def animal_alias(rulebook_id: str) -> str: ...
~~~

- [x] **Step 1: Write failing identity tests.**

~~~python
def test_rulebook_hash_excludes_ticker_and_metrics():
    definition = _definition()
    self.assertEqual(rulebook_id(definition), rulebook_id(_definition()))
    self.assertTrue(rulebook_id(definition).startswith("frb_"))

def test_semantic_setting_change_creates_new_rulebook_id():
    self.assertNotEqual(rulebook_id(_definition(max_hold_bars=22)),
                        rulebook_id(_definition(max_hold_bars=23)))

def test_alias_is_deterministic_but_not_identity():
    first = animal_alias(rulebook_id(_definition()))
    self.assertRegex(first, r"^[A-Z][a-z]+-[A-Z][a-z]+$")

def test_selection_policy_locks_training_overlap_threshold():
    self.assertEqual(SelectionPolicy().training_overlap_ratio, Decimal("0.75"))

def test_runtime_budget_rejects_deadlines_outside_under_five_hour_contract():
    self.assertEqual(RuntimeBudget().candidate_admission_seconds, 16_200)
    self.assertEqual(RuntimeBudget().normal_terminal_seconds, 17_700)

def test_feature_build_contract_and_primitive_key_include_all_causal_revisions(): ...
def test_feature_build_contract_freezes_optional_append_stream_state_schema(): ...
def test_enabled_append_extension_algorithm_revision_changes_component_identity(): ...
def test_feature_plan_is_derived_from_snapshot_contract_and_profile_not_cache_state(): ...
def test_receipt_identity_is_component_keys_and_digests_not_cache_path_or_age(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_contracts -v
~~~

Expected: import failure because Flexible package does not exist.

- [x] **Step 3: Implement minimal canonical contracts.**

~~~python
def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def rulebook_id(definition: RulebookDefinition) -> str:
    digest = hashlib.sha256(canonical_json(definition.to_semantic_dict()).encode()).hexdigest()
    return f"frb_{digest}"
~~~

Reject ticker/date/metric/result fields from semantic definition. Require at least
one BUY predicate, finite settings, strictly positive finite enabled ATR
stop/target/trailing multipliers, min_hold_bars==3, and 4 <= max_hold_bars <= 64.
`FeatureProfile` canonicalizes requested primitive family/settings only.
`FeatureBuildContract` canonically freezes feature algorithm, warm-up, quality,
numeric, raw-scale, cache-schema, and optional append-stream-state-schema
revisions; it belongs to evaluation/campaign identity but not rulebook identity.
Numeric runtime revision explicitly covers NumPy/pandas behavior and Flexible
numeric implementation revisions.
Any enabled append-extension algorithm revision is part of its feature-algorithm
revision. The initial contract declares append extension disabled.
`PrimitiveKey` hashes FeatureSnapshot, FeatureBuildContract, and exactly one
primitive spec. `FeaturePlan` is the
canonical ordered primitive-key set derived from a snapshot/contract/profile;
`FeatureResolutionReceipt` canonically records that plan's resolved keys and
component digests (all arrays plus causal state) before candidate evaluation.
Neither includes cache path, age, hit,
or rebuild choice. `SelectionPolicy` is
evaluation/campaign provenance, not a rulebook identity, and fixes
`timing-distinct-top3-v1` plus Decimal("0.75").
`RuntimeBudget` rejects a candidate admission deadline above 16,200, a normal
terminal deadline above 17,700, or a non-positive/incorrect ordering.

- [x] **Step 4: Run GREEN and invalid-contract coverage.**

~~~python
def test_definition_rejects_empty_buy_and_nonportable_fields():
    with self.assertRaises(ValueError):
        RulebookDefinition(buy_predicates=(), gates=(), filters=(), exits=(), max_hold_bars=64)

def test_definition_rejects_zero_or_negative_atr_exit_multiplier(): ...
def test_feature_profile_change_creates_new_profile_hash_not_rulebook_id(): ...
def test_cache_metadata_cannot_enter_semantic_or_request_material(): ...
def test_every_feature_build_contract_field_changes_primitive_key(): ...
def test_threshold_change_reuses_base_component_but_changes_predicate_mask(): ...
def test_receipt_digest_change_is_detected_without_changing_rulebook_id(): ...
~~~

Run same command. Expected: all tests pass.

- [x] **Step 5: Update FOCUS/current-status.**

Record Task 1 complete, exported API, exact focused test total, and no V3 change.

### Task 2: Bounded history, quality, fingerprint, and deterministic split

**Files:**

- Create: app/flexible_rulebook/history.py
- Create: tests/test_flexible_rulebook_history.py

**Consumes:** RulebookDefinition and only the existing bounded
backtest_engine.data_quality.load_ticker_history adapter. Flexible owns its
quality/audit policy and imports no V3 validation helper.

**Produces:**

~~~python
@dataclass(frozen=True)
class HistorySnapshot:
    ticker: str
    frame: pd.DataFrame
    fingerprint: str | None
    quality_state: Literal["eligible", "display_only", "invalid"]
    requested_start: date
    requested_as_of: date
    first_date: date | None
    as_of_date: date | None
    evidence_prefix_fingerprint: str | None

@dataclass(frozen=True)
class EvidenceSourceAnchor:
    ticker: str
    requested_start: date
    requested_as_of: date
    first_date: date
    as_of_date: date
    prefix_fingerprint: str

def load_flexible_history(engine, ticker: str, as_of: date | None = None) -> HistorySnapshot: ...
def make_evaluation_split(snapshot: HistorySnapshot) -> EvaluationSplit: ...
def trade_dates_belong_to_partition(signal_date: date, entry_date: date,
                                    exit_date: date,
                                    partition: EvaluationPartition) -> bool: ...
def verify_evidence_source_anchor(engine, anchor: EvidenceSourceAnchor) -> Literal["match", "changed", "unavailable"]: ...
~~~

- [x] **Step 1: Write failing loader/split tests.**

~~~python
def test_split_uses_first_native_bar_on_or_after_calendar_cutoff():
    split = make_evaluation_split(_snapshot("2011-01-03", "2026-01-02"))
    self.assertEqual(split.method, "calendar_10y_5y")
    self.assertEqual(split.test_start, date(2021, 1, 4))

def test_short_history_uses_single_chronological_65_35_boundary():
    split = make_evaluation_split(_snapshot("2019-01-02", "2026-01-02"))
    self.assertEqual(split.method, "chronological_65_35")
    self.assertGreater(split.test_start, split.train_start)
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_history -v
~~~

Expected: missing history module/API.

- [x] **Step 3: Implement Flexible-owned adapter.**

Use only parameterized existing loader with explicit earliest date and frozen
as-of date. The earliest date is exactly 15 calendar years before requested
as-of (29 February maps to 28 February). Preserve requested start/as-of with
native first/last dates. Derive
the full-window cutoff from requested_as_of, then choose the first native bar
on or after it as test_start and the preceding native bar as train_end. Reject
a full-window snapshot with no native bar at/after cutoff. A full calendar
window permits its first native bar through seven calendar days after requested
start; any materially later first bar is shorter usable history and uses the
single chronological 65%/35% split. Validate raw OHLCV
without modifying raw source. Flexible-owned quality marks malformed columns,
date order/duplicates, non-finite or non-positive OHLC, and negative volume
`invalid`; it marks an OHLC ordering mismatch above 1% of maximum bar OHLC or
an adjacent close discontinuity >=15% `display_only`; warnings alone remain
usable. Fingerprint ordered raw ticker/date/open/high/low/close/volume rows with
SHA-256. Never normalize raw data in place.

Every new operation calls this loader before it can inspect a persistent feature
bundle. Do not validate a cache with only ticker/latest date/row count: an
ordered same-date historical correction must change `fingerprint`. Continue
calls the same bounded loader only to verify its persisted source fingerprint;
it may then rebuild identical features from that frozen source, never silently
switch to a new snapshot.
Define `EvidenceSourceAnchor` with exact requested/actual bounds, historical
as-of, and prefix fingerprint; Task 6 persists it for every evaluation. Later
current scans query
that old range and compare its prefix before treating append-only latest data as
compatible; unavailable old range/moving window is not append proof.

- [x] **Step 4: Add boundary tests.**

~~~python
def test_split_drops_crossing_trade_by_dates_not_row_count():
    split = make_evaluation_split(_snapshot())
    self.assertFalse(trade_dates_belong_to_partition(date(2020, 12, 31), date(2021, 1, 4), date(2021, 1, 8), split.training))

def test_holiday_cutoff_uses_first_available_native_bar(): ...
def test_full_window_without_native_test_bar_fails_explicitly(): ...
def test_same_as_of_and_row_count_but_corrected_close_changes_fingerprint(): ...
def test_ordered_volume_and_date_changes_change_fingerprint(): ...
def test_append_changes_fingerprint_while_prior_evidence_remains_historical(): ...
def test_evidence_anchor_accepts_append_but_rejects_same_date_correction(): ...
def test_evidence_anchor_rejects_unavailable_old_range_or_moving_start_boundary(): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run history tests. Record test total and explicit adapter-only V3 reuse.

### Task 3: Finite catalog, causal FeatureStore, and persistent primitive cache

**Files:**

- Create: app/flexible_rulebook/catalog.py
- Create: app/flexible_rulebook/features.py
- Create: app/flexible_rulebook/primitive_cache.py
- Create: tests/test_flexible_rulebook_catalog.py
- Create: tests/test_flexible_rulebook_features.py
- Create: tests/test_flexible_rulebook_primitive_cache.py

**Consumes:** contracts.py and validated HistorySnapshot.

**Produces:**

~~~python
@dataclass(frozen=True)
class CatalogRevision: ...
def catalog_revision_1() -> CatalogRevision: ...
@dataclass
class FeatureStore: ...
@dataclass(frozen=True)
class CacheOffer: ...
@dataclass(frozen=True)
class FeaturePreflight:
    snapshot: HistorySnapshot
    build_contract: FeatureBuildContract
    feature_plan: FeaturePlan
    cache_offer: CacheOffer
@dataclass(frozen=True)
class FeatureResolution:
    store: FeatureStore
    plan: FeaturePlan
    receipt: FeatureResolutionReceipt
def feature_profile(catalog: CatalogRevision) -> FeatureProfile: ...
def current_feature_build_contract() -> FeatureBuildContract: ...
def build_feature_store(snapshot: HistorySnapshot, contract: FeatureBuildContract,
                        profile: FeatureProfile) -> FeatureStore: ...
def primitive_mask(store: FeatureStore, predicate: PredicateSpec) -> np.ndarray: ...
def compose_entry_mask(store: FeatureStore, definition: RulebookDefinition) -> np.ndarray: ...
def inspect_primitive_cache(snapshot, contract: FeatureBuildContract,
                            profile: FeatureProfile, root: Path, now: datetime) -> CacheOffer: ...
def resolve_feature_store(snapshot, contract: FeatureBuildContract,
                          profile: FeatureProfile, root: Path,
                          choice: Literal["reuse", "rebuild"], now: datetime) -> FeatureResolution: ...
~~~

- [x] **Step 1: Write RED causal tests.**

~~~python
def test_relative_volume_excludes_current_bar_from_baseline():
    store = build_feature_store(_snapshot_with_volume([10, 10, 10, 100]), _profile())
    self.assertEqual(store.relative_volume[3], 10.0)

def test_breakout_uses_prior_high_not_current_high():
    store = build_feature_store(_breakout_snapshot(), _profile())
    self.assertTrue(primitive_mask(store, _breakout_3())[3])

def test_shared_rsi14_reuses_when_second_profile_adds_ema21(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_catalog tests.test_flexible_rulebook_features tests.test_flexible_rulebook_primitive_cache -v
~~~

Expected: missing catalog/features APIs.

- [x] **Step 3: Implement catalog revision 1, FeatureStore, and cache.**

Implement exactly BUY EMA bullish cross/RSI upcross/prior-high breakout;
EMA-up/relative-volume/ADX gates; EMA bearish/RSI down/prior-low breakdown
technical exits; ATR stop/target/trailing configuration. `FeatureStore` owns
read-only raw integer arrays, dates, causal primitive arrays, and primitive
auxiliary state. Build predicate Boolean masks only in memory from those base
arrays, so a threshold change (for example RSI 52 to 55) reuses RSI(14) rather
than writing a second persistent component. Use prior-only rolling windows and
explicit finite/non-null masks.
Multiple selected technical SELL predicates form one lazy AND mask; zero selected
technical SELL predicates produce no technical-exit mask. Do not import V3
indicators or build a DataFrame per candidate.

Key each PrimitiveComponent by SHA-256 of cache schema, full FeatureSnapshot
(ticker/fingerprint/exact bounds/as-of), FeatureBuildContract, and one primitive
family/settings instance. Store canonical key payload and component digest over
every numeric array/causal-state value in its manifest. A FeatureBundle is
request-scoped assembly only, so adding an
unrelated primitive reuses existing components. Read `.npz` only with
`allow_pickle=False`; validate manifest, array names, dtypes, shapes, date order,
key payload, and causal digest before use. Recalculate of same PrimitiveKey must
match stored digest; otherwise retain old component and emit
FEATURE.NONDETERMINISTIC_BUILD. Write a component via same-directory temporary
file, flush/fsync, atomic replace, contained hash-only path, and a per-key lease
with bounded wait. A corrupt/missing/partial/locked/low-space/write failure is a
safe uncached build, never ticker failure. Require free disk >= component bytes
plus 512 MiB before a cache write. Never persist raw source, composed masks, exit
plans, trade outcomes, test results, or ranking.

Define `component_digest` as SHA-256 over canonical PrimitiveKey payload, sorted
array names, dtype, shape, C-order bytes, and canonical causal stream-state
payload—not compressed `.npz` bytes, timestamp, file path, or cache metadata.

For a new request, `inspect_primitive_cache` receives an already freshly
fingerprinted snapshot and returns component coverage. If at least one required
component is fresh at `age <= 24h`, it yields one Reuse-valid-components/
Recalculate-all offer; `age > 24h` or negative age rebuilds that component.
Store successful calculation completion and compare age using
Asia/Ho_Chi_Minh-aware datetimes. Worker start remeasures age after source
verification. Resume/Continue calls this module in frozen mode: no prompt;
reuse compatible components or rebuild only under the persisted FeatureBuildContract.
If that contract cannot be provided by the runtime, return
FEATURE.REVISION_UNAVAILABLE without cursor advance.
Before a discovery slot can commit, return the canonical FeaturePlan plus a
FeatureResolutionReceipt with every component digest; storage/campaign code
persists it atomically. A resume/Continue rebuild after cache eviction is valid
only when it reproduces the receipt exactly. Initial core behavior for an
appended/corrected source is a new-key full rebuild. Keep an
`append_extension_v1` seam disabled until a separate benchmark and exact-digest
parity gate approve it; a correction never uses that seam.

- [x] **Step 4: Add no-look-ahead and catalog-validation tests.**

~~~python
def test_future_mutation_does_not_change_prior_feature_rows():
    first = build_feature_store(_snapshot(), _profile())
    changed = _snapshot_with_last_close_multiplied(9)
    second = build_feature_store(changed, _profile())
    np.testing.assert_allclose(first.rsi[:-1], second.rsi[:-1], equal_nan=True)

def test_two_selected_technical_sell_predicates_require_both_true(): ...
def test_zero_selected_technical_sell_predicates_never_queue_exit(): ...
def test_catalog_rejects_zero_or_negative_atr_exit_multiplier(): ...
def test_verified_reuse_and_rebuild_have_identical_primitive_digest(tmp_path): ...
def test_exact_24h_cache_age_offers_choice_but_over_24h_rebuilds(tmp_path): ...
def test_partial_component_coverage_reuses_rsi14_and_builds_only_missing_ema21(tmp_path): ...
def test_worker_age_crossing_24h_after_ui_offer_rebuilds_without_second_prompt(tmp_path): ...
def test_corrected_history_same_asof_is_cache_miss(tmp_path): ...
def test_changed_period_creates_only_new_component_but_threshold_change_reuses(tmp_path): ...
def test_same_key_recalculate_digest_mismatch_keeps_old_component_and_fails_safe(tmp_path): ...
def test_component_digest_covers_array_name_dtype_shape_bytes_and_stream_state_not_npz_metadata(tmp_path): ...
def test_every_snapshot_contract_and_primitive_field_changes_component_key(tmp_path): ...
def test_feature_resolution_receipt_is_identical_for_verified_reuse_and_rebuild(tmp_path): ...
def test_receipt_mismatch_after_cache_eviction_blocks_resume_without_cursor_advance(tmp_path): ...
def test_append_extension_is_disabled_by_default_and_correction_never_uses_it(tmp_path): ...
def test_enabled_append_extension_requires_exact_prefix_stream_state_and_full_rebuild_digest_parity(tmp_path): ...
def test_append_extension_is_offered_only_in_reuse_branch_at_or_under_24h(tmp_path): ...
def test_corrupt_npz_wrong_dtype_shape_or_pickle_is_rebuilt_not_trusted(tmp_path): ...
def test_interrupted_write_stale_lease_low_disk_and_write_failure_continue_uncached(tmp_path): ...
def test_cache_root_is_never_discovered_as_rulebook_or_signal_artifact(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run all three suites. Record catalog/profile hashes, cache schema/revisions,
unsupported indicator list, and cache failure-as-safe-miss contract.

### Task 4: Daily flat-to-flat execution engine

**Files:**

- Create: app/flexible_rulebook/execution.py
- Create: tests/test_flexible_rulebook_execution.py

**Consumes:** RulebookDefinition, FeatureStore lazy masks, EvaluationSplit, RuntimeBudget checkpoint.

**Produces:**

~~~python
@dataclass(frozen=True)
class CompletedTrade:
    trade_id: str
    signal_date: date
    entry_date: date
    exit_date: date
    signal_bar_ordinal: int
    entry_bar_ordinal: int
    exit_bar_ordinal: int
    entry_price: int
    exit_price: float
    exit_reason: str
    return_pct: float

@dataclass(frozen=True)
class EventExitPlan: ...

def execute_rulebook_reference(store: FeatureStore, entry_mask: np.ndarray,
                               technical_exit_mask: np.ndarray | None,
                               definition: RulebookDefinition, partition: EvaluationPartition,
                               *, should_stop: Callable[[], bool] | None = None) -> tuple[CompletedTrade, ...]: ...
def build_event_exit_plan(store: FeatureStore, technical_exit_mask: np.ndarray | None,
                          definition: RulebookDefinition, partition: EvaluationPartition,
                          receipt_digest: str) -> EventExitPlan | None: ...
def execute_rulebook(store: FeatureStore, entry_mask: np.ndarray,
                     technical_exit_mask: np.ndarray | None,
                     definition: RulebookDefinition, partition: EvaluationPartition,
                     *, event_plan: EventExitPlan | None = None,
                     should_stop: Callable[[], bool] | None = None) -> tuple[CompletedTrade, ...]: ...
~~~

- [x] **Step 1: Write RED execution-order tests.**

~~~python
def test_buy_at_close_signal_enters_next_raw_open():
    trade = execute_rulebook(_store_with_buy(2), _mask(2), _none(), _definition(), _partition())[0]
    self.assertEqual((trade.signal_date, trade.entry_date, trade.entry_price),
                     (date(2026, 1, 5), date(2026, 1, 6), 10100))

def test_stop_first_and_minimum_hold_block_early_exit():
    trade = execute_rulebook(_store_with_dual_hit_before_hold(), _mask(0), _none(), _definition(), _partition())[0]
    self.assertEqual(trade.exit_date, date(2026, 1, 7))
    self.assertEqual(trade.exit_reason, "stop_loss")

def test_test_partition_starts_flat_after_crossing_training_trade(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_execution -v
~~~

Expected: missing state-machine API.

- [x] **Step 3: Implement the authoritative reference state machine.**

Use raw next open, one active position, E+3 earliest exit, and one immediate
technical-exit queue only when its next raw-open fill is legal. Discard rather
than defer/recheck technical SELL signals whose next open is before E+3 or
after deadline. Process a legal queued technical open exit before price checks;
otherwise process raw-open price gaps, then intrabar price levels, then deadline
raw-close timeout. Freeze signal ATR; retain fractional computed thresholds and
returns without int/display rounding; use max(static_stop, trailing_stop) for
enabled long stops; use high_water starting at entry and prior-only trailing
state; stop-first; and E+63 deadline for 64 inclusive bars. Emit deterministic
trade IDs and full-frozen-snapshot native-bar ordinals for signal, entry, and
exit. Drop no-exit trades.
Operate on raw arrays rather than a copied/sliced DataFrame. Check an injected
deadline/cancellation function at deterministic bounded bar chunks and return an
uncommitted-slot sentinel before ledger write when time expires; never persist a
partial trade sequence as a candidate rejection.

- [x] **Step 4: Add deadline/technical/trailing tests.**

~~~python
def test_deadline_uses_close_only_after_open_queue_and_price_checks(): ...
def test_trailing_stop_cannot_use_current_high_to_raise_same_bar_threshold(): ...
def test_open_position_suppresses_second_buy_signal(): ...
def test_blocked_technical_exit_is_discarded_not_deferred(): ...
def test_technical_exit_at_close_e_plus_2_fills_open_e_plus_3_without_recheck(): ...
def test_later_legal_technical_exit_is_not_replaced_by_blocked_signal(): ...
def test_blocked_price_hit_is_not_backfilled(): ...
def test_deadline_minus_one_technical_signal_fills_deadline_open(): ...
def test_deadline_close_technical_signal_cannot_bypass_timeout(): ...
def test_static_and_trailing_stop_use_tighter_long_stop(): ...
def test_fractional_atr_threshold_is_not_truncated_before_return(): ...
def test_queued_technical_open_beats_same_bar_price_exit(): ...
def test_gap_price_exit_uses_raw_open_not_threshold(): ...
def test_deadline_interrupt_leaves_candidate_slot_uncommitted_for_resume(): ...
def test_execution_uses_feature_store_arrays_without_dataframe_copy(): ...
~~~

- [x] **Step 5: Add a benchmark-gated fast-path parity layer.**

Keep `execute_rulebook_reference` as the oracle. Build an EventExitPlan only for
an exact source/receipt/technical-mask/price-exit/partition tuple; otherwise
return no plan and run the reference path. The optimized path may jump between
known entries and known eligible exit events, but it must retain every bar that
can alter trailing state, price fill, or deadline semantics. It must never
change candidate ordering, deadline checkpoints, memo identity, or evidence.
Enable it only after the benchmark gate records deterministic equality against
the reference executor.

~~~python
def test_event_path_matches_reference_for_every_exit_precedence_case(): ...
def test_event_path_matches_reference_on_seeded_sparse_and_dense_signal_fixtures(): ...
def test_event_plan_rejects_different_source_receipt_mask_or_partition(): ...
def test_unsupported_event_plan_falls_back_to_reference_without_result_change(): ...
def test_event_path_preserves_deadline_checkpoint_and_uncommitted_slot_contract(): ...
def test_performance_work_counter_is_lower_or_equal_without_wall_clock_assertion(): ...
~~~

- [x] **Step 6: Run GREEN and update status.**

Run execution suite. Record every exit precedence rule, reference/fast parity
gate, and benchmark-only enablement in status note.

### Task 5: Partition metrics, qualification, rank, and sensitivity

> **Resolved 2026-08-26:** `RulebookEvaluation` owns typed ordered
> `training_trades` and `test_trades` evidence tuples, whose counts match their
> partition metrics. They are evaluation evidence only, never `rulebook_id`.
> `compare_entry_timing()` reads those tuples and never derives intervals from
> aggregates or performs an implicit artifact lookup.

> **Sensitivity/Top 3 design approved 2026-08-26:** pair inclusive intervals
> using the specified first-overlap two-pointer walk. Before ranking/selection,
> require one selection scope: identical ticker, raw source fingerprint, split,
> and execution revision. Rank only threshold-qualified evaluations by training
> win rate, mean return, finite Sharpe/null Sharpe, then lexical ID. Greedily
> retain at most three candidates only when every training overlap is strictly
> below 75%; test timing and metrics are evidence only. For multiple blockers,
> retain greatest exact ratio, then earlier training rank, then lexical ID.

**Files:**

- Create: app/flexible_rulebook/metrics.py
- Create: tests/test_flexible_rulebook_metrics.py

**Consumes:** CompletedTrade, EvaluationSplit, RulebookEvaluation.

**Produces:**

~~~python
def partition_metrics(trades: tuple[CompletedTrade, ...]) -> PartitionMetrics: ...
def qualifies(train: PartitionMetrics, test: PartitionMetrics) -> bool: ...
def rank_qualified(evaluations: Sequence[RulebookEvaluation]) -> tuple[RulebookEvaluation, ...]: ...
@dataclass(frozen=True)
class PairwiseTimingEvidence: ...
@dataclass(frozen=True)
class SelectionResult: ...
def select_timing_distinct_top_three(
    ranked: Sequence[RulebookEvaluation], policy: SelectionPolicy,
) -> SelectionResult: ...
def compare_entry_timing(
    left: RulebookEvaluation,
    right: RulebookEvaluation,
    partition: Literal["training", "test"],
) -> PairwiseTimingEvidence: ...
~~~

- [x] **Step 1: Write RED qualification/rank tests.**

~~~python
def test_requires_threshold_in_both_train_and_test():
    self.assertFalse(qualifies(_metrics(n=12, win_rate=65, mean_return_pct=15),
                               _metrics(n=11, win_rate=90, mean_return_pct=30)))

def test_rank_is_training_only_then_lexical_id():
    self.assertEqual([item.rulebook_id for item in rank_qualified(_evaluations())[:2]],
                     ["frb_a", "frb_b"])

def test_training_metrics_choose_the_representative_before_distinctness(): ...
def test_rank_rejects_mixed_ticker_source_split_or_execution_scope(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_metrics -v
~~~

Expected: missing metrics API.

- [x] **Step 3: Implement exact gross metrics.**

Use return > 0 for win; preserve unrounded values; Sharpe null for insufficient
or zero-variance samples. Enforce exactly n>=12, win_rate>=65, and
mean_return_pct>=15 in both partitions. Do not calculate PSR, DSR, or p-value.
Reject NaN/infinite metrics; rank finite Sharpe descending and null Sharpe after
every finite value before lexical ID. Validate one selection scope (ticker,
source fingerprint, split, execution revision) before ranking.
For timing evidence, validate distinct rulebooks with matching ticker, source
fingerprint, split, and execution revision; canonicalize left/right by lexical
rulebook_id before pairing. `left_earlier_count` always refers to lexical-left;
median lead is absolute native-bar distance among non-ties and null when none.
Pair inclusive `[entry_bar_ordinal, exit_bar_ordinal]` intervals by the exact
two-pointer transitions in the design; do not use calendar dates. For training
comparisons, persist `paired_count` and `min(training_n)` and test duplicate via
integer `4 * paired_count >= 3 * min_training_n`, never a rounded float.
`select_timing_distinct_top_three` first ranks all threshold-qualified results,
then greedily selects the first one and later candidates only when each training
overlap ratio is `< Decimal("0.75")`. The selected earlier training-ranked
candidate is representative; test timing/metrics never decide membership. Store
the blocker with greatest integer ratio, then lower training rank, then lexical
ID. It produces a pure immutable selection input/result; storage owns a
campaign-chain SelectionSnapshot, never mutates the evaluation/signal set.

- [x] **Step 4: Add deterministic sensitivity tests.**

~~~python
def test_sensitivity_pairs_each_overlapping_trade_once_and_keeps_unmatched():
    result = compare_entry_timing(_evaluation_a(), _evaluation_b(), "training")
    self.assertEqual((result.left_earlier_count, result.tie_count,
                      result.unmatched_left_count), (1, 1, 1))

def test_sensitivity_rejects_same_rulebook_or_incompatible_source_or_split(): ...
def test_sensitivity_rejects_execution_revision_mismatch(): ...
def test_sensitivity_is_identical_when_inputs_are_reversed(): ...
def test_sensitivity_uses_native_bar_lead_not_calendar_days(): ...
def test_sensitivity_all_ties_has_null_median_lead(): ...
def test_training_and_test_sensitivity_are_separate(): ...
def test_inclusive_endpoint_windows_pair_and_nested_disjoint_windows_are_deterministic(): ...
def test_overlap_integer_boundary_9_of_12_and_10_of_13_are_duplicates(): ...
def test_overlap_integer_boundary_8_of_12_and_9_of_13_are_distinct(): ...
def test_higher_ranked_duplicate_is_skipped_for_next_distinct_candidate(): ...
def test_duplicate_of_any_selected_representative_is_rejected(): ...
def test_test_timing_change_cannot_change_top_three_membership(): ...
def test_test_metric_change_cannot_change_top_three_when_both_remain_eligible(): ...
def test_test_threshold_failure_excludes_before_training_rank(): ...
def test_null_sharpe_ranks_after_finite_sharpe_then_lexical_id(): ...
def test_selection_rejects_mixed_ticker_source_split_or_execution_scope(): ...
def test_fewer_than_three_when_no_third_distinct_candidate_exists(): ...
def test_excluded_duplicate_remains_qualified_and_reusable_with_blocker(): ...
def test_multiple_blockers_choose_ratio_then_rank_then_lexical_deterministically(): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run metrics suite. Record that training timing enforces Top 3 distinctness while
test timing remains evidence only.

### Task 6: Stratified time-bounded discovery and frozen test evaluation

**Files:**

- Create: app/flexible_rulebook/search.py
- Create: tests/test_flexible_rulebook_search.py

**Consumes:** catalog, features, execution, metrics.

**Produces:**

~~~python
@dataclass(frozen=True)
class SearchBudget:
    attempt_count: int
    runtime: RuntimeBudget

@dataclass(frozen=True)
class CandidateSpace:
    candidate_space_hash: str
    candidate_space_algorithm_version: str
    size: int
    def definition_at(self, canonical_index: int) -> RulebookDefinition: ...

@dataclass(frozen=True)
class FrontierAssignment:
    assignment_hash: str
    algorithm_version: str
    frontier_seed: str
    source_ticker: str
    candidate_space_hash: str
    candidate_space_algorithm_version: str
    frontier_size: int
    stratification_revision: str
    strata: tuple[StratumAssignment, ...]
    start_slot: int
    attempt_count: int

def candidate_space(catalog: CatalogRevision) -> CandidateSpace: ...
def assign_frontier(space: CandidateSpace, *, frontier_seed: str,
                    source_ticker: str, start_slot: int,
                    budget: SearchBudget) -> FrontierAssignment: ...
def scheduled_candidates(space: CandidateSpace, assignment: FrontierAssignment) -> Iterator[tuple[int, str, int, RulebookDefinition]]: ...
def discover_and_evaluate(snapshot: HistorySnapshot, features: FeatureResolution,
                          space: CandidateSpace, assignment: FrontierAssignment,
                          *, monotonic: Callable[[], float]) -> DiscoveryResult: ...
~~~

- [x] **Step 1: Write RED deterministic-budget tests.**

~~~python
def test_large_candidate_space_is_lazy_and_same_index_is_stable():
    space = candidate_space(_large_catalog())
    self.assertGreater(space.size, 123_000_000)
    self.assertEqual(space.definition_at(99), space.definition_at(99))

def test_same_seed_ticker_and_window_replay_same_schedule(): ...
def test_different_source_ticker_changes_schedule_but_not_definition_identity(): ...
def test_each_stratum_affine_schedule_is_unique_and_exhaustive_on_small_space(): ...
def test_frozen_round_robin_stratum_quotas_cover_nonempty_structures(): ...
def test_continuation_window_never_repeats_prior_same_ticker_slots(): ...
def test_assignment_rejects_non_coprime_stratum_multiplier_or_wrapping_window(): ...
def test_candidate_space_mapping_version_mismatch_rejects_resume(): ...

def test_candidate_count_exhaustion_uses_next_slot_for_remaining_count():
    result = discover_and_evaluate(_snapshot(), _resolution(), _space(), _assignment(start_slot=2, attempt_count=2), monotonic=_clock())
    self.assertEqual(result.state, "no_qualified_candidate_within_budget")
    self.assertEqual(result.chain_attempted_count, result.next_slot)
    self.assertEqual(result.unsearched_count, result.frontier_size - result.next_slot)

def test_full_error_free_space_exhaustion_has_distinct_truthful_state(): ...
def test_time_budget_exhaustion_is_never_no_qualified_candidate_within_budget(): ...
def test_admission_deadline_starts_no_new_slot_and_keeps_current_slot_uncommitted(): ...
def test_time_counts_source_cache_train_test_selection_and_write(): ...
def test_cache_hit_cannot_change_assignment_quota_or_frozen_test_schedule(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_search -v
~~~

Expected: missing search API.

- [x] **Step 3: Implement canonical stratified search.**

Build/resolve one FeatureResolution before the candidate loop. Keep CandidateSpace
lazy: derive a canonical definition only for its assigned global/stratum slot.
Partition it into deterministic non-empty structural strata by BUY family/count,
gate count, technical-exit configuration, ATR price-exit configuration, and
max-hold bucket. Freeze pre-outcome round-robin quotas and global slot order.
Within every stratum derive `a_i`/`b_i` only from frontier_seed,
candidate-space hash, source ticker, stratum ID, and frontier algorithm version,
with `gcd(a_i, N_i)=1`; never use prices, outcomes, cache state, or test data.
CandidateSpace hash includes mapping revision; assignment includes
stratification revision/quotas/coefficients; resume rejects a mismatch. Use only
hashlib and math.gcd; never allocate a shuffled candidate list.

Run only frozen assignment slots. Before execution, reject only invalid canonical
definitions, exact duplicate predicate configuration, or a provable training
entry-mask upper bound below 12. For a training threshold pass, freeze the ID
and execute untouched test before moving to the next frozen training slot. This
test work cannot change later slots, quotas, seed, candidate count, or rank
criteria. Capture compact outcome/rejection with global/stratum slot/index/
assignment provenance for every committed attempt. Return ranges/next slot,
uncommitted slot, and unsearched count; never materialize unsearched IDs.

Use `time.monotonic()` from the caller's preflight start. Do not admit a new
slot at/after 16,200 seconds. The executor must stop a current slot at bounded
checkpoints before normal terminal time 17,700, omit its ledger outcome, and
return `time_budget_exhausted`; it is resumable at that exact slot. Candidate
count exhaustion has its own truthful state. Emit
`frontier_exhausted_no_qualified_candidate` only after every candidate and every
frozen test has non-error terminal outcomes. Cache performance never changes the
frozen schedule.

- [x] **Step 4: Add source/test isolation tests.**

~~~python
def test_test_rows_cannot_change_schedule_or_frozen_training_candidate_list():
    before = discover_and_evaluate(_snapshot(test_multiplier=1), _resolution(), _space(), _assignment(), monotonic=_clock())
    after = discover_and_evaluate(_snapshot(test_multiplier=99), _resolution(), _space(), _assignment(), monotonic=_clock())
    self.assertEqual(before.assigned_candidate_indices, after.assigned_candidate_indices)
    self.assertEqual(before.frozen_rulebook_ids, after.frozen_rulebook_ids)

def test_assignment_rejects_catalog_size_or_start_slot_mismatch(): ...
def test_rulebook_id_excludes_seed_ticker_slot_and_assignment(): ...
def test_partial_train_return_sharpe_or_test_metrics_cannot_prune_or_reallocate(): ...
def test_continue_finishes_parent_frozen_test_before_new_training_slot(): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run search suite. Record frozen strata/quota values, deadline checkpoint
contract, safe-pruning boundary, and cache-invariant schedule rule.

### Task 7: Schema-1 Flexible artifact store

**Files:**

- Create: app/flexible_rulebook/storage.py
- Create: tests/test_flexible_rulebook_storage.py

**Consumes:** contracts/search result/evaluations.

**Produces:**

~~~python
def write_rulebook_definition(root: Path, definition: RulebookDefinition) -> Path: ...
def write_signal_set(root: Path, evaluation: RulebookEvaluation) -> Path: ...
def append_ledger_chunk(root: Path, campaign_id: str, ticker: str, rows: Sequence[LedgerRow]) -> Path: ...
def write_feature_resolution_receipt(root: Path, campaign_id: str,
                                     ticker: str, receipt: FeatureResolutionReceipt) -> Path: ...
def write_selection_snapshot(root: Path, campaign_id: str, snapshot: SelectionSnapshot) -> Path: ...
def read_signal_set(path: Path) -> dict[str, object]: ...
def resolve_flexible_root() -> Path: ...
~~~

- [x] **Step 1: Write RED schema/path tests.**

~~~python
def test_signal_set_is_hash_addressed_and_self_contained(tmp_path):
    path = write_signal_set(tmp_path, _qualified_evaluation())
    payload = read_signal_set(path)
    self.assertEqual(payload["schema_version"], 1)
    self.assertEqual(payload["artifact_kind"], "flexible_rulebook_signal_set")
    self.assertIn("definition", payload)
    self.assertIn("completed_trades", payload)
    self.assertIn("feature_build_contract", payload)
    self.assertIn("evidence_source_anchor", payload)

def test_resolve_flexible_root_is_absolute_and_independent_of_current_working_directory(): ...
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_storage -v
~~~

Expected: missing storage API.

- [x] **Step 3: Implement Flexible-only atomic storage.**

Copy the proven temporary-file/fsync/replace pattern into Flexible storage
without importing V3 persistence. Validate payload schema before write. Write
definition once per hash; never overwrite a historical signal set. Store alias
inside payload, not canonical path. Persist discovery assignment provenance on
signal sets that originate from discovery, and candidate-space/index/slot/
stratum/assignment/mapping-version fields on every ledger row. Keep an
evaluation/signal set free of mutable Top-3 rank, selected number, or
timing-duplicate blocker. Write instead an immutable campaign-chain
SelectionSnapshot containing its input ledger/evaluation digest, selection scope,
selection/pairing revisions, complete rank order, selected IDs, rejected blocker
relations, integer overlap numerator/denominator, and explicit searched-window
truth: `partial_window`, `complete_assigned_window`, or `frontier_exhausted`.
Only `frontier_exhausted` may claim global CandidateSpace exhaustion. A linked
Continue writes a new snapshot without changing parent signal sets, ledgers, or
snapshots. Persist current-window/runtime/
deadline state, cache diagnostic event, threshold-funnel counts, and
SelectionSnapshot ID plus FeaturePlan/FeatureResolutionReceipt IDs on the
campaign summary. A receipt must be atomic and immutable before a ticker's first
candidate outcome commits; its component digests are compared on frozen resume/
Continue. Cache metadata is diagnostic only
and must not mutate semantic IDs. `storage.py` must explicitly exclude `cache/`
from every rulebook/library/download/signal-set traversal. Reject writes outside
configured root. `resolve_flexible_root()` derives the absolute package-relative
development root, records persistence as unverified, and is the only root source
for page/coordinator/worker/manifest; pass its resolved absolute value to every
subprocess rather than relying on CWD.

- [x] **Step 4: Add crash/rejection tests.**

~~~python
def test_rejected_candidate_writes_compact_ledger_without_trade_payload(tmp_path): ...
def test_invalid_existing_payload_is_not_silently_replaced(tmp_path): ...
def test_ledger_records_remaining_count_without_materialized_ids(tmp_path): ...
def test_discovered_signal_set_retains_assignment_provenance(tmp_path): ...
def test_storage_rejects_mapping_version_mismatch_on_resume(tmp_path): ...
def test_timing_duplicate_is_in_selection_snapshot_but_rulebook_remains_reusable(tmp_path): ...
def test_continue_writes_new_chain_snapshot_without_mutating_parent_signal_set(tmp_path): ...
def test_selection_snapshot_records_pairing_revision_and_integer_ratio(tmp_path): ...
def test_completed_assignment_snapshot_is_not_labeled_global(tmp_path): ...
def test_only_frontier_exhausted_snapshot_can_claim_global_exhaustion(tmp_path): ...
def test_feature_receipt_is_atomic_immutable_and_written_before_first_ledger_slot(tmp_path): ...
def test_resume_receipt_digest_mismatch_fails_without_ledger_or_cursor_advance(tmp_path): ...
def test_cache_directory_is_not_library_or_download_input(tmp_path): ...
def test_time_budget_terminal_records_uncommitted_slot_and_never_claims_no_result(tmp_path): ...
def test_worker_receives_resolved_root_when_started_from_different_cwd(tmp_path): ...
~~~

- [x] **Step 5: Run GREEN and update status.**

Run storage suite. Record storage root and production-mount limitation.

### Task 8: Single-ticker discovery and cross-ticker qualification service

**Files:**

- Create: app/flexible_rulebook/service.py
- Create: tests/test_flexible_rulebook_service.py

**Consumes:** history, catalog, primitive_cache FeatureStore, search, metrics, storage.

**Produces:**

~~~python
def preflight_feature_components(engine, ticker: str,
                                 profiles: Sequence[FeatureProfile],
                                 contracts: Sequence[FeatureBuildContract],
                                 root: Path, now: datetime) -> tuple[FeaturePreflight, ...]: ...
def resolve_frozen_feature_bundle(snapshot: HistorySnapshot,
                                  contract: FeatureBuildContract,
                                  profile: FeatureProfile, root: Path) -> FeatureResolution: ...
def discover_for_ticker(engine, ticker: str, catalog: CatalogRevision,
                        assignment: FrontierAssignment, root: Path,
                        *, cache_choice: Literal["reuse", "rebuild"],
                        monotonic: Callable[[], float]) -> DiscoveryResult: ...
def qualify_rulebook_for_ticker(engine, definition: RulebookDefinition, ticker: str,
                                preflight: FeaturePreflight, root: Path,
                                *, cache_choice: Literal["reuse", "rebuild"]) -> RulebookEvaluation: ...
def reusable_rulebooks(root: Path) -> tuple[RulebookDefinition, ...]: ...
~~~

- [x] **Step 1: Write RED portability tests.**

~~~python
def test_vcb_rejection_does_not_delete_rulebook_before_fpt_qualification(tmp_path):
    definition = _definition()
    _write_definition(tmp_path, definition)
    self.assertEqual(_qualify("VCB", definition, tmp_path).state, "not_qualified")
    self.assertEqual(_qualify("FPT", definition, tmp_path).rulebook_id, rulebook_id(definition))
    self.assertTrue((tmp_path / "rulebooks" / f"{rulebook_id(definition)}.json").exists())
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_service -v
~~~

Expected: missing service API.

- [x] **Step 3: Implement orchestration.**

Load once, build once, discover/qualify, write immutable definition plus
ticker-specific evidence. Explicitly return display_only versus qualified,
source_changed, data_ineligible, no_qualified_candidate_within_budget, and
time_budget_exhausted. New discovery/qualification always fresh-loads source
then offers or resolves compatible PrimitiveComponents; it assembles one
FeatureStore per immutable FeatureBuildContract/profile union. For several
portable definitions, group requested primitives by contract rather than assuming
one current catalog/profile. Persist the FeaturePlan and FeatureResolutionReceipt
before discovery starts a candidate; pass the receipt digest into execution memo
identity and require the identical receipt when a frozen worker resumes or
continues. The worker rechecks the request's preflight
fingerprint and contract immediately before ticker execution; a mismatch returns
source_changed, an unavailable historical contract returns
FEATURE.REVISION_UNAVAILABLE, and neither uses prior cache choice. Discovery consumes a frozen FrontierAssignment; it
never creates, rewrites, or reallocates one. Cross-ticker qualification consumes
portable definitions only and rejects discovery-assignment fields. A frozen
Continue coordinator passes an already verified frozen HistorySnapshot to
`resolve_frozen_feature_bundle`, which reuses/rebuilds only that exact source
without prompting. Campaign code—not this core service—owns parent verification,
cursor advancement, and source_changed status. Never call V3 pipeline/job/status/
position APIs.

- [x] **Step 4: Add V3-isolation test.**

~~~python
def test_service_source_never_imports_v3_pipeline_or_persistence():
    source = inspect.getsource(service)
    self.assertNotIn("backtest_engine.pipeline", source)
    self.assertNotIn("backtest_engine.persistence", source)

def test_vcb_discovery_assignment_never_blocks_fpt_qualification_of_definition(): ...
def test_new_request_component_offer_never_skips_fresh_source_fingerprint(tmp_path): ...
def test_worker_preflight_source_change_rejects_old_cache_choice(tmp_path): ...
def test_verified_frozen_snapshot_rebuilds_expired_cache_without_prompt(tmp_path): ...
def test_resume_after_cache_eviction_requires_the_original_feature_receipt(tmp_path): ...
def test_core_requires_verified_frozen_snapshot_not_campaign_cursor(tmp_path): ...
def test_cache_reuse_and_rebuild_produce_identical_evaluation_payload(tmp_path): ...
def test_two_definitions_with_different_profiles_share_rsi14_but_not_contract(tmp_path): ...
def test_threshold_only_definition_change_reuses_base_components_and_changes_only_masks(tmp_path): ...
def test_single_qualification_requires_declared_component_cache_choice(tmp_path): ...
~~~

- [x] **Step 5: Run core gate and update handoff.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_contracts tests.test_flexible_rulebook_history tests.test_flexible_rulebook_catalog tests.test_flexible_rulebook_features tests.test_flexible_rulebook_primitive_cache tests.test_flexible_rulebook_execution tests.test_flexible_rulebook_metrics tests.test_flexible_rulebook_search tests.test_flexible_rulebook_storage tests.test_flexible_rulebook_service -v
~~~

Expected: all focused core tests pass. Update FOCUS/current-status with core
completion and hand off to dependent campaign/UI plan.

## Core plan self-review

- Coverage: contracts, fresh full-source fingerprints, reusable primitive cache,
  finite catalog, causal array features, exact exit execution, native-bar split,
  thresholds, training-metric representative rank with 75% timing distinctness,
  lazy seeded stratified under-five-hour discovery, portable reuse, and artifact
  integrity map to one task each.
- Deliberate ceiling: no durable multi-ticker worker/campaign or Streamlit page
  exists in this plan; dependent plan adds them rather than reusing V3 runner.
- Placeholder scan: no hidden tuning, V3 coupling, future predicate, eager
  frontier materialization, outcome-adaptive schedule, cache-semantic identity,
  or unbounded search is permitted.
- Verification: do not call core complete until every focused suite in Task 8
  passes and an implementation review records no protected-boundary change.
