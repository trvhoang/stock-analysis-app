# Flexible Rulebook Production Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Docker CLI that records canonical production-scale Flexible Rulebook discovery benchmark evidence without enabling Discover.

**Architecture:** `benchmark.py` owns immutable report contracts, canonical I/O, and derivation of an existing `BenchmarkRecord`. `benchmark_runner.py` owns CLI parsing and real source/worker execution using temporary isolated roots. The existing `ScalePolicy()` remains unchanged and keeps discovery disabled.

**Tech Stack:** Python 3.12, stdlib `argparse`/`subprocess`/`tempfile`, Streamlit project runtime, SQLAlchemy, pandas, NumPy, Docker `stock_app`.

## Global Constraints

- Use the existing Flexible bounded history loader, `catalog_revision_1()`, `feature_profile()`, `DiscoveryService`, runner, and worker boundary; do not reuse V3 execution or artifacts.
- Read real source history at a required fixed `--as-of` date and fingerprint every preflight and worker recheck.
- Cold starts with no component cache, then parent preflight rebuilds the full profile once; the worker must reuse those exact components. Warm pre-populates before timing, fresh-loads again, and may reuse only an identical full cache; warm timing never authorizes a cap.
- At least 100 completed cold full-path samples per configured ticker **and seed** are required before a report is eligible. A training-only candidate is recorded but is not maximal proof.
- Every ticker has one serial 17,700-second benchmark budget. An exhausted ticker records remaining slots as `BENCHMARK.TICKER_BUDGET_EXHAUSTED`; a child process group is terminated at the remaining budget.
- The report writer is atomic and its SHA-256 is verified on every read.
- Temporary benchmark evidence must never be written below `app/Flexible-Rulebook`.
- Keep `ScalePolicy().max_discovery_attempt_count == 0`; no UI or policy enablement in this plan.
- One-slot timing evidence leaves `BenchmarkRecord.measured_discovery_attempt_caps == ()`, which the policy validator rejects for every nonzero discovery cap. A later end-to-end cap-length benchmark/approval remains separate work.
- Do not alter protected SQL, BIGINT scaling, credentials, Docker files, V3, positions, or validation.
- No new dependency, git action, or commit.

---

## File structure

| File | Responsibility |
|---|---|
| `app/flexible_rulebook/benchmark.py` | Typed sample/report contracts, canonical digest, atomic report I/O, eligibility and `BenchmarkRecord` summary. |
| `app/flexible_rulebook/benchmark_runner.py` | CLI, real DB preflight, isolated worker sample execution, telemetry collection, report assembly. |
| `tests/test_flexible_rulebook_benchmark.py` | Pure report, digest, eligibility, and policy-summary tests. |
| `tests/test_flexible_rulebook_benchmark_runner.py` | CLI validation, isolated-root, source stability, warm/cold, and no-production-root tests. |
| `docs/superpowers/specs/2026-08-28-flexible-rulebook-production-benchmark-design.md` | Frozen benchmark contract. |

### Task 1: Benchmark report contract

**Files:**

- Modify: `app/flexible_rulebook/benchmark.py`
- Modify: `tests/test_flexible_rulebook_benchmark.py`

**Consumes:** Existing `BenchmarkRecord`, `ScalePolicy`, canonical JSON conventions.

**Produces:** `BenchmarkSample`, `ProductionBenchmarkReport`,
`write_production_benchmark_report`, `read_production_benchmark_report`, and
`benchmark_record_from_report`.

- [x] **Step 1: Write failing report tests.**

```python
def test_production_report_round_trips_only_when_digest_matches(tmp_path): ...
def test_report_with_one_failed_cold_sample_is_ineligible(): ...
def test_report_requires_one_hundred_completed_cold_samples_per_ticker(): ...
def test_report_summary_uses_worst_ticker_cold_p99(): ...
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark -v`

Expected: import failures for the new report API.

- [x] **Step 3: Implement minimal immutable report contracts and atomic I/O.**

