# Horizon V3 Exploratory Multi-Rulebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline task-by-task execution. Do not delegate, commit, stage, or run Git commands.

**Goal:** Replace fixed schema-3 V3 certification with schema-4 exploratory evaluation of all gate subsets, Top-3 training ranking, and split train/test evidence.

**Architecture:** Keep one fixed RulebookSpec per horizon, but attach a deterministic selected gate subset to each execution. A pure exploratory evaluator splits the completed indicator frame into independent train/test executions and returns paired treatment records. Pipeline persists one schema-4 aggregate document per ticker/horizon; readers consume only its Top 3 preferred treatments.

**Tech Stack:** Python 3.12, pandas, NumPy, Streamlit, unittest, Docker.

**Status:** Complete on 2026-08-22. Verification evidence: `../reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md`. Validate Positions remains blocked pending user direction.

## Global Constraints

- Implement [approved design](../specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md) exactly.
- Swing: volume >= 1.15x, ADX >= 17, training n >= 5.
- Mid-term: RSI upcross 65, volume >= 1.3x, ADX >= 20, training n >= 5.
- Evaluate exactly all 15 non-empty subsets of RSI, joint trend, volume, ADX; run both no-theme and VN-Index AND treatments.
- Full 15 years: 10-year training and 5-year test. Otherwise use chronological 65%/35%. Train/test executions start independently flat; no crossing or incomplete trade survives.
- Candidate membership is no-theme training n >= 5. DSR selects variant only; no DSR threshold. Exact DSR tie and unavailable themed DSR select no-theme.
- Rank using preferred treatment's unrounded training win_rate, then profit_pct, then Sharpe, then lexical rulebook_id; hard-stop at three. Test metrics never rank.
- Moving-block p-value is informational only. At n <= 20, store null p-value with N/A status; never calculate the degenerate bootstrap result.
- All visible labels say Exploratory — gross with in-sample/out-of-sample treatment. Never say profitable, tradable, or statistically certified.
- Schema-4 has one canonical ticker/horizon artifact. Old schema-3 artifacts and job sidecars become filename-only requires_regeneration markers; do not parse or migrate their payloads.
- Audit-ineligible results remain visible but cannot create BUY action.
- Preserve frozen schema-3/legacy positions as history only. New positions use schema version 4.
- Do not change common_queries.py, BIGINT scaling, get_engine_with_retry, credentials, Docker files, database schema, dependencies, research_optimizer, or V2 deletion policy.
- No Git actions, commits, staging, resets, or Git commands.

---

## File map

| File | Responsibility |
|---|---|
| app/backtest_engine/config.py | Fixed horizon inputs and schema-4 request contracts |
| app/backtest_engine/models.py | Gate-subset execution identity and job states |
| app/backtest_engine/signal_combos.py | Deterministic 15 subsets and selected-gate literal entries |
| app/backtest_engine/exploratory.py | Pure split, metrics, DSR preference, p-value status, and Top-3 ranking |
| app/backtest_engine/pipeline.py | Paired data loading, all-candidate evaluation, aggregate terminal output |
| app/backtest_engine/persistence.py | Strict schema-4 aggregate and regeneration-marker JSON |
| app/backtest_engine/regeneration.py | Filename-only schema-3/job-sidecar invalidation |
| app/backtest_engine/worker.py, job_runner.py | Schema-4 request decoding and requires_regeneration terminal jobs |
| app/backtest_engine/early_warning.py | Preferred-rulebook current replay |
| app/backtest_engine/validation_advice.py | Selected-gate monitoring and audit BUY block |
| app/backtest_engine/signal_catalog.py, result_store.py | Schema-4 catalog and saved-option discovery |
| app/backtest_engine/position_identity.py, manual_position_store.py, position_overview.py | Schema-4 frozen positions and labels |
| app/pages/backtest_lab.py | Mandatory paired Collect, Top-3 View/Validate, compliant labels |
| tests/test_backtest_*.py | RED/GREEN coverage for every changed boundary |
| FOCUS.md, ai-context/current-status.md | Ordered task status and stopping point |
| docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md | Final test and fresh-run evidence |

### Task 1: V4 fixed contracts and deterministic gate subsets

**Files:**

