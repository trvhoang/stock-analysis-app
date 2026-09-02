# Flexible Rulebook UI Scope Expansion and Progress

## Goal

**Implementation status (2026-08-30): complete and Docker-verified.**

Let an operator expand the active Flexible Rulebook Discover scope from the
UI while preserving the production benchmark gate. One explicit button starts
the benchmark and, only after every requested ticker/seed pair is eligible,
atomically activates a new policy containing the existing scope plus the new
scope. The UI also exposes meaningful progress for Discover, Qualification, and
Current Group BUY Scan.

## Safety invariants

- The existing active policy remains authoritative while an expansion job is
  queued or running.
- Expansion always benchmarks the complete union of current and requested
  tickers and seeds. This gives the new immutable report anchors for the full
  policy scope; no old evidence is copied or edited.
- The fixed attempt cap and one-worker rule come from the active policy. The UI
  cannot tune the cap, worker count, or cold-window count.
- The benchmark must produce 100 complete cold windows for every ticker/seed
  pair, matching source/split identities and the serial deadline. Any failure
  leaves the active pointer unchanged and records a safe terminal reason.
- Operator identity and approval note are required before the button is
  enabled. The submitted request freezes both values into the job evidence.
- Reports, requests, status sidecars, policies, and the active pointer use
  canonical JSON and atomic/immutable writes. A rerun or browser refresh never
  duplicates a job or mutates a completed report.
- Scope expansion is still exploratory research. No order, position, V3, or
  validation workflow is started by the expansion button.

## UI workflow

### Discover: active scope

The existing policy-bound ticker and seed selectors remain unchanged. A new
`Expand Discovery Scope` expander shows:

- Additional tickers: space/comma-separated, normalized uppercase.
- Additional seeds: space/comma-separated, trimmed and deduplicated.
- Operator identity: required non-empty editable text; its one-time default is
  `admin DDMonYY` using the Ho Chi Minh date (for example, `admin 31Aug26`).
- Approval note: required non-empty editable text. Its generated default names
  the normalized additional tickers (for example, `FPT, HPG and REE scope
  expansion for Flexible Rulebook discovery.`). A ticker edit refreshes this
  default only while it is unchanged; operator-written wording is preserved.
  A browser state holding the old blank fields receives the defaults once.
- A read-only union summary and estimated pair/window count.
- The benchmark `as-of` is computed from a fresh common-as-of preflight across
  the complete union and frozen into the request; it is not typed by the user.
  If eligible members have different latest bars, the frozen date is the
  minimum per-ticker latest completed bar—the latest bar available to the
  complete union.
- One disabled/enabled button: `Benchmark and Activate Scope`.

The button is enabled only when an active policy is valid, at least one new
ticker or seed is supplied, all values validate, and both metadata fields are
non-empty. Existing values are merged with additions and sorted deterministically.
Duplicate-only submissions are rejected without starting work.

### Expansion job status

The button creates or reuses one idempotent expansion job. The page shows a
progress bar and status card with:

- job state (`queued`, `running`, `completed`, `failed`, `cancelled`);
- current ticker/seed pair;
- completed pairs / total pairs;
- completed cold windows / required windows for the current pair;
- elapsed time and safe terminal reason;
- automatic three-second sidecar polling while queued/running, plus manual
  `Refresh`; polling stops at every terminal state and exposes no destructive
  controls.

On successful completion the status includes the new policy digest and union
scope. Activation is performed by the job exactly once after report
eligibility validation. A failed or cancelled job never changes the active
policy. The active pointer is re-read on every page render so a stale browser
cannot overwrite a newer policy.

## Durable job boundary

Add a small scope-expansion coordinator and worker boundary beside the existing
campaign runner:

1. The coordinator validates the active policy and creates an immutable request
  containing policy digest, union scope, fixed common-as-of date, fixed cap, one worker, 100 cold
   windows, operator metadata, and request digest.
2. A subprocess runs the existing read-only cap benchmark against a temporary
   report path outside the live evidence root. After each completed pair/window
   it atomically updates a canonical status sidecar.
3. The coordinator validates the final report with the existing cap-report
   parser. It calls the existing activation function with the union scope only
   when the report is eligible and still matches the policy runtime contract.
4. The job sidecar records the report digest, policy digest, terminal state, and
   safe error. Repeated submission of the same request digest returns the
   existing job; a different request cannot reuse it.

Job files live under the configured benchmark directory, never under the live
`Flexible-Rulebook` evidence root. All subprocess input crosses as canonical
JSON; no Python callable is serialized.

## Progress contract

Introduce a narrow callback/event contract with `phase`, `completed`,
`total`, `label`, and optional safe error. Callbacks are optional so existing
library callers and tests remain behavior-compatible.

- **Discover preflight:** `source`, `cache`, `frontier`, and `ready` phases;
  the UI progress reaches 1.0 only after the frozen preflight is stored.
- **Discover campaign:** derive progress from the persisted manifest cursor and
  frozen assignment; never infer progress from elapsed time.
- **Qualification:** report source loading, cache resolution, and each
  ticker/definition evaluation through the callback. The UI renders one bar
  for the active run and preserves terminal item results.
- **Current Group BUY Scan:** report common-as-of, evidence/cache preflight,
  feature resolution, and per-ticker evaluation. The UI renders the same
  phase-aware bar and leaves the result manifest authoritative.
- **Expansion benchmark:** use sidecar values, not in-memory Streamlit state,
  so browser refreshes show the same progress.

Progress is operational telemetry only. It cannot mark a partial run eligible,
qualified, or successful.

## Error handling and recovery

- Invalid scope or missing metadata: inline validation; no job is created.
- Active policy changes before submission: reject and require a fresh render.
- Source, cache, worker, deadline, or report failure: terminal `failed` with a
  safe error code; active policy remains unchanged.
- Process interruption: sidecar becomes `interrupted`; the UI may offer a
  guarded resume only if the frozen request and report state pass the existing
  continuation rules. It must never silently restart from a different scope.
- Activation failure after an eligible report: retain the immutable report and
  terminal failure details; retrying the exact request may activate it, while a
  different request gets a new digest.

## Acceptance criteria

1. One UI button can benchmark and activate an additive ticker/seed scope only
   after required operator fields are filled.
2. Existing scope remains active during all nonterminal states.
3. Every union pair has 100 complete cold windows before activation.
4. A successful job creates a digest-named report/policy and atomically updates
   the active pointer; an unsuccessful job never does.
5. Refreshing the page preserves job identity and progress from sidecars.
6. Discover, Qualification, and Current Group BUY Scan each display phase-aware
   progress without changing their evidence or safety contracts.
7. Tests cover validation, idempotency, scope union, progress events, failure
   paths, pointer preservation, and active-policy replacement.