Use canonical JSON, same-directory temporary write, `flush`, `fsync`, and
`os.replace`. Preserve existing `BenchmarkRecord` behavior.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark -v`

Expected: all benchmark contract tests pass.

### Task 2: Read-only sample runner

**Files:**

- Create: `app/flexible_rulebook/benchmark_runner.py`
- Create: `tests/test_flexible_rulebook_benchmark_runner.py`

**Consumes:** Task 1 report API; existing Flexible catalog/profile/history,
feature resolver, campaign runner, `DiscoveryService`, and `worker.py`.

**Produces:** `run_benchmark_sample`, `run_production_benchmark`, and CLI
`main(argv=None)`.

- [x] **Step 1: Write failing runner tests.**

```python
def test_runner_rejects_relative_report_path(): ...
def test_cold_sample_uses_rebuild_and_never_uses_production_root(tmp_path): ...
def test_warm_sample_reloads_source_then_uses_reuse(tmp_path): ...
def test_source_fingerprint_change_marks_sample_incomplete(tmp_path): ...
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark_runner -v`

Expected: module import failure.

- [x] **Step 3: Implement one sample through the production worker path.**

Use the existing full-catalog `feature_profile(catalog_revision_1())`,
`CampaignRequest`, `submit_campaign`, `claim_campaign`,
`start_campaign_worker`, and `watch_campaign_worker`. The worker factory must
re-read only its sample configuration under the isolated root and the source
loader must use `FeatureSnapshot.requested_as_of`.

- [x] **Step 4: Implement cold/warm batch assembly and CLI validation.**

Each sample root is temporary. Record bytes before cleanup. Require absolute
output and reject output inside `resolve_flexible_root()`.

- [x] **Step 5: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark_runner -v`

Expected: runner tests pass without DB writes or production-root artifacts.

### Task 3: Telemetry, error truth, and executable evidence

**Files:**

- Modify: `app/flexible_rulebook/benchmark_runner.py`
- Modify: `tests/test_flexible_rulebook_benchmark_runner.py`
- Modify: `tests/test_flexible_rulebook_benchmark.py`

**Consumes:** Tasks 1–2.

**Produces:** Per-sample timing, source, RSS, pool-checkout, cache-byte,
artifact-byte, terminal-state, and safe-error telemetry.

- [x] **Step 1: Write failing telemetry tests.**

```python
def test_incomplete_worker_state_is_recorded_not_zero_timed(tmp_path): ...
def test_report_records_source_fingerprint_for_every_sample(tmp_path): ...
def test_non_matching_fingerprint_makes_report_ineligible(tmp_path): ...
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark tests.test_flexible_rulebook_benchmark_runner -v`

Expected: telemetry assertion failures.

- [x] **Step 3: Implement measured telemetry and report aggregation.**

Measure preflight before cache resolve and maximal slot around isolated worker
launch/watch. Worker-owned phase observers record actual training/test/
selection/write spans; only outcomes that reached test can be maximal proof.
Capture fresh benchmark-child `resource.getrusage` where available and expose
`None` where unavailable. Capture client-process SQLAlchemy pool checkout count
where available; never claim server-side connection counts.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark tests.test_flexible_rulebook_benchmark_runner -v`

Expected: all contract and runner tests pass.

### Task 4: Docker command, verification, and documentation

**Status (2026-08-28):** host suite, compilation, and CLI help pass. Docker
server `24.0.6` passes the focused 29/29 contract/runner gate, compilation,
and CLI help; see
`docs/superpowers/reports/2026-08-28-flexible-rulebook-production-benchmark-verification.md`.

**Files:**

- Modify: `docs/superpowers/plans/2026-08-25-flexible-rulebook-campaigns-and-current-scan.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-28-flexible-rulebook-production-benchmark-verification.md`

**Consumes:** Tasks 1–3.

**Produces:** A documented target command and truthful implementation status.

- [x] **Step 1: Run focused Docker verification.** Docker server `24.0.6`
  passes 29/29 contract/runner tests.

Run:

```text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark tests.test_flexible_rulebook_benchmark_runner -v
docker exec stock_app python -m compileall -q flexible_rulebook/benchmark.py flexible_rulebook/benchmark_runner.py
```

Expected: all tests and compilation pass.

- [x] **Step 2: Run CLI help.** Docker help displays without opening a DB
  connection or writing output.

Run: `docker exec stock_app python -m flexible_rulebook.benchmark_runner --help`

Expected: usage displays without opening a DB connection or writing output.

- [x] **Step 3: Update durable status.**

State that the benchmark command is ready, but no measured production report
or discovery-cap approval exists until a user runs the command against an
explicit frozen corpus.

## Plan self-review

- Spec coverage: Tasks 1–3 cover canonical report evidence, real source/
  worker execution, cold/warm behavior, telemetry, source stability, and
  ineligible-error truth. Task 4 covers Docker operation and durable status.
- Deliberate scope boundary: policy approval and Discover UI enablement remain
  outside this plan, so a benchmark command cannot accidentally authorize
  discovery.
- Type consistency: Task 1 exports the report objects used by Task 2; Task 2
  produces samples consumed by Task 3; Task 4 runs the exact two test modules.