- Modify: app/backtest_engine/config.py
- Modify: app/backtest_engine/models.py
- Modify: app/backtest_engine/signal_combos.py
- Modify: tests/test_backtest_contracts.py
- Modify: tests/test_backtest_rulebook_config.py
- Modify: tests/test_backtest_signal_combos.py

**Consumes:** Existing RulebookSpec, RulebookExecution, causal Boolean frame columns.

**Produces:** ENTRY_GATE_NAMES, gate_subsets(), V4 RulebookExecution with selected_gates, and schema-4 request configuration without theme-choice, PSR, DSR-cutoff, or p-value-alpha knobs.

- [x] **Step 1: Write RED contract tests.**

~~~python
def test_v4_rulebooks_lock_updated_thresholds_and_n(self):
    swing, midterm = rulebook_for("swing"), rulebook_for("midterm")
    self.assertEqual((swing.volume_multiplier, swing.adx_minimum, swing.min_n), (1.15, 17, 5))
    self.assertEqual(
        (midterm.rsi_upcross_level, midterm.volume_multiplier, midterm.adx_minimum, midterm.min_n),
        (65, 1.3, 20, 5),
    )

def test_all_nonempty_gate_subsets_are_deterministic(self):
    subsets = gate_subsets()
    self.assertEqual(len(subsets), 15)
    self.assertEqual(subsets[0], ("rulebook_adx_gate",))
    self.assertEqual(subsets[-1], tuple(sorted(ENTRY_GATE_NAMES)))

def test_execution_id_is_horizon_and_lexical_gate_subset(self):
    execution = RulebookExecution(
        rulebook_for("swing"),
        selected_gates=("rulebook_rsi_upcross", "rulebook_adx_gate"),
    )
    self.assertEqual(
        execution.rule_id,
        "swing_rulebook_v4__adx__rsi_upcross",
    )
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_rulebook_config tests.test_backtest_signal_combos -v
~~~

Expected: failures for absent gate-subset API and old threshold/request contracts.

- [x] **Step 3: Implement smallest fixed contract change.**

~~~python
ENTRY_GATE_NAMES = (
    "rulebook_adx_gate",
    "rulebook_joint_trend_pass",
    "rulebook_rsi_upcross",
    "rulebook_volume_gate",
)

def gate_subsets() -> tuple[tuple[str, ...], ...]:
    return tuple(
        subset
        for width in range(1, len(ENTRY_GATE_NAMES) + 1)
        for subset in combinations(ENTRY_GATE_NAMES, width)
    )

@dataclass(frozen=True)
class RulebookExecution:
    rulebook: RulebookSpec
    selected_gates: tuple[str, ...]
    theme_variant: str = "no-background-theme"

    @property
    def rule_id(self) -> str:
        names = "__".join(
            gate.removeprefix("rulebook_").removesuffix("_gate").removesuffix("_pass")
            for gate in self.selected_gates
        )
        return f"{self.horizon}_rulebook_v4__{names}"
~~~

Set the approved values in RulebookSpec instances. Validate non-empty, lexical,
unique selected_gates. Make the request represent a ticker/horizon batch only;
always request both treatments. Remove deflated_sharpe_cutoff,
permutation_alpha, theme_variant, theme_mode, and include_theme from new
configuration serialization. Keep only count, seed, and block-size permutation
controls.

Make rulebook_entry_signal require only execution.selected_gates plus
rulebook_missing_required_input. Generate one no-theme and one AND execution for
each subset; never require an unselected Boolean column.

- [x] **Step 4: Add selected-gate entry tests.**

~~~python
def test_selected_gate_entry_ignores_unselected_false_gate(self):
    frame = _complete_frame()
    frame.loc[frame.index[-1], "rulebook_volume_gate"] = False
    execution = RulebookExecution(
        rulebook_for("swing"),
        selected_gates=("rulebook_joint_trend_pass", "rulebook_rsi_upcross"),
    )
    self.assertTrue(rulebook_entry_signal(frame, execution).iloc[-1])

def test_selected_gate_entry_rejects_selected_false_or_missing_input(self):
    frame = _complete_frame()
    execution = RulebookExecution(
        rulebook_for("swing"), selected_gates=("rulebook_volume_gate",)
    )
    frame.loc[frame.index[-1], "rulebook_volume_gate"] = False
    self.assertFalse(rulebook_entry_signal(frame, execution).iloc[-1])
    frame.loc[frame.index[-1], "rulebook_volume_gate"] = True
    frame.loc[frame.index[-1], "rulebook_missing_required_input"] = True
    self.assertFalse(rulebook_entry_signal(frame, execution).iloc[-1])
