# Flexible Rulebook UI Scope Expansion and Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-button, policy-safe UI scope expansion workflow and phase-aware progress bars for every Flexible Rulebook operation.

**Implementation status (2026-08-30): complete.** Tasks 1–6 are checked and
verified by the report linked below; the Docker Flexible gate passes 321 tests.

**Architecture:** A durable scope-expansion job validates the active policy, benchmarks the complete additive union in an isolated subprocess, and atomically activates a new immutable policy only after all pairs pass. Streamlit reads the job sidecar and existing campaign manifests for progress; synchronous qualification/current-scan services receive optional progress callbacks.

**Tech Stack:** Python 3.12, dataclasses, canonical JSON, atomic filesystem writes, existing cap benchmark/activation/campaign services, Streamlit, PostgreSQL read-only history loader, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-30-flexible-rulebook-ui-scope-expansion-progress-design.md`

## Global Constraints

- Existing active policy remains authoritative while expansion is queued/running/failed.
- Expansion benchmarks the complete union of existing and requested tickers/seeds; no old report is edited or copied.
- Fixed cap, one worker, and 100 cold windows per ticker/seed pair are inherited from the active policy and cannot be tuned in UI.
- Operator identity and approval note are required before the expansion button is enabled.
- Reports, requests, status sidecars, policies, and pointers use canonical JSON with immutable/atomic writes.
- Progress is telemetry only and cannot mark a partial run eligible or qualified.
- No changes to `common_queries.py`, BIGINT scaling, credentials, Docker, dependencies, V3, positions, validation, or git state.
- Preserve existing exploratory labels and manual-only behavior.

---

### Task 1: Scope-expansion request and status contracts

**Files:**

- Create: `app/flexible_rulebook/scope_expansion.py`
- Test: `tests/test_flexible_rulebook_scope_expansion.py`

**Interfaces:**

- Produce frozen `ScopeExpansionRequest` with `policy_digest`, fixed
  `benchmark_as_of`, sorted union `tickers`, sorted union `seeds`, fixed `cap_attempts`, `cold_samples=100`,
  `worker_count=1`, `approved_by`, `approval_note`, and deterministic `job_id`.
- Produce frozen `ScopeExpansionStatus` with `state`, `phase`, `completed_pairs`,
  `total_pairs`, `completed_windows`, `required_windows`, current pair, elapsed
  seconds, report digest, policy digest, and safe error fields.
- Produce `parse_scope_values(text, kind)`, `build_scope_expansion_request(...)`,
  `write_scope_request(...)`, `read_scope_request(...)`,
  `write_scope_status(...)`, and `read_scope_status(...)`.

- [x] **Step 1: Write failing tests** for canonical parsing, duplicate removal,
  rejecting empty additions/metadata, rejecting an invalid active policy digest,
  additive union ordering, deterministic job identity, immutable request files,
  and atomic status round-tripping.
- [x] **Step 2: Run the focused contract tests** with
  `docker exec stock_app python -m unittest tests.test_flexible_rulebook_scope_expansion -v`;
  confirm the new interfaces fail before implementation.
- [x] **Step 3: Implement the contracts** using existing ticker/seed validation,
  `canonical_json`, temporary-file plus `os.replace` writes, and no database or
  subprocess work.
- [x] **Step 4: Rerun the focused tests** and confirm all contract cases pass.

### Task 2: Benchmark progress and isolated expansion worker

**Files:**

- Modify: `app/flexible_rulebook/cap_benchmark_runner.py`
- Create: `app/flexible_rulebook/scope_expansion_worker.py`
- Test: `tests/test_flexible_rulebook_cap_benchmark_runner.py`
- Test: `tests/test_flexible_rulebook_scope_expansion.py`

**Interfaces:**

- Extend `run_cap_benchmark(...)` with an optional progress callback receiving
  `ProgressEvent(phase, completed, total, label, safe_error=None)`; default is a
  no-op and report semantics remain unchanged.
- Worker entry point:
  `python -m flexible_rulebook.scope_expansion_worker <request.json>`.
- Worker updates the status sidecar after each ticker/seed pair and each cold
  window, runs the existing cap benchmark in a temporary report location, and
  exits nonzero with a canonical safe error on any ineligible result.

- [x] **Step 1: Add failing tests** for 100-window progress monotonicity,
  pair/window totals, subprocess JSON-only input, worker failure sidecars, and
  unchanged cap-report eligibility.
- [x] **Step 2: Run the focused runner/worker tests** and verify the progress
  assertions fail before implementation.
- [x] **Step 3: Add the progress event callback** at pair/window boundaries;
  keep the existing serial one-worker execution and temporary root isolation.
- [x] **Step 4: Implement the worker entry point** with request validation,
  status transitions (`queued` → `running` → terminal), report digest capture,
  and safe exception mapping. Never update the active policy here.
- [x] **Step 5: Rerun focused tests** and compile `flexible_rulebook`.

### Task 3: Additive atomic activation coordinator

**Files:**

- Modify: `app/flexible_rulebook/activation.py`
- Modify: `app/flexible_rulebook/scope_expansion.py`
- Create: `app/flexible_rulebook/scope_expansion_runner.py`
- Test: `tests/test_flexible_rulebook_activation.py`
- Test: `tests/test_flexible_rulebook_scope_expansion.py`

**Interfaces:**

- `submit_scope_expansion(request, *, benchmark_directory)` validates the active
  policy digest and additive union at submission; the UI freezes the fresh
  full-union common-as-of date into the request, and the coordinator rechecks
  policy authority before activation. It returns
  the idempotent job ID without changing the pointer.
- `run_scope_expansion_job(request_path, *, benchmark_directory, live_root)`
  runs the worker, validates the final report, and calls
  `activate_cap_report(..., allowed_tickers=union, allowed_seeds=union, ...)`
  exactly once on success.

- [x] **Step 1: Write failing tests** proving old policy pointer preservation
  during queued/running/failing jobs, union scope activation on success,
  rejection of a changed active policy, duplicate request reuse, and exact
  operator metadata persistence.
- [x] **Step 2: Run activation tests** and verify the new coordinator behavior
  is absent/failing.
- [x] **Step 3: Implement submission and coordination** with the existing active
  policy loader and immutable cap-report parser. Keep benchmark output outside
  the live Flexible evidence root; retain failed reports and safe reasons.
- [x] **Step 4: Add atomic activation** only after `report.is_eligible` and
  runtime/source/split checks pass. The active pointer must be the sole mutable
  authority and old policies remain readable for existing campaigns.
- [x] **Step 5: Rerun focused tests** and compile the affected modules.

### Task 4: Discover scope-expansion UI

**Files:**

- Modify: `app/pages/flexible_rulebook.py`
- Test: `tests/test_flexible_rulebook_page.py`

**Interfaces:**

- Add injected `scope_policy_loader_fn`, `scope_submit_fn`, `scope_status_fn`,
  `scope_refresh_fn`, and `scope_rerun_fn` dependencies to keep AppTest
  deterministic.
- Render `Expand Discovery Scope` with additional ticker/seed text inputs,
  operator identity, approval note, union summary, and one
  `Benchmark and Activate Scope` button.

- [x] **Step 1: Write failing AppTest cases** for disabled-button validation,
  additive union display, duplicate-only rejection, active-policy preservation,
  status/progress rendering, successful activation digest, and failed-job safe
  message.
- [x] **Step 2: Run the page tests** and confirm they fail before UI wiring.
- [x] **Step 3: Implement the expander and submission path**; do not run work
  synchronously in the Streamlit request. Start/reuse the durable job and rerun
  the page once to show its sidecar status.
- [x] **Step 4: Render the expansion progress card** from sidecar state, with
  current pair, completed/required windows, elapsed time, terminal reason, and
  automatic three-second sidecar refresh while queued/running (manual Refresh
  remains available). Never expose an activation button because the approved
  one-button action performs activation automatically.
- [x] **Step 5: Rerun focused page tests** with both active and missing-policy
  loaders.

### Task 5: Progress bars for Discover, Qualification, and Current Scan

**Files:**

- Modify: `app/pages/flexible_rulebook.py`
- Modify: `app/flexible_rulebook/service.py`
- Modify: `app/flexible_rulebook/current_scan.py`
- Test: `tests/test_flexible_rulebook_page.py`
- Test: `tests/test_flexible_rulebook_service.py`
- Test: `tests/test_flexible_rulebook_current_scan.py`

**Interfaces:**

- Reuse `ProgressEvent` from Task 2 as an optional callback parameter for
  qualification preflight/evaluation and current-scan preflight/evaluation.
- Discover preflight emits `source`, `cache`, `frontier`, `ready`; campaign
  progress derives from persisted `next_slot / assignment.attempt_count`.

- [x] **Step 1: Write failing tests** for monotonic phase events, progress
  reaching 1.0 only on terminal success, no progress-based success on failures,
  and Discover manifest cursor rendering.
- [x] **Step 2: Run focused tests** and confirm missing callbacks/progress bars
  fail.
- [x] **Step 3: Add optional callbacks** around source loading, cache
  resolution, feature resolution, and each ticker/definition evaluation. Keep
  callback failures isolated from evidence generation.
- [x] **Step 4: Render phase-aware `st.progress` bars** with labels in Discover,
  Qualification, and Current Group BUY Scan. Preserve existing result manifests
  and safe error states.
- [x] **Step 5: Rerun focused UI/service/current-scan tests** and compile pages.

### Task 6: Full verification, documentation, and handoff

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/specs/2026-08-30-flexible-rulebook-ui-scope-expansion-progress-design.md`
- Modify: `docs/superpowers/plans/2026-08-30-flexible-rulebook-ui-scope-expansion-progress.md`
- Create: `docs/superpowers/reports/2026-08-30-flexible-rulebook-ui-scope-expansion-progress-verification.md`

- [x] **Step 1: Run the full Flexible Docker gate**:
  `docker exec stock_app python -m unittest discover -s tests -p "test_flexible_rulebook*.py"`.
- [x] **Step 2: Run compilation**:
  `docker exec stock_app python -m compileall -q flexible_rulebook pages`.
- [x] **Step 3: Run non-writing CLI help checks** for the existing cap benchmark,
  activation, and new scope-expansion runner.
- [x] **Step 4: Execute a mocked end-to-end UI job** proving one button creates
  one job, progress is rendered from sidecar state, and successful completion
  activates additive scope while failure preserves the old pointer. Do not run
  a new production benchmark as part of this test.
- [x] **Step 5: Perform implementation self-review** for SQL safety, BIGINT and
  timezone rules, atomic writes, stale-policy handling, progress monotonicity,
  and no V3/positions coupling.
- [x] **Step 6: Update durable status and verification report** with exact test
  counts, changed interfaces, and any remaining operator-only production
  benchmark requirement.

No git staging, commit, reset, checkout, or branch action is part of this plan.