~~~

- [x] **Step 5: Run GREEN.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_rulebook_config tests.test_backtest_signal_combos -v
~~~

Expected: every updated contract test passes; no request can select one treatment
or pass statistical cutoffs.

### Task 2: Pure split evaluation, statistics, and ranking

**Files:**

- Create: app/backtest_engine/exploratory.py
- Modify: app/backtest_engine/rolling_window.py
- Modify: app/backtest_engine/validation.py
- Delete: app/backtest_engine/certify.py
- Create: tests/test_backtest_exploratory.py
- Modify: tests/test_backtest_rolling_window.py
- Modify: tests/test_backtest_validation.py
- Delete: tests/test_backtest_certification.py

**Consumes:** V4 RulebookExecution, gate_subsets(), causal native frame, existing
trade executor, calculate_deflated_sharpe(), and moving_block_permutation_test().

**Produces:** EvaluationSplit, PartitionMetrics, TreatmentEvaluation,
ExploratoryCandidate, split_native_frame(), execute_partition(),
evaluate_exploratory_candidates(), and rank_top_candidates().

- [x] **Step 1: Write RED split and ranking tests.**

~~~python
def test_partition_completed_events_drops_trade_crossing_boundary(self):
    split = EvaluationSplit("calendar_10y_5y", date(2011, 1, 3), date(2021, 1, 3), date(2026, 1, 2))
    crossing = _trade_event(
        signal_date=date(2020, 12, 31),
        entry_date=date(2021, 1, 4),
        exit_date=date(2021, 1, 8),
    )
    train = Window(pd.Timestamp(split.train_start), pd.Timestamp(split.test_start) - pd.Timedelta(days=1))
    self.assertEqual(partition_completed_events((crossing,), train), [])

def test_test_execution_can_use_warm_frame_but_no_pretest_entry(self):
    frame = _frame_with_pretest_indicator_values()
    test_events = execute_partition(frame, execution, entries, start=split.test_start)
    self.assertTrue(all(event.signal_date >= split.test_start for event in test_events))

def test_rank_uses_training_preferred_metrics_then_lexical_rulebook_id(self):
    candidates = (_candidate("swing_rulebook_v4__volume", 60, 8, 1.2),
                  _candidate("swing_rulebook_v4__adx", 60, 8, 1.2),
                  _candidate("swing_rulebook_v4__rsi_upcross", 59, 99, 9.0))
    self.assertEqual(
        [item.rule_id for item in rank_top_candidates(candidates)],
        ["swing_rulebook_v4__adx", "swing_rulebook_v4__volume", "swing_rulebook_v4__rsi_upcross"],
    )
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_exploratory tests.test_backtest_rolling_window tests.test_backtest_validation -v
~~~

Expected: import failures for exploratory module and obsolete certification tests.

- [x] **Step 3: Implement split and partition metrics.**

~~~python
@dataclass(frozen=True)
class EvaluationSplit:
    method: Literal["calendar_10y_5y", "chronological_65_35"]
    train_start: date
    test_start: date
    test_end: date

@dataclass(frozen=True)
class PartitionMetrics:
    n: int
    win_rate: float
    profit_pct: float
    sharpe: float | None
    p_value: float | None
    p_value_status: Literal["not_estimated_n_le_block_size", "informational"]

@dataclass(frozen=True)
class TreatmentEvaluation:
    execution: RulebookExecution
    training: PartitionMetrics
    test: PartitionMetrics
    training_dsr: float | None
    dsr_status: Literal["available", "unavailable"]

def split_native_frame(frame, requested_start, requested_end) -> EvaluationSplit:
    # use requested 10y/5y boundary only when effective native history covers it;
    # otherwise choose first native date on/after 65% of effective date duration

def partition_metrics(events, *, permutation_count, permutation_seed, permutation_block_size):
    # preserve unrounded metrics; calculate p only when len(events) > block size
~~~

Add execute_partition(frame, execution, entries, start, end) that passes only
the target native-bar slice to run_rulebook_trade_sequence. The frame was built
on all bars before slicing, so indicators remain causal warm-up while execution
starts flat. Filter event signal, entry, and exit dates against the same
partition before metrics.

Replace ValidatedRulebookTreatment binary success/empty logic with pure
metric helpers. Retain calculate_deflated_sharpe and moving_block_permutation_test
as math functions; remove PSR and validation-as-certification APIs. Delete
certify.py and its tests because V4 has no certified signal set.

- [x] **Step 4: Implement candidate preference and candidate membership.**

~~~python
@dataclass(frozen=True)
class ExploratoryCandidate:
    rule_id: str
    selected_gates: tuple[str, ...]
    no_theme: TreatmentEvaluation
    themed: TreatmentEvaluation
    preferred_variant: str

    @property
    def preferred(self) -> TreatmentEvaluation:
        return self.themed if self.preferred_variant == "background-theme" else self.no_theme

def preferred_variant(no_theme, themed) -> str:
    if no_theme.training_dsr is None or themed.training_dsr is None:
        return "no-background-theme"
    return "background-theme" if themed.training_dsr > no_theme.training_dsr else "no-background-theme"

def rank_top_candidates(candidates):
    ranked = sorted(
        candidates,
        key=lambda item: (
            -item.preferred.training.win_rate,
            -item.preferred.training.profit_pct,
            -item.preferred.training.sharpe,
            item.rule_id,
        ),
    )
    return tuple(ranked[:3])
~~~

Only append a candidate when no-theme training n >= 5. Always retain themed
training/test metrics, even with zero trades. For two finite treatment training
series, calculate both DSR scores from the same two-Sharpe family. Otherwise set
both DSR values null and themed DSR status unavailable; preferred remains
no-theme. Do not round metric values.

- [x] **Step 5: Add RED/GREEN edge tests.**

~~~python
def test_candidate_with_theme_n_one_persists_and_prefers_no_theme(self):
    result = evaluate_exploratory_candidates(_frame(), _confirmation(), _controls())
    candidate = next(item for item in result.candidates if item.rule_id.endswith("__rsi_upcross"))
    self.assertGreaterEqual(candidate.no_theme.training.n, 5)
    self.assertEqual(candidate.themed.training.n, 1)
    self.assertEqual(candidate.preferred_variant, "no-background-theme")
    self.assertEqual(candidate.themed.training.dsr_status, "unavailable")

def test_partition_p_value_is_na_through_block_size(self):
    metrics = partition_metrics(_five_events(), permutation_count=1000, permutation_seed=42, permutation_block_size=20)
    self.assertIsNone(metrics.p_value)
    self.assertEqual(metrics.p_value_status, "not_estimated_n_le_block_size")
~~~

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_exploratory tests.test_backtest_rolling_window tests.test_backtest_validation -v
~~~

Expected: all split, DSR, membership, and ranking tests pass. Confirm no
remaining production import references certify_rulebook_result or
ValidatedRulebookTreatment.

### Task 3: Schema-4 aggregate persistence and paired pipeline

**Files:**

- Modify: app/backtest_engine/persistence.py
- Modify: app/backtest_engine/pipeline.py
- Modify: app/backtest_engine/result_store.py
- Modify: tests/test_backtest_persistence.py
- Modify: tests/test_backtest_pipeline.py
- Modify: tests/test_backtest_result_store.py

**Consumes:** Exploratory candidates, EvaluationSplit, audit metadata, atomic JSON
writer, paired VN-Index confirmation.

**Produces:** schema-4 canonical path, validate_rulebook_document(), one aggregate
document per ticker/horizon, and batch output path per ticker.

- [x] **Step 1: Write RED schema tests.**

~~~python
def test_schema4_success_requires_all_candidates_and_top_ids(self):
    payload = _schema4_success()
    self.assertTrue(validate_rulebook_document(payload))
    payload["top_rulebook_ids"] = ["not-present"]
    with self.assertRaisesRegex(ValueError, "top_rulebook_ids"):
        validate_rulebook_document(payload)

def test_schema4_rejects_rounded_or_certification_fields(self):
    payload = _schema4_success()
    payload["candidates"][0]["treatments"]["no-background-theme"]["training"]["significance_method"] = "dsr"
    with self.assertRaisesRegex(ValueError, "invalid schema"):
        validate_rulebook_document(payload)

def test_current_path_has_no_theme_component(self):
    self.assertEqual(
        signal_artifact_path("VCB", "swing", "/tmp/results").name,
        "VCB_signals_swing.json",
    )
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_result_store -v
~~~

Expected: schema-3 path and per-treatment pipeline assumptions fail.

- [x] **Step 3: Implement strict aggregate serialization.**

~~~python
def signal_artifact_path(ticker: str, horizon: str, output_dir: str) -> Path:
    return Path(output_dir) / ticker / f"{ticker}_signals_{horizon}.json"

def save_rulebook_result(ticker: str, result: Mapping[str, object], output_dir: str) -> str:
    payload = {**result, "schema_version": 4, "ticker": ticker, "evaluated_at": market_now()}
    validate_rulebook_document(payload)
    _write_json_atomically(signal_artifact_path(ticker, payload["horizon"], output_dir), payload)
    return str(target)
~~~

Define exact terminal shapes. Success contains evaluation_label, requested and
effective ranges, split, audit_eligibility, candidates, and top_rulebook_ids.
Require 1-3 IDs, all unique, all present in candidates, and exactly equal to
rank_top_candidates order. Require both treatment objects for every candidate;
allow nullable DSR/Sharpe/p-value only where their status permits. Empty and
failed contain no candidates/top IDs. Requires_regeneration is handled in Task 4.

- [x] **Step 4: Replace pipeline treatment flow.**

~~~python
def _evaluate_ticker(frame, config, confirmation_frame):
    return evaluate_exploratory_candidates(
        frame,
        horizon=config.horizon,
        confirmation_frame=confirmation_frame,
        requested_start=_requested_dates(config)[0],
        requested_end=_requested_dates(config)[1],
        permutation_count=config.permutation_count,
        permutation_seed=config.permutation_seed,
        permutation_block_size=config.permutation_block_size,
    )

def run_backtest_pipeline(config, report_progress, engine):
    frame, audit, raw = _prepare_ticker(config.ticker, config, engine)
    confirmation = _load_confirmation_for_single(config, engine)
    evaluation = _evaluate_ticker(frame, config, confirmation)
    return [save_rulebook_result(config.ticker, _result_document(config, evaluation, raw, audit), config.output_dir)]
~~~

Always load theme confirmation. If it fails, write one schema-4 failed aggregate
document; never persist a no-theme-only result. Change batch code to create one
output per ticker/horizon, retain group assignment behavior, and never use
include_theme branches. Update result_store current-signal discovery to scan the
canonical path and accept only schema-4 success with at least one Top-3 ID.

- [x] **Step 5: Add pipeline behavior tests and run GREEN.**

~~~python
def test_pipeline_always_uses_paired_confirmation_and_writes_one_aggregate(self):
    result = run_backtest_batch_pipeline(BacktestBatchConfig(tickers=("FPT",)), None, engine)
    self.assertEqual(len(result["output_paths"]), 1)
    document = load_rulebook_result(result["output_paths"][0])
    self.assertEqual(document["schema_version"], 4)
    self.assertEqual(set(document["candidates"][0]["treatments"]), {
        "no-background-theme", "background-theme",
    })

def test_confirmation_failure_replaces_canonical_path_with_failed_aggregate(self):
    paths = run_backtest_pipeline(config, None, failing_vnindex_engine)
    document = load_rulebook_result(paths[0])
    self.assertEqual(document["terminal_state"], "failed")
    self.assertIn("VN-Index", document["failure_reason"])
~~~

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_result_store -v
~~~

Expected: strict schema-4 documents only; one aggregate path; no no-theme
fallback after theme-source failure.

### Task 4: Filename-only regeneration and job markers

**Files:**

- Create: app/backtest_engine/regeneration.py
- Modify: app/backtest_engine/models.py
- Modify: app/backtest_engine/job_runner.py
- Modify: app/backtest_engine/worker.py
- Modify: tests/test_backtest_job_runner.py
- Modify: tests/test_backtest_worker.py
- Create: tests/test_backtest_regeneration.py

**Consumes:** Canonical schema-4 persistence writer and job status directory.

**Produces:** invalidate_superseded_outputs(), terminal requires_regeneration
artifact markers, terminal requires_regeneration job markers, and worker refusal.

- [x] **Step 1: Write RED no-parse invalidation tests.**

~~~python
def test_legacy_artifact_filename_is_overwritten_without_reading_invalid_json(self):
    legacy = self.signal_root / "VCB" / "VCB_signals_swing_no-background-theme.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{this is deliberately invalid JSON}", encoding="utf-8")
    report = invalidate_superseded_outputs(self.signal_root, self.status_root)
    marker = json.loads(legacy.read_text(encoding="utf-8"))
    self.assertEqual(marker["terminal_state"], "requires_regeneration")
    self.assertEqual(report.canonical_paths[0].name, "VCB_signals_swing.json")

def test_legacy_request_and_status_are_marked_without_config_decode(self):
    request = self.status_root / "abc.request.json"
    status = self.status_root / "abc.json"
    request.write_text("not json", encoding="utf-8")
    status.write_text("not json", encoding="utf-8")
    invalidate_superseded_outputs(self.signal_root, self.status_root)
    self.assertEqual(read_job_status("abc", self.status_root).state, "requires_regeneration")
    self.assertEqual(run_worker_request(str(request)).state, "requires_regeneration")
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_regeneration tests.test_backtest_job_runner tests.test_backtest_worker -v
~~~

Expected: no invalidation module and JobStatus rejects requires_regeneration.

- [x] **Step 3: Implement marker-only invalidation.**

~~~python
def invalidate_superseded_outputs(signal_dir: str, status_dir: str) -> RegenerationReport:
    # Match exact V3 filename shape only. Never call read_text or json.loads on
    # an artifact/job being superseded.
    for legacy_path, ticker, horizon, variant in legacy_artifact_paths(signal_dir):
        save_regeneration_marker(ticker, horizon, signal_dir)
        write_legacy_artifact_marker(legacy_path, ticker, horizon, variant)
    for job_id, request_path, status_path in legacy_job_sidecars(status_dir):
        write_job_marker(request_path, job_id)
        write_job_marker(status_path, job_id)
~~~

Add requires_regeneration to JobStatus state validation and terminal-status
handling. Marker shape must include schema_version 4, job_id, state,
progress 1.0, output_paths [], and reason. Worker reads only the schema-4 marker
shape and returns the terminal state without calling _config_from_payload.
Normal requests serialize request_type backtest_batch_v4 and schema_version 4.

- [x] **Step 4: Add reader/UI-status tests and run GREEN.**

~~~python
def test_legacy_marker_is_not_catalog_invalid_data(self):
    invalidate_superseded_outputs(self.signal_root, self.status_root)
    rows = list_current_signal_set_rows(str(self.signal_root))
    self.assertEqual(rows["invalid"], [])
    self.assertEqual(rows["terminal"][0]["terminal_state"], "requires_regeneration")
    self.assertIn("Regenerate under amended rulebook", rows["terminal"][0]["reason"])
~~~

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_regeneration tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_persistence -v
~~~

Expected: invalid JSON legacy payloads are overwritten without parsing; no worker
attempts a legacy request; current readers show regeneration state.

### Task 5: Schema-4 catalog, replay, monitoring, positions, and UI

**Files:**

- Modify: app/backtest_engine/signal_catalog.py
- Modify: app/backtest_engine/early_warning.py
- Modify: app/backtest_engine/validation_advice.py
- Modify: app/backtest_engine/position_identity.py
- Modify: app/backtest_engine/manual_position_store.py
- Modify: app/backtest_engine/position_overview.py
- Modify: app/pages/backtest_lab.py
- Modify: tests/test_backtest_signal_catalog.py
- Modify: tests/test_backtest_early_warning.py
- Modify: tests/test_backtest_validation_advice.py
- Modify: tests/test_backtest_position_store.py
- Modify: tests/test_backtest_manual_position_store.py
- Modify: tests/test_backtest_position_overview.py
- Modify: tests/test_backtest_page.py

**Consumes:** Schema-4 aggregate result, Top-3 IDs, selected-gate RulebookExecution,
fresh audit, and position store.

**Produces:** Preferred Top-3 replay, selected-gate monitoring, audit-safe BUY
actions, schema-4 position identity, and compliant Streamlit UI.

- [x] **Step 1: Write RED reader/replay tests.**

~~~python
def test_catalog_lists_only_three_ranked_rulebooks_with_both_treatments(self):
    _write_schema4_success(self.signal_dir, candidate_count=5, top_ids=("rule_a", "rule_b", "rule_c"))
    rows = list_current_signal_set_rows(self.signal_dir)["valid"]
    self.assertEqual([row["Rulebook"] for row in rows], ["rule_a", "rule_b", "rule_c"])
    self.assertTrue(all(row["Evaluation"] == "Exploratory — gross" for row in rows))

def test_validate_replays_preferred_variant_only_and_blocks_audit_ineligible_buy(self):
    replay = _available_replay(preferred_variant="background-theme", audit_eligible=False, literal_entry=True)
    with patch("backtest_engine.validation_advice.check_current_situation", return_value=replay):
        result = validate_saved_signals("VCB", object())
    item = result["results"][0]
    self.assertEqual(item["preferred_variant"], "background-theme")
    self.assertFalse(item["buy_eligible"])
    self.assertEqual(item["buy_block_reason"], "audit_ineligible")
~~~

- [x] **Step 2: Run RED.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_manual_position_store tests.test_backtest_position_overview tests.test_backtest_page -v
~~~

Expected: readers require per-theme schema-3 documents and current BUY ignores
audit status.

- [x] **Step 3: Implement schema-4 catalog and current replay.**

~~~python
def load_current_rulebook_document(ticker: str, horizon: str, output_dir: str) -> dict[str, object] | None:
    path = signal_artifact_path(ticker, horizon, output_dir)
    return None if not path.is_file() else load_rulebook_result(path)

def top_candidate(document, rulebook_id: str) -> Mapping[str, object]:
    if rulebook_id not in document["top_rulebook_ids"]:
        raise ValueError("rulebook is not a Top-3 candidate")
    return next(item for item in document["candidates"] if item["rulebook_id"] == rulebook_id)
~~~

Catalog emits one row per Top-3 candidate with preferred treatment plus nested
both-treatment evidence for detail display. list_saved_signal_options returns
only Top-3 preferred selections. Early warning rebuilds one execution using
candidate selected_gates and preferred_variant; it loads VN-Index only when that
preferred variant is themed.

- [x] **Step 4: Implement selected-gate monitoring and schema-4 positions.**

~~~python
def monitoring_match_level(current, selected_gates, preferred_variant, rulebook):
    factors = {
        "rulebook_rsi_upcross": bool(current["rsi_upcross"]),
        "rulebook_joint_trend_pass": bool(current["joint_trend_pass"]),
        "rulebook_volume_gate": bool(current["volume_gate"]),
        "rulebook_adx_gate": bool(current["adx_gate"]),
    }
    selected = [factors[name] for name in selected_gates]
    if preferred_variant == "background-theme":
        selected.append(bool(current["theme_eligible"]))
    return round(100.0 * sum(selected) / len(selected), 2), classification(...)
~~~

Use selected-gate equal weighting only. Do not score unselected gates; do not
feed monitoring into literal entry, ranking, DSR, or action eligibility.

Replace validate_v3_position_snapshot with validate_v4_position_snapshot. V4
reference required fields are schema_version, ticker, horizon, rulebook_id,
preferred_variant, and exploratory_candidate. Permit existing schema-3 and
legacy validators only for stored history. Adapt manual_position_store
representative lookup so new positions freeze their preferred treatment evidence
without rendering certification wording.

- [x] **Step 5: Update Backtest Lab and UI tests.**

~~~python
def test_collect_has_no_theme_checkbox_and_submits_paired_v4_request(self):
    app.run()
    self.assertNotIn("VN-Index AND treatment", [item.label for item in app.checkbox])
    config = _submitted_config(app)
    self.assertEqual(config.to_dict()["request_type"], "backtest_batch_v4")

def test_ui_never_uses_certification_profitability_or_tradability_copy(self):
    source = inspect.getsource(backtest_lab).lower()
    self.assertIn("exploratory — gross", source)
    self.assertNotIn("certification:", source)
    self.assertNotIn("profitable", source)
    self.assertNotIn("tradable", source)
~~~

Remove Collect and Validate theme checkboxes. Render each Top-3 rulebook with
both treatments and explicit training/test labels. Render requires_regeneration
as Regenerate under amended rulebook. Only preferred Top-3 item can reach BUY
draft; block and explain audit-ineligible literal entries. Update saved position
labels to include horizon, rulebook ID, and preferred treatment.

- [x] **Step 6: Run GREEN.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_manual_position_store tests.test_backtest_position_overview tests.test_backtest_page -v
~~~

Expected: schema-4 only reader path, three or fewer preferred replay entries,
selected-gate monitoring, preserved old position history, and no unsupported
claims in UI.

### Task 6: Integration verification, real invalidation, and ordered handoff

**Files:**

- Modify: FOCUS.md
- Modify: ai-context/current-status.md
- Create: docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md
- Test: all focused Backtest modules changed above

**Consumes:** Completed schema-4 engine, readers, and regeneration operation.

**Produces:** Verified implementation record, current output regeneration state,
and exact parent-plan gate status.

- [x] **Step 1: Run complete focused Docker suite.**

Run:

~~~text
docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_rulebook_config tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_rolling_window tests.test_backtest_trade_execution tests.test_backtest_validation tests.test_backtest_exploratory tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_result_store tests.test_backtest_regeneration tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_signal_catalog tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_manual_position_store tests.test_backtest_position_overview tests.test_backtest_page -v
~~~

Expected: all specified tests pass. Investigate root cause before changing code;
never weaken tests to force pass.

- [x] **Step 2: Run static checks.**

Run:

~~~text
docker exec stock_app python -m compileall backtest_engine pages/backtest_lab.py
docker exec stock_app python -c "from backtest_engine.exploratory import evaluate_exploratory_candidates; from backtest_engine.regeneration import invalidate_superseded_outputs; print('import ok')"
~~~

Expected: compilation succeeds and both new public boundaries import.

- [x] **Step 3: Execute approved filename-only regeneration.**

Run the production-scoped regeneration function once with actual configured
signal and status roots. Record only counts and paths written; do not open old
artifact or sidecar contents. Verify each discovered ticker/horizon has one
canonical schema-4 requires_regeneration artifact and each old visible job status
renders requires_regeneration.

- [x] **Step 4: Run one fresh normal Collect request after regeneration.**

Use the normal schema-4 worker path for one ticker/horizon with a 15-year range.
Record requested/effective range, split boundary, candidate count, Top-3 IDs,
both treatment metrics, p-value status, audit status, and terminal state. Do not
tune gates if it is empty; record the result honestly.

- [x] **Step 5: Perform implementation self-criticism and publish evidence.**

Use ai-skills/skill-implementation-review.md. Check:

- every schema-3 artifact/job path is marker-only and never parsed;
- test partition has no train trade state;
- no rounded values determine rank;
- no test metric reaches preferred selection or Top-3 sort;
- audit blocks every BUY path, including literal current entry;
- current UI/artifact copy has required exploratory gross labels;
- research_optimizer and protected files are unchanged;
- no V2 deletion has occurred.

Write the focused test command/output, static checks, regeneration count, fresh
run summary, self-criticism fixes, and remaining parent gates to the verification
report.

- [x] **Step 6: Update task order truthfully.**

Mark this replacement plan implementation complete only after Steps 1–5 pass.
Update FOCUS and current-status to point to this plan and report. Keep parent
Horizon Task 7 manual schema-4 proof, Task 8 tracker/backfill, and Task 9
separate V2 deletion approval open. State explicitly that Validate Positions
remains blocked.

## Plan self-review

| Spec requirement | Plan task |
|---|---|
| Updated fixed values and 15 gate subsets | Task 1 |
| Split, warm-up, no crossing trades | Task 2 |
| n >= 5 membership, DSR choice, ranking, p-value N/A | Task 2 |
| One schema-4 artifact and mandatory pair | Task 3 |
| Filename-only stale artifact/job replacement | Task 4 |
| Top-3 UI, preferred replay, selected monitoring, audit BUY block, V4 positions | Task 5 |
| Tests, static checks, regeneration, fresh evidence, parent order | Task 6 |

Self-review outcome: no placeholders; all interfaces named before later use; no
Git step; no dependency, protected-boundary, V2-deletion, or optimizer scope
leak.
