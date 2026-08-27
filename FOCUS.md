# FOCUS.md
# Updated: 2026-08-27

## Current Task

**Horizon Rulebook Signal Redesign and Validate Positions Risk — Phase B are
complete (2026-08-25).**

Horizon V3 remains complete through its schema-4 replacement. Validate
Positions Phase B is complete and verified by 68 focused Docker tests plus
container compilation. Evidence:
`docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.

**Active work:** Flexible Rulebook Core Plan. Tasks 3 and 4 implementation is
complete (2026-08-27): catalog-v1, causal FeatureStore/lazy masks, individual
computed-component cache, receipt proof, reference execution, and inert
identity-bound event-plan parity guard exist. Cache accepts only matching
source/contract primitive keys; corrupt, partial, locked, low-space, and write
failures stay uncached without ticker failure. Task 4 fixtures cover next-open,
E+3, technical queue/discard, prior-high trailing, raw-open gaps, deadline
precedence, sparse/dense masks, cancellation, and source/receipt/mask/partition
event-plan rejection. Canonical Docker focused gate passes 73/73 plus
compilation. Tasks 3–4 are verified complete.

**Task 5 contract history (completed 2026-08-26):** its evidence contract is locked:
`RulebookEvaluation` will own typed immutable `training_trades` and
`test_trades` tuples, count-matched to each partition metric and excluded from
`rulebook_id`. Sensitivity reads these tuples only; no aggregate inference or
artifact lookup.

**Task 5 complete (2026-08-26):** metrics now validates a single selection
scope, pairs first inclusive trade-interval overlaps deterministically, records
exact integer overlap evidence, and greedily retains at most three training-time
distinct candidates under the fixed 75% rule. Focused Flexible Docker gate
passes 56/56 with compilation. **Task 6 complete:** catalog-v1 fixes ATR
stop `2.0×`, target `3.0×`, and no trailing. Its first lazy seed-free
CandidateSpace and ticker-seeded affine traversal tests pass in Docker (4/4).
Structural strata and discovery evaluation are complete: seeded stratum order,
continuation-safe affine slots, budget terminal truth, and frozen train/test
typed evidence. Core Docker gate passes 80/80 plus compilation. **Task 7 is
complete:** Flexible-only schema-1 storage writes immutable definitions,
qualified/explicitly-saved evidence, receipt-bound provenance ledgers, verified
Continue selection chains, and excludes `cache/` from signal-set traversal.
Full Flexible Docker gate passes 96/96 and all Flexible modules compile.
Campaign manifests/resume cursors begin only in the dependent Campaigns and
Current Scan plan.

**Active work:** Flexible Campaigns and Current Scan plan, Task 1. Its isolated
campaign contract now freezes semantic request identity, ignores cache/runtime
diagnostics in request hashing, validates discovery-only frontier assignment,
enforces legal campaign and item states, and creates source-verified linked
Continue windows with contiguous cursor accounting. Continue now also requires
an exact, non-empty, freshly verified FeatureResolutionReceipt ID tuple before
it can create a child request. Campaign reconciliation also validates any
claimed immutable SelectionSnapshot schema, ID, and content digest; a missing
claim becomes a safe campaign failure. A terminal committed discovery now
writes its immutable SelectionSnapshot before atomically checkpointing its ID
into the manifest; nonterminal discovery is rejected. Focused Docker evidence
is 23/23 plus compilation. A linked child campaign writes its own immutable
higher-ranked snapshot; a parent checkpoint cannot be replaced. Durable
versioned manifest persistence now atomically
round-trips frozen request identity, validates the campaign ID against that
identity, and reconciles worker-owned item artifacts: verified orphans are
adopted while missing/corrupt claimed artifacts become item failures. Receipt-
bound Resume remains within Task 1. Selection recomputation now accepts typed
evaluation evidence only from the full committed parent chain and applies the
frozen training-only timing-distinct policy. A chain reader accepts only contiguous discovery
parents with preserved frozen semantics, terminal state, and verified immutable
SelectionSnapshots.

**Active work:** Flexible Campaigns Task 2 has begun with durable idempotent
submit/read APIs and legal cancellation state handling. A duplicate frozen
request attaches to its existing queued campaign; queued cancellation is
terminal before a worker claim, while a running campaign becomes cancelling.
The global one-worker lease is atomic, increments the claim epoch, blocks a
different campaign, and permits only the owner to release it. Focused Docker
runner evidence is 6/6; full Flexible evidence is 125/125 plus compilation.
Heartbeat is atomic and timezone-aware; stale recovery verifies the exact
campaign/epoch, marks it interrupted, and releases the worker. Explicit Resume
reuses the persisted request/assignment and obtains a new lease epoch only from
the documented recoverable states. Focused Docker runner evidence is 7/7; full
Flexible evidence is 126/126 plus compilation. The coordinator now accepts an
injected campaign service, persists only an identity/epoch-compatible returned
checkpoint, and releases the lease after terminal work. Focused Docker runner
evidence is 8/8; full Flexible evidence is 127/127 plus compilation. Isolated
subprocess wiring remains. Before any service execution, the runner now
fresh-loads and exactly verifies every frozen source and the active feature-build
contract, passes only those verified sources to the service, and safely blocks
on source change/unavailability or unavailable feature revision without cursor
advance; it then releases the lease. Focused Docker runner evidence is 12/12;
full Flexible evidence is 131/131 plus compilation. Receipt resolution/matching
and real isolated worker execution remain. Runner-level Continue now reads only
the persisted terminal parent, fresh-verifies its frozen source/contract, and
creates the linked queued window through the existing receipt-bound cursor
contract; corrected history creates no child and leaves the parent unchanged.
Focused Docker runner evidence is 14/14; full Flexible evidence is 133/133 plus
compilation.

**Campaign service prerequisite (2026-08-27):** discovery evaluation now accepts
and records a caller-supplied frozen `EvaluationSplit` and `ExecutionContract`,
rather than reconstructing their provenance when a campaign service invokes it.
Focused Docker search evidence is 8/8; full Flexible evidence is 134/134 plus
compilation. Concrete service/artifact checkpointing and isolated worker wiring
remain.

**Campaign receipt checkpoint (2026-08-27):** `ReceiptCheckpointService` now
requires one runner-verified discovery source, resolves only a receipt matching
the frozen source/FeaturePlan/FeatureBuildContract, writes that immutable receipt
before returning its checkpoint, and rejects a different persisted receipt.
Focused Docker runner evidence is 15/15; full Flexible evidence is 135/135 plus
compilation. Frozen-frontier candidate-to-ledger conversion now emits compact
receipt/assignment/stratum/outcome provenance only for committed slots; the full
Flexible Docker gate then passed 136/136 plus compilation. Receipt-bound ledger
chunk persistence is now exposed through the service boundary, and campaign-item
checkpointing writes the immutable worker-owned item artifact before returning
the coordinator's updated manifest checkpoint. Focused campaign evidence is
24/24 plus compilation. The remaining Task 2 work is to compose receipt
resolution, candidate evaluation, ledger and item checkpoints into one concrete
discovery service, then add the isolated subprocess worker/watchdog and fault
classification paths.
Approved design:
`docs/superpowers/specs/2026-08-25-flexible-rulebook-design.md`. Execution
sequence remains `docs/superpowers/plans/2026-08-25-flexible-rulebook-core.md`
then `docs/superpowers/plans/2026-08-25-flexible-rulebook-campaigns-and-current-scan.md`.

**Flexible Rulebook planning amendment (2026-08-26):** approved review repair
now locks a lazy seeded structurally stratified CandidateSpace/FrontierAssignment
search, persisted continuation cursor, portable cross-ticker reuse, native-bar
split boundary, explicit technical/price exit precedence, and 75%-overlap
training timing distinctness for Top 3. It also defines fresh-source-validated
reusable per-primitive indicator components (with request-scoped bundles only),
the <=24-hour Reuse/Recalculate prompt, frozen-source Continue/Resume safety,
append-safe historical evidence anchors, immutable campaign-chain selection
snapshots, a 4h55 per-ticker normal terminal limit with 4h30 candidate admission
stop, benchmark-backed maximal-slot caps, and standalone radio-workspace UI
behavior. The amendment now adds FeaturePlan/FeatureResolutionReceipt digest
proof for cache eviction and continuation, a reference-executor oracle with an
exact-parity-gated event fast path, and an optional exact-prefix append extension
that remains disabled until its benchmark gate passes. Core Tasks 1–7 and
Campaigns Task 1 contract, durable persistence/reconciliation, and receipt-bound
Continue now exist; receipt-bound Resume reconciliation, runner, service,
benchmark, and UI remain
for ordered later tasks.

**Completed UI change:** Collect Signals now has named-Group Edit Group draft
editing: Add/Remove members in a popover and atomically Save, including an
empty Group. Layout is Tickers/Group/Edit Group, then Horizon/Range/Run.
Verification:
`docs/superpowers/reports/2026-08-23-collect-signals-edit-group-verification.md`.

**Completed UI change:** Validate Signals now has the local `Position actions`
dropdown (`ALL` default) ANDed with Monitoring classifications. Its first row
is Tickers plus Ticker group; second row is both filters plus Validate. It
filters the latest cached result without replay. Design:
`docs/superpowers/specs/2026-08-23-validate-signals-position-action-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-validate-signals-position-action-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-23-validate-signals-position-action-filter-verification.md`.

**Completed UI change:** New OPEN Position form now shows an empty SELL date.
Validate Signals shows sequential progress, an action in the top Monitoring
summary (`can BUY`, `expired BUY`, `can SELL`, or `HOLD`), and collapsed JSON
diagnostics. OPEN signal-backed actions use only the current replay and frozen
SL/TP; no action executes a trade. Design:
`docs/superpowers/specs/2026-08-23-current-positions-sell-default-and-validate-actions-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-current-positions-sell-default-and-validate-actions.md`.
Verification:
`docs/superpowers/reports/2026-08-23-current-positions-sell-default-and-validate-actions-verification.md`.

**Completed UI change:** View Signals now filters the existing read-only
schema-4 summary table by optional uppercase partial Ticker and by the
`Both`/`Swing`/`Mid-term` Horizon select box (default `Both`). The filters
intersect and do not mutate artifacts, jobs, catalog data, validation, or
positions. Design:
`docs/superpowers/specs/2026-08-23-view-signals-ticker-horizon-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-view-signals-ticker-horizon-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-23-view-signals-ticker-horizon-filter-verification.md`.

**Completed UI change:** a native shared `View Signals` tab with no View
Signals buttons/popovers, and group-driven batch Validate Signals are
specified in
`docs/superpowers/specs/2026-08-22-backtest-signal-tabs-and-batch-group-validation-design.md`.
Implementation plan:
`docs/superpowers/plans/2026-08-22-backtest-signal-tabs-and-batch-group-validation.md`.
Verification: `docs/superpowers/reports/2026-08-22-backtest-signal-tabs-and-batch-group-validation-verification.md`.
This work does not alter the Phase B risk contract.

**Completed UI change:** View Signals summary columns and terminal-row
suppression are specified in
`docs/superpowers/specs/2026-08-22-view-signals-summary-columns-design.md`.
Implementation plan is
`docs/superpowers/plans/2026-08-22-view-signals-summary-columns.md`.
Verification: `docs/superpowers/reports/2026-08-22-view-signals-summary-columns-verification.md`.

**Completed repair:** New Position now uppercases a committed ticker and
refreshes its saved signal-set choices through isolated current validation;
audit-ineligible or otherwise non-BUY-eligible sets remain manual-only with a
blocking explanation. Verification:
`docs/superpowers/reports/2026-08-22-new-position-saved-set-refresh-verification.md`.

**Completed UI change:** Collect Signals Group defaults to `N/A`, offers
existing groups plus `New group…`, locks Tickers to selected existing-group
members, and preserves existing atomic group creation only on Run Backtest.
Verification:
`docs/superpowers/reports/2026-08-22-collect-signals-group-selector-verification.md`.

**Completed UI change:** Collect Signals run artifacts render in stable output
order, four items per row; item content and downloads are unchanged.
Verification:
`docs/superpowers/reports/2026-08-22-collect-signals-result-grid-verification.md`.

**Completed repair:** Validate Signals Classifications now filter the latest
successful cached validation result without replaying; fresh sessions render no
result list. Verification:
`docs/superpowers/reports/2026-08-22-validate-signals-classification-refresh-verification.md`.

Phase A now provides the fifth non-actionable `Validate Positions` tab,
schema-4 BUY/SELL position groups, and existing position controls. `View
Signals` is the second shared read-only tab.
Verification: 41 focused Docker tests passed; compilation and whitespace checks
passed. The approved Phase B contract is isolated schema-4/no-signal risk
advice: T+3 signal-backed activation, raw-BIGINT scoring, no risk-created SELL
reason, and no legacy evaluation path.

Authoritative design and plan are
`docs/superpowers/specs/2026-08-16-validate-positions-risk-and-trade-rows-design.md`
and `docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`.
Phase B is governed by the approved
`docs/superpowers/specs/2026-08-22-validate-positions-risk-phase-b-design.md`
and executable plan
`docs/superpowers/plans/2026-08-22-validate-positions-risk-phase-b.md`.
Implementation is complete. Focused Docker verification passes 68 tests and
container compilation passes. Risk suggestion text renders each available
horizon on its own line with a one-decimal score. Its saved-set boundary is
current schema-4 V3 artifacts. Completion evidence:
`docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.
Verification is recorded in
`docs/superpowers/reports/2026-08-22-validate-positions-phase-a-verification.md`.

**Predecessor: Horizon Rulebook Signal Redesign — schema-4 exploratory
multi-rulebook replacement: complete and verified.**

Authoritative policy and implementation are
`docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`
and `docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.
Verification is recorded in
`docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md`.
The implementation evaluates all 15 non-empty RSI/joint-trend/volume/ADX
subsets under both treatments, persists no-theme-training `n >= 5` candidates,
selects treatment only by training DSR, ranks Top 3 by training
win-rate/profit/Sharpe/lexical ID, and labels all evidence
`Exploratory — gross`.

V3 marker invalidation is complete: legacy V3 artifacts/job sidecars are now
schema-4 `requires_regeneration` markers. Fresh VCB Swing verification passed
with a clean audit, calendar 10y/5y split, 15 candidates, and Top 3 evidence.
Audit-ineligible rulebooks are display-only and blocked both in the UI and at
the schema-4 signal-backed position boundary.

**Stopping point:** Phase B is complete. Flexible Rulebook Core Plan Task 3's
generic FeatureStore/lazy-mask slice passes its focused gate. Catalog-v1 finite
settings and persistent primitive cache remain blocked. Task 4 needs a
definition-owned ATR primitive/period before it can freeze entry ATR. It must
not enumerate candidates or depend on cache resolution.
The text below is historical context only.

Replace the current three compact strategy IDs with one deterministic,
long-only rulebook per horizon. Swing is daily EMA(5/13), RSI(9) upcross 52,
short causal Alligator, a prior-10-session 1.3× volume gate, ADX(14) >=17,
and an inclusive 22-bar hold. Mid-term is weekly SMA(8/21), RSI(14) upcross
70, standard causal Alligator, a prior-8-week 1.5× volume gate, ADX(14) >=20,
and an inclusive 16-bar hold. Both require the shared MA/Alligator joint trend
predicate: each strict local point must be `Up` (`>=3`); there is no averaged
trend bucket. Swing historical entry uses joint trend plus RSI crossing only;
mid-term historical entry uses joint trend plus volume only. VN-Index AND is an
optional additional entry gate. The other calculated criteria remain
monitoring-only. Rulebook inputs are fresh Backtest-owned functions, never Analyze
helpers; missing/non-finite required input explicitly blocks entry. Mid-term
uses `W-FRI` bars and excludes the final labelled week until its Friday has
passed, including where Friday itself is a market holiday. Saturday and later
include that labelled row; there is no Monday-only block.

Validate's match percentage is a monitoring/near-miss readout only, never an
entry or certification score. It weights capped current-to-saved-rulebook
threshold ratios for RSI, volume, ADX, and (when themed) VN-Index. Trend is
binary: the same joint predicate contributes 100% or 0%, never an averaged
near-miss score. Swing uses 15% per ticker factor plus 40% theme; Mid-term
uses 20% each. No-theme redistributes to 25% per ticker factor with zero theme
share. The four exclusive classifications are: Swing themed `<=50`, `>50–<65`,
`>=65–<90`, `>=90`; Swing no-theme `<=50`, `>50–<65`, `>=65–<80`, `>=80`;
Mid-term themed `<=40`, `>40–<60`, `>=60–<85`, `>=85`; Mid-term no-theme
`<=40`, `>40–<60`, `>=60–<80`, `>=80` (No Match, Weak, Nearly, Closely).

Certification remains per ticker/horizon/theme with `n >=5` for both horizons.
Default no-theme execution runs only no-theme and uses
`min_n` plus deterministic permutation p-value; it has no PSR or DSR. A
VN-Index request runs both treatments and uses their exact two-Sharpe DSR family
for both rows, with Swing `DSR >=0.90` and Mid-term `DSR >=0.85`, then each
row's permutation p-value. A missing themed companion blocks no-theme
certification explicitly and never falls back to permutation-only. V3 audit
eligibility is freshly calculated from the run's raw DB history:
clean needs valid OHLCV, <=1% OHLC mismatch, and no >=15% close discontinuity;
indeterminate/ordering-only-invalid normal results remain available but
audit-ineligible, using the derived envelope only for ordering issues. A range
longer than retained history uses all available history and records its bounds.

V2 artifacts have no current reader, fallback, conversion, warning, or
maintenance path. After V3 tests and a manual nonempty V3 proof, an explicit
bulk backfill inventories legacy filenames only, runs every ticker across both
horizons with theme enabled, and writes no-theme and themed V3 documents.
Every requested treatment writes one terminal `success`, `empty`, or
`failed(reason)` document; a tracker, not a four-file atomicity claim, gates
cleanup. Empty certification records a controlled rejection reason, including
`missing required no-theme DSR companion`; unavailable date ranges use paired
null dates plus a reason. Failures do not retain V2 evidence. Only then may
the user review exact V2 paths and separately approve deletion.
Existing frozen position snapshots remain readable without artifact lookup.
V3-only cutover explicitly removes V2 job requests, root migration, compact
score replay, artifact/catalog readers, and UI/download paths. Existing pre-V3
positions are P&L/manual-management history only, never V3 signal evidence.

Current stopping point: **the approved gate/statistics amendment design and
executable plan are ready; implementation has not started.** It supersedes the
previous V3 gate/PSR policy, so all Task 7 evidence stated below is
pre-amendment history and the manual proof must be rerun after the amendment is
implemented and verified. Task 6 replaced score replay with horizon-isolated V3 rulebook replay,
added V3 saved-set position identity and risk snapshots, retained frozen
pre-V3 positions only for P&L/manual management, and restored those management
controls in Current Positions with k-VND display scaling. The full Docker
Backtest suite passes 132 tests. Task 7 published read-only VCB evidence:
both horizons are clean but remain below their locked `min_n`, without tuning.
The final read-only proof preflight also found every locked-roster no-theme
Swing result empty (`n=5--8`, below 22), so no locked ticker can clear the
manual nonempty-proof gate. The 2026-08-21 user-run Swing Collect job
`ef0412da7a504a76843fe3abb7657b95` for TCB, VCB, REE, FPT, HPG, and MSN
completed without errors and wrote all 12 requested V3 documents, but each is
an `empty` `min_n` result. No-theme completed exits were TCB 2, VCB 8, REE 5,
FPT 5, HPG 6, and MSN 8; themed exits were 2, 5, 5, 4, 5, and 6 respectively.
TCB and VCB were audit-clean; the remaining four are ordering-mismatch
audit-ineligible but remain normal results by design. The required manual
nonempty proof is therefore still unmet and no backfill may begin. Separate
VCB-only read-only signal-optimizer research has an approved design at
`docs/superpowers/specs/2026-08-21-vcb-read-only-signal-optimizer-design.md`
and execution plan at
`docs/superpowers/plans/2026-08-21-vcb-read-only-signal-optimizer.md`.
Its isolated `backtest_engine.research_optimizer` implementation and 15-year
VCB live run are complete. It evaluates all 60 candidates through native V3
frames/execution without V3 persistence or configuration changes; report:
`docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md`.
Swing had 16 DSR and 14 PSR rejections; Mid-term had 25 PSR, four `min_n`,
and one PSR-computation rejection, so no candidate is fully eligible under the
approved search-wide contract. The focused Docker gate passed 39/39. V3 and
Task 7 remain untouched. Diagnostics
now use current pipeline date/theme helpers; immutable Swing/Mid-term
rulebooks own all values; causal Boolean entries execute one flat-to-flat
native trade sequence; and the permanent
read-only frozen-roster audit is at
`docs/superpowers/reports/2026-08-15-v3-price-audit.md`. All eight tickers
meet the independent Swing/Mid-term history floors; only VCB is price-audit
clean. Future V3 research excludes REE, FPT, SSI, VIC, PLX, DHG, and HPG while
normal UI availability remains unchanged. The temporary input—not the
report—is removed only after the whole plan and separately approved V2 cleanup.

Queued only after **every** Horizon Rulebook Signal Redesign task closes:
**Validate Positions Risk and Trade-row Presentation** has an approved
two-phase design. Do not start any Phase A task after V3-only cutover alone:
Tasks 0--9 must finish in order, including Task 7 manual V3 proof, Task 8
backfill/tracker, and Task 9 V2 cleanup after separate explicit deletion
approval. Phase A adds the fourth tab and collapsible BUY/SELL position groups
while retaining existing controls; Phase B was initially blocked pending a separately
approved deterministic risk formula, bands, and result-table contract. It uses
latest completed DB bars only, supports up to five sequential OPEN positions,
and never reads V2 artifacts.
Design: `docs/superpowers/specs/2026-08-16-validate-positions-risk-and-trade-rows-design.md`.
Plan: `docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`.

- [x] Study the existing rule logic and run read-only VCB/frozen-universe
  feasibility spikes.
- [x] Lock two rulebooks, entry gates, min-n values, AND-only theme, PSR/DSR
  trial semantics, fresh V3 audit eligibility, and bulk-backfill-before-delete.
- [x] Write the V3-only artifact cutover design and phased implementation plan.
- [x] Spike all three Backtest tabs and add the V2 job, migration, replay,
  horizon-identity, audit-metadata, and UI cutover gaps to the plan.
- [x] Lock the shared joint-trend gate/zero-strength monitoring behavior,
  treatment-specific match bands, and holiday-short-week `W-FRI` boundary
  fixture (Thursday/Friday exclude; Saturday/Monday include).
- [x] Design queued V3-only Validate Positions and grouped BUY/SELL position
  presentation; defer risk formula and bands to a separate Phase B contract.
- [x] Task 0: repair diagnostics and publish the locked-roster price-audit report.
- [x] Task 1: encode immutable horizon rulebooks.
- [x] Task 2: build causal rulebook inputs and entry gates.
- [x] Task 3: execute one flat-to-flat trade sequence per rulebook.
- [x] Task 4: original PSR/DSR implementation (superseded by the approved amendment).
- [x] Task 5: introduce V3 horizon-qualified terminal artifacts and remove V2 current-artifact support.
- [x] Task 6: V3 replay/UI and horizon-qualified saved-set position boundary.
- [x] Review the V3 gate/statistics amendment design and write its executable amendment plan.
- [x] Implement and verify the approved V3 schema-4 exploratory replacement.
- [x] Task 7: evidence/report complete under the replacement plan.
- [x] Task 8: replacement-plan terminal artifact/job transition complete.
- [x] Task 9: V3 plan closure complete; V2 deletion remains explicitly outside scope and unapproved.

Design:
`docs/superpowers/specs/2026-08-15-horizon-rulebook-signal-redesign-design.md`.

Superseded amendment design:
`docs/superpowers/specs/2026-08-21-horizon-rulebook-v3-gate-statistics-update-design.md`.

Active replacement design:
`docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`.

Active replacement plan:
`docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.

Plan:
`docs/superpowers/plans/2026-08-15-horizon-rulebook-signal-redesign.md`.

## Latest Completed Task

**Collect Group Membership Independent of Backtest Results (2026-08-15).**

Named Collect Groups now atomically add all requested batch tickers before
theme preflight or ticker execution, regardless of empty, failed, or retried
backtest outcomes. Group-store failures abort before work starts. Validate
continues to skip no-signal Group tickers and validates eligible siblings.
Unordered uppercase unique Group JSON tickers are accepted and read in sorted
order; duplicate/non-uppercase values remain invalid. Docker focused Backtest
tests passed 108/108, compilation and Streamlit health `200` passed. No
artifact, position, replay, SQL, BIGINT-price, dependency, Docker, credential,
runtime-data, or commit change.

Verification:
`docs/superpowers/reports/2026-08-15-collect-group-membership-independent-of-results-verification.md`.

## Task

**Backtest Multi-Metric Certified Candidates and Sequential Batch (2026-08-14).**

- Persist one schema-v2 candidate for every metric group won by the exact same
  indicator combination; no V1 artifact read, conversion, or fallback remains.
- Collect Signals accepts one to five ordered unique tickers and submits one
  auto-polled sequential job. Theme runs one shared VN-Index preflight then
  writes each ticker's no-theme and VN-Index AND outputs in order; ticker
  failures retry once after first pass and remain recorded when terminal.
- Saved-set replay, catalog, validation, and position references preserve the
  full grouped metric list. Existing frozen legacy position snapshots remain
  readable only in position history.
- The final focused Docker gate passes 127/127. The six verified V1 FPT/TCB/VCB
  artifact files were deleted; no V2 artifact remains and signals will be
  regenerated later. No Backtest, database, position, job-status, dependency,
  Docker, credential, or commit change was made.

Design:
`docs/superpowers/specs/2026-08-14-backtest-v2-multi-metric-batch-design.md`.
Plan:
`docs/superpowers/plans/2026-08-14-backtest-v2-multi-metric-batch.md`.
Verification:
`docs/superpowers/reports/2026-08-14-backtest-v2-multi-metric-batch-verification.md`.

## Earlier Completed Task

## Task

**View Signals Current-Tab Ticker Filter.**

- Add one label-hidden filter at the top of View Signals with placeholder
  `ticker name`.
- Filter uses partial ticker matching and auto-capitalizes input; it affects
  the displayed All, Valid, or Invalid rows while leaving warnings and tab
  availability intact.
- The implementation is read-only: no artifact, position, job, replay, SQL,
  BIGINT-price, dependency, Docker, credential, or commit change.

Design:
`docs/superpowers/specs/2026-08-13-view-signals-ticker-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-13-view-signals-current-tab-ticker-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-13-view-signals-current-tab-ticker-filter-verification.md`.

## Earlier Completed Task

## Task

**View Current Signal Sets Popover.**

- Add native `View Signals` beside Collect Signals `Run backtest`; it scans
  every current ticker/theme JSON artifact read-only and has no action control.
- Show the approved nine fields. Invalid artifacts keep the same schema, use a
  red row, and show a separate warning; tabs are All/Valid/Invalid only when
  invalid data exists, otherwise All only.
- Preserve job submission, replay, persistence, SQL, BIGINT pricing,
  dependencies, Docker, credentials, and commit history.

Plan: `docs/superpowers/plans/2026-08-13-view-current-signal-sets.md`.
Verification:
`docs/superpowers/reports/2026-08-13-view-current-signal-sets-verification.md`.

## Earlier Completed Task

## Task

**Action Labels for Collect Signals and Data Page.**

- Add `Action` above Collect Signals `VN-Index theme` and Data Page `Get data`
  so each aligns with the input and dropdown boxes.
- Preserve checkbox label/default/disabled state, ingestion callback behavior,
  configuration variants, SQL, BIGINT pricing, dependencies, Docker, and
  commit history.

Verification:
`docs/superpowers/reports/2026-08-13-collect-signals-theme-alignment-verification.md`.

## Earlier Completed Task

## Task

**Data Page Phase-Progress UI.**

- Put `Up-to date`, `Year gaps`, and `Get data` on one first row; Year gaps
  defaults to `15`, with an `Action` label above the button for input-box
  alignment.
- Replace the spinner with truthful completed-phase progress: reset, schema,
  stock, VN-Index, and completion, from 0 to 100%.
- Keep existing detailed ingestion messages in an initially-expanded
  `Progress details` section.
- Preserve the existing synchronous ingestion path, API/background behavior,
  reset semantics, URLs, SQL, BIGINT `* 1000` price scaling, dependencies,
  Docker, and commit history.

Plan: `docs/superpowers/plans/2026-08-13-data-page-phase-progress.md`.
Verification:
`docs/superpowers/reports/2026-08-13-data-page-phase-progress-verification.md`.

## Earlier Completed Task

## Task

**Collect Signals Control-Row Layout.**

- Put Ticker, Time range, Horizon, and `VN-Index theme` on line 1.
- Default Time range to `15y`; use Horizon dropdown default `-` and preserve
  existing required-horizon validation.
- Keep Custom Start/End dates and Run backtest below; leave Validate Signals
  and Current Positions unchanged.

Plan: `docs/superpowers/plans/2026-08-13-collect-signals-control-row.md`.
Verification:
`docs/superpowers/reports/2026-08-13-collect-signals-control-row-verification.md`.

## Earlier Completed Task

## Task

**Current Positions Native New Position Popover Restoration.**

- Restore `st.popover("New position")` and remove panel-only session state,
  placeholder, and Close button.
- Preserve ticker capitalization, saved-signal lookup, OPEN/CLOSED validation,
  raw-price conversion, frozen risk snapshot, and persistence calls.
- Retain native click-outside/Escape dismissal; Streamlit 1.32 has no supported
  API for an internal Close control.
- Add `TODO(streamlit-upgrade)` beside the popover for future reevaluation.

Plan:
`docs/superpowers/plans/2026-08-13-current-positions-native-popover-restoration.md`.
Verification:
`docs/superpowers/reports/2026-08-13-current-positions-native-popover-restoration-verification.md`.

## Earlier Completed Task

## Task

**Current Positions UI Regression Fix — select-all and New Position Close.**

- Fix the stale state overwrite that prevented Select all visible from checking
  or unchecking the current filtered rows.
- Replace the Streamlit 1.32 popover (which lacks a programmatic close API)
  with a state-controlled New position panel and a Close button that writes no
  position data.
- Add RED/GREEN AppTest regression coverage for both paths.
- Leave SQL, schema, BIGINT price scaling, dependencies, Docker, credentials,
  and commit history unchanged.

Verification:
`docs/superpowers/reports/2026-08-12-current-positions-ui-regression-fix-verification.md`.

## Earlier Completed Task

## Task

**Validate Signals UI Revamp — Scope Definition.**

Improve the saved-signal validation flow without changing replay, signal
artifacts, or long-only execution rules. Extend position persistence only for
the approved optional quantity and editable actual BUY/SELL values.

Approved design:
`docs/superpowers/specs/2026-08-11-validate-signals-ui-revamp-design.md`.

Execution plan:
`docs/superpowers/plans/2026-08-11-validate-signals-ui-revamp.md`.

- show progress only while `Validate saved signals` is running; hide it after
  success or failure;
- show no-theme result first, then VN-Index AND result; each title owns its
  corresponding signal sets;
- place an expandable signal-set summary below those results. Show Identity
  (ticker and selected metric), Strategy (indicators and BUY threshold),
  Backtest performance, Current match, Current trade signal, and
  Existing-position state by default;
- show Backtest performance fields: `n`, win rate %, profit %, Sharpe,
  deflated Sharpe, p-value, and date range;
- show Current match fields: match %, classification, advice, and theme
  eligibility;
- show Current trade signal fields: signal date, entry, SL, TP, and projected
  exit;
- show Existing-position state fields: status, holding/suggested holding,
  SELL allowed/reasons, and pinned SL/TP;
- provide a column-visibility filter; all other available fields are hidden by
  default; visibility resets each browser session;
- reveal selected signal sets in expandable detail views; users may expand
  several detail panels at once; summary and detail panels start collapsed;
- support explicit, individual BUY/SELL decision recording for each eligible
  signal set or open position.
- keep BUY and SELL recording in `Validate Signals`: show BUY or `Close
  position` beside each applicable suggestion. `Current Positions` is the
  saved-position list, filter, and saved price/quantity edit view.
- add `Current Positions` as a third top-level Backtest Lab tab beside
  `Collect Signals` and `Validate Signals`.
- render all OPEN positions immediately; filter by ticker and state, with
  `OPEN` selected and `CLOSED` hidden by default.
- use an explicit `Refresh` button for Current Positions.
- treat themed and no-theme positions equally; order the combined list by
  position open time, oldest first.
- show ticker, actual BUY price, actual SELL price or `-`, percentage profit,
  profit, open time, closed time, and associated signal set for every position.
- for OPEN positions, show latest trading-day close as current price and use it
  to calculate unrealized profit and percentage profit; show SELL price and
  closed time as `-`.
- calculate displayed P&L without fees or taxes.
- display absolute P&L as per-share VND price difference. Manual BUY/SELL
  recording forms keep user-editable actual price fields. Saved quantity and
  BUY/SELL prices remain editable after recording.
- add optional position quantity. When present, absolute P&L equals price
  difference times quantity; when absent, show simple per-share price
  difference. Percentage P&L remains price-based. Quantity is user-entered
  optionally at any time; it is not fixed at BUY and remains editable after
  recording. Quantity/price edits overwrite their current values only and
  never change open or closed time.

## Current Phase — Complete

- [x] Confirm result ordering: No theme first, then VN-Index AND.
- [x] Confirm collapsible signal-set selection: several detail panels may be
  expanded simultaneously.
- [x] Confirm current-position tab placement: third top-level Backtest Lab tab.
- [x] Confirm current-position list/filter contract: render all OPEN positions;
  ticker and OPEN/CLOSED filters; CLOSED hidden by default.
- [x] Confirm position ordering principle: one theme-neutral combined list,
  ordered oldest first by open time.
- [x] Confirm current-position fields: ticker, BUY/SELL prices, percentage and
  absolute profit, open/closed times, and signal set.
- [x] Confirm OPEN placeholders: SELL price and closed time are `-`.
- [x] Confirm OPEN profit semantics: latest trading-day close is current price
  and drives unrealized profit/%.
- [x] Confirm P&L cost treatment: no fees or taxes.
- [x] Confirm manual-decision placement: BUY/Close position beside applicable
  Validate Signals advice; Current Positions is a list/filter/edit view.
- [x] Confirm decision interaction: individual action/form per eligible item;
  no batch selection or shared BUY/SELL form.
- [x] Confirm absolute-profit unit: per-share VND price difference; manual
  decision forms accept user-entered actual prices.
- [x] Confirm optional quantity/P&L contract: quantity multiplies absolute P&L;
  no quantity preserves simple per-share price difference.
- [x] Confirm quantity interaction: optional user entry at any time, not fixed
  at BUY, and editable after recording.
- [x] Confirm edit temporal rule: quantity/price edits never change open or
  closed time.
- [x] Confirm edit persistence: overwrite current quantity/price only; no
  correction history.
- [x] Confirm current-position refresh trigger: explicit Refresh button.
- [x] Confirm Current Positions Refresh scope: saved position records plus
  latest prices and recalculated P&L.
- [x] Confirm default signal-summary groups and fields: Identity/Strategy plus
  specified Backtest performance, Current match, Current trade signal, and
  Existing-position state fields.
- [x] Confirm column visibility: non-default fields start hidden and users can
  control their visibility.
- [x] Confirm column visibility lifetime: reset each browser session.
- [x] Retain current per-set detail content in this structural UI revamp.
- [x] Confirm saved price/quantity edit entry point: Current Positions.
- [x] Confirm default collapse state: signal-set summary and all detail panels
  start collapsed.
- [x] Write consolidated design and test-first implementation plan.
- [x] Task 1: position quantity and atomic manual edits. Host RED proved the
  missing interface; host GREEN passes 7/7 position-store tests.
- [x] Task 2: batched current-position overview. Host RED proved the missing
  module; host GREEN passes 12/12 store/overview tests.
- [x] Task 3: Validate Signals progress, hierarchy, and individual decisions.
  Docker RED exposed missing third tab; green AppTests prove progress cleanup,
  no-theme-first hierarchy, collapsed summaries/details, and individual manual
  actions.
- [x] Task 4: Current Positions tab/filter/edit flow. Docker AppTests prove
  OPEN default/filtering, per-record BUY/SELL edits, optional quantity removal,
  and recalculated frozen-ATR SL/TP after a BUY-price edit.
- [x] Task 5: verification, review, and documentation. See
  `docs/superpowers/reports/2026-08-11-validate-signals-ui-revamp-verification.md`.

Current stopping point: **Validate Signals UI Revamp complete. No commit made.**

## Prior Phase — Backtest Compact Strategy Revamp (complete)

Review the VCB zero-certification behavior without tuning to VCB. The approved
design replaces the generated indicator grid with three compact strategies,
adds causal Williams Alligator, removes rolling-window duplicate trade events,
and decouples statistical gate semantics after a database-only price audit.

Approved design:
`docs/superpowers/specs/2026-08-10-backtest-compact-strategy-revamp-design.md`.

Execution plan:
`docs/superpowers/plans/2026-08-10-backtest-compact-strategy-revamp.md`.

## Completion Evidence

- [x] Freeze no-forced-signal, per-ticker `n >= 30`, database-only audit,
  compact strategy, causal Alligator, and hard-ADX decisions.
- [x] Write and self-review the design specification.
- [x] User reviews and approves the specification.
- [x] Write and self-review the detailed implementation plan.
- [x] Task 0: record RED contract baseline; old 270/810 generated grid lacks
  compact `strategy_id` and fixed-rulebook behavior as expected.
- [x] Task 1: 14/14 Docker audit/universe tests pass. One bound raw-connection
  query loads candidates; exact 15% moves are indeterminate, material OHLC
  mismatches and coverage exclude candidates, and ticker-symbol ties are
  deterministic.
- [x] Task 2: 11/11 Docker indicator tests pass. Backtest-only Alligator uses
  causal 13/8/5 SMMA values with 8/5/3 lags; no live Technical behavior changed.
- [x] Task 3: 43/43 Docker compatibility gate passes. Generator emits only
  three strategy IDs per no-theme/AND variant at score 60 with hard `ADX >=20`.
  Old no-ID artifact replay remains supported.
- [x] Task 4: 28/28 Docker native-clock tests pass. One chronological sequence
  executes each signal once; partitions exclude boundary-crossing exits.
- [x] Task 5: 8/8 Docker validation/certification tests pass. Permutation alpha
  is explicit and independent from the DSR cutoff.
- [x] Task 6: 5/5 Docker pipeline/diagnostic tests pass (one expected unmounted
  CLI skip). Pipeline certifies sequence events, not rolling duplicates.
- [x] Task 7 deterministic gate: 60/60 Docker tests pass, one expected CLI skip;
  Backtest package compiles and whitespace check passes.
- [x] Refine the audit using current DB evidence: use the shared available
  history bounds, warn for `<=1%` OHLC mismatch, reject `>1%`, and create only
  a derived Backtest OHLC envelope. Raw DB values remain unchanged.
- [x] Task 7 live audit: 21 clean, 6 indeterminate, and 1,837 invalid
  candidates. VCB is clean (0.95% minor mismatch, no `>=15%` close move), and
  the deterministic frozen universe is `VCB, DHC, HJS, ELC, VPL, C47, HAP,
  CSM`.
- [x] Task 7: `collect_compact_strategy_diagnostics()` evaluates eight frozen
  tickers across Swing/Mid-term and no-theme/VN-Index AND variants (96 compact
  strategy results). It loads candidates once, loads VN-Index once, reuses raw
  frames, reports full-history certification plus reporting-only calibration
  and holdout metrics, preserves VCB trade traces, and declares no writes.
- [x] Final gate: Docker focused Backtest suite passes 66/66 with one expected
  unmounted CLI skip; `compileall backtest_engine pages/backtest_lab.py`,
  `git diff --check`, and changed-file whitespace checks pass.
- [x] Follow-up replay repair: persisted JSON sorts compact indicator dimensions
  alphabetically, while compact strategy identity requires rulebook order. The
  shared `IndicatorCombo` contract now validates indicator content independent
  of JSON key order, canonicalizes the approved order, and still rejects
  duplicate, missing, extra, or incorrect dimensions. RED/GREEN regression
  coverage passes; live VCB no-theme and VN-Index AND replay are both available.

Current outcome: **live read-only diagnostic used current DB history from
2011-08-10 through 2026-08-10; selected `VCB, DHC, HJS, ELC, VPL, C47, HAP,
CSM`; returned 27 qualified compact combinations. VCB Swing has five qualified
sets; VCB Mid-term has none because no-theme variants fail DSR and themed
variants fail `n >= 30`. This is a truthful certification outcome, not an OHLC
failure and not a reason to tune frozen gates. Runtime was 204.64 seconds. No
database data, job, current signal artifact, or commit changed. Evidence:
`docs/superpowers/reports/2026-08-10-backtest-compact-strategy-evidence.md`.**

## Prior Phase — Validate Signals Verification and Documentation (complete)

- [x] Inspect signal artifacts, replay context, price conversion, and position
  persistence boundaries without writing an artifact or database record.
- [x] Prove daily/weekly buy-date and as-of handling with a deterministic
  Mid-term mid-week fixture; no future source bar may be counted.
- [x] Record the selected native-bar contract before source code changes.

Phase 0 gate: PASS — see
`docs/superpowers/reports/2026-08-07-validate-signals-spike.md`.

Task 1 checklist:

- [x] Add and run RED coverage for raw replay context, artifact horizon
  consistency, one-frame-per-horizon replay, and matching boundaries.
- [x] Make the smallest replay and matching implementation that turns that
  coverage GREEN.
- [x] Verify the read-only boundary and compile the engine package.

Task 1 gate: PASS — the expected RED failures were recorded; the focused
Docker gate passes 18/18 and `backtest_engine` compiles in the container.

Task 2 checklist:

- [x] Add and run RED coverage for `k VND` input conversion and atomic
  per-tuple position histories.
- [x] Implement validated raw-price conversion and freeze caller-supplied
  signal, entry, and risk snapshots without deriving new trading values.
- [x] Verify focused Docker tests, snapshot immutability, whitespace, and
  protected-boundary scope.

Task 2 gate: PASS — expected missing-interface RED was recorded; the focused
Docker gate passes 9/9 and `backtest_engine` compiles in the container. The
store uses raw integers only, deep-copies validated snapshots, and atomically
replaces its per-tuple JSON file. The protected-path inspection showed a
pre-existing unrelated `app/main.py` diff; Task 2 did not modify it.

Task 3 checklist:

- [x] Add and run RED lifecycle coverage for native holding periods, SL/TP
  proximity, timeout, and no-look-ahead handling.
- [x] Implement the read-only daily/weekly monitor without an exit path.
- [x] Verify monitor and existing Swing/Mid-term lifecycle tests.

Task 3 gate: PASS — the focused native-monitor and existing Swing/Mid-term
lifecycle Docker gate passes 17/17. The monitor slices raw history at as-of
before calculation, counts daily/weekly native periods only, and never writes
or closes a position.

Task 4 checklist:

- [x] Add and run composition coverage for Observe, BUY eligibility, theme
  ineligibility, independent variants, and pinned open-position monitoring.
- [x] Isolate malformed position history to its own theme variant, retaining
  advice from the other variant.
- [x] Verify no persistence calls during validation and rerun replay coverage.

Task 4 gate: PASS — Docker validation-advice, position-store,
position-monitor, and early-warning gate passes 30/30. Validation remains
read-only; a corrupt themed position file now reports only that themed result
as unavailable and does not hide no-theme advice.

Task 5 checklist:

- [x] Add and run RED AppTests for explicit validation, independent theme
  rendering, unavailable artifacts, manual BUY, manual SELL, and no job
  submission.
- [x] Implement injected validation/store callbacks, selection identity
  protection, raw/UI price conversion, and manual forms only.
- [x] Lock each BUY date to its validation as-of date and calculate/freeze its
  raw ATR risk snapshot from that same context.
- [x] Verify page, job, replay, and advice regressions; prove stale selection
  guard fails when removed and passes when restored.

Task 5 gate: PASS — Docker page, job-runner, replay, and validation-advice
gate passes 47/47. The Validate tab has no job submission, refresh, auto-buy,
or auto-close path. Streamlit dependency `SyntaxWarning` output is external;
the test suite has no test failures or page exceptions.

Task 6 checklist:

- [x] Run explicit Backtest module gate: 105 passed; one expected Docker
  diagnostics skip for unmounted top-level `scripts`.
- [x] Compile `backtest_engine` and `pages`; inspect whitespace and protected
  boundaries without commits.
- [x] Replay real FPT history using temporary artifacts/positions; verify
  no-theme/themed reads, multi-BUY raw/UI conversion, manual SELL, retained
  history, and cleanup.
- [x] Complete implementation review, fix Ho Chi Minh SELL date default and
  multi-selection preflight, then rerun all verification.

Task 6 gate: PASS — full evidence in
`docs/superpowers/reports/2026-08-07-validate-signals-verification.md`.

## Active Locked Decisions

- Validation reads existing current signal files only. It never submits a job,
  re-certifies, or overwrites `ticker-signals`.
- Theme checkbox behavior mirrors Collect Signals: unchecked validates
  no-theme; checked shows no-theme and VN-Index AND separately.
- `match = min(100, current_score / threshold_score_buy * 100)`; a failed
  required theme makes the themed set ineligible. `<70` Observe, `70–<85`
  Nearly match, `>=85` Closely match.
- Eligible sets without an open position advise BUY. Users may select one or
  more, saved separately by ticker/theme/metric. BUY and SELL need explicit
  confirmation and never trade or auto-close.
- A manual BUY date is locked to its selected validation as-of date; this
  freezes that as-of raw ATR and engine-standard 1.5x/2.5x raw exit levels
  with the user's actual raw BUY price. Mixed-as-of selections must be saved
  separately.
- UI price is `k VND`; persistence is raw integer price. No SQL scaling,
  database BIGINT, export, dependency, Docker, or protected-boundary change.
- Each position pins its certified signal/risk snapshot. SELL is allowed only
  after `>60%` of pinned max-hold or within/beyond 5% of pinned SL/TP. Swing
  stays daily; Mid-term stays weekly.
- No commits. `IMPLEMENTED.md` remains excluded.
- Current Docker configuration supplied real FPT history to live-safe temporary
  validation. Existing signal artifacts and position histories were untouched.

## Active Phase Plan

1. Spike/freeze actual temporal contract.
2. Expose replay context and matching primitives.
3. Add raw-price position persistence.
4. Monitor pinned positions on native clocks.
5. Compose advice.
6. Implement Validate Signals tab.
7. Complete verification and document evidence. **Complete.**

Update this active section task-by-task only after each recorded test gate
passes. Current stopping point: **all approved Validate Signals plan tasks are
complete; no commit was made.**
The material below is retained solely as historical Backtest context.

## Archived Backtest Locked Decisions

- Engine package location: `app/backtest_engine/`; this keeps offline jobs and
  the standalone page available in the existing Docker image without changing
  Docker configuration.
- UI placement: standalone `app/pages/backtest_lab.py`.
- Phase 1 trade direction: long-only BUY entries; no short entries and no
  technical early exits. Each TradeEvent is one implicit unit BUY and one
  equal-volume SELL through SL, TP, or timeout; multi-fill support is not in
  the current schema and requires a separately approved model change.
- Combo score: reuse existing technical dimensions, 4/3/2/1/0 points, equal
  group weights, and existing ADX gate semantics.
- Signal trigger: one BUY on the upward crossing of the searched threshold,
  not one signal for every bar above threshold.
- Search: indicator subsets by dimension, BUY threshold grid `{60, 65, 70,
  75, 80}`, ADX gate modes `soft/hard`, horizon, and theme variant.
- Risk/holding defaults: ATR(14), SL `1.5x`, TP `2.5x`, Swing timeout 15
  daily bars with first exit at entry plus three daily bars; Mid-term timeout
  `MAX_HOLD_MIDTERM_BARS = 16` inclusive weekly bars with first exit on the
  next weekly bar. Same-bar SL wins only among eligible exit bars.
- Validation defaults: pooled `MIN_N=30`, six-month windows, one-month
  sliding stride, moving block permutation size 20, 1000 permutations, seed
  42, Deflated-Sharpe/PSR cutoff `0.95`.
- Certification math: unannualized per-trade returns, Pearson kurtosis,
  empirical variance across the exact observed trial Sharpe set, and DSR
  cutoff `0.95`; annualization is display-only.
- Early warning: replay persisted combo, ATR exit, and saved VN-Index
  condition against fresh bounded data; expose no-signal, active, open, and
  timeout-resolved states plus certification age and certified/current diff.
- Job runner: submit immediately through an isolated
  `python -m backtest_engine.worker` subprocess. It atomically persists a JSON
  request and queued/running/done/failed sidecars, keeps progress monotonic,
  serializes no callable, and never imports Streamlit or `main.py`. Database
  URL ports are validated before engine creation; terminal worker failures log
  a job-ID traceback without logging configuration values.
- Container startup: the Compose file is under `docker/`, so Compose must load
  the repository-root `.env` during interpolation, not only as `env_file`.
  Use `docker compose --env-file .env -f docker/docker-compose.yml up -d
  --force-recreate app`; `env_file` alone does not populate `${POSTGRES_PORT}`
  while Compose constructs `DATABASE_URL`.
- Backtest page: a required selected Horizon radio (`Swing` or `Mid-term`) and
  unchecked `INCLUDE_THEME_OPTION` produce one no-theme run or two sibling
  runs (no-theme plus fixed VN-Index `AND`). Request-defining controls and Run
  remain disabled while any submitted job is queued/running/unreadable;
  per-variant statuses/results render independently and update automatically
  every second without a Refresh button. All existing controls, status, and
  results are under `Collect Signals`; `Validate Signals` is intentionally a
  static deferred-work tab. Prices remain raw in engine artifacts.
- Theme: optional no-theme, AND, or OR; VN-Index confirmation uses SMA(50)
  daily for Swing and SMA(20) weekly for Mid-term, aligned as-of signal date.
- Persistence: JSON source of truth; exactly two current files per ticker,
  with-theme and without-theme; re-certification overwrites the selected file.
- Long-running work: background job only. The current isolated worker evaluates
  combos and windows sequentially; its parent uses one reaper thread only to
  wait for the worker process. Do not assume an executor or add concurrency
  diagnostics without separately approved parallelisation work.

## Global Do / Check / Act Workflow

For every task:

1. **DO:** write the smallest failing test first; run it and record the
   expected RED failure.
2. **CHECK:** implement the minimum behavior, run the focused GREEN tests,
   inspect logic/performance/SQL/side effects, and run the phase gate.
3. **ACT:** update this checklist and `current-status.md` only after the gate
   passes; then begin the next task.

No phase advances with a failing, skipped, or unrecorded test. No production
code is written until the plan is approved. No page integration occurs before
the engine and job contracts are proven.

## Archived Backtest Phase Tracker

### Phase 0 — Freeze Contracts and Test Fixtures

- [x] Task 0.1 — Define and test `BacktestConfig`, `IndicatorCombo`,
  `TradeEvent`, and `JobStatus`. Test: `tests.test_backtest_contracts`.
- [x] Task 0.2 — Verify RED for missing contracts. Test command is recorded in
  the implementation plan.
- [x] Task 0.3 — Implement named constants and validated dataclasses only.
- [x] Task 0.4 — Verify GREEN, serialization, invalid-input rejection, and
  contract self-review.

Phase gate: PASS — Docker `tests.test_backtest_contracts` 8/8, compile check
passed, and all Phase 0 schema decisions are frozen.

### Phase 1 — Data Quality, Raw History, and Indicator Adapter

- [x] Task 1.1 — Write RED data-quality tests for structure, prices, duplicate
  dates, >7% findings, gaps, and raw-value preservation.
- [x] Task 1.2 — Verify `tests.test_backtest_data_quality` fails for the
  expected missing implementation.
- [x] Task 1.3 — Implement `data_quality.py` and parameterized raw history
  loading; malformed data blocks indicators, warnings are explicit.
- [x] Task 1.4 — Verify data-quality GREEN and no raw BIGINT mutation.
- [x] Task 1.5 — Write RED indicator-adapter tests for all eight existing
  indicators and horizon parameter reuse.
- [x] Task 1.6 — Implement `indicators.py` as a narrow adapter over existing
  `commons.technical_analysis` functions.
- [x] Task 1.7 — Verify adapter GREEN, SQL safety, and storage-boundary review.

Phase gate: PASS — Docker focused Phase 1 tests pass 11/11; existing
Technical Analyze regressions pass 9/9; SQL, BIGINT, UI-import, and protected
boundary review passed.

### Phase 2 — Combo Generation and Exact Signal Score

- [x] Task 2.1 — Write RED tests for bounded subsets, fixed weights, soft/hard
  ADX gates, threshold grid, and upward crossing semantics.
- [x] Task 2.2 — Verify expected RED failure.
- [x] Task 2.3 — Implement deterministic `signal_combos.py` generation and
  score functions without duplicating live scoring constants.
- [x] Task 2.4 — Verify GREEN and deterministic combo ordering.
- [x] Task 2.5 — Self-review for no flat cross-product, no short signal, no
  weight search, and no level-trigger duplication.

Phase gate: PASS — Docker combo tests pass 4/4; cumulative backtest and
Technical regression gate passes 32/32; no short path, weight search, or
level-trigger duplication found.

### Phase 3 — Rolling Windows and Vectorized Long Trade Engine

- [x] Task 3.1 — Write RED full-coverage rolling-window tests.
- [x] Task 3.2 — Write RED trade fixtures for no look-ahead, next-open entry,
  SL/TP, same-bar SL priority, timeout, and crossing-only signals.
- [x] Task 3.3 — Verify both rolling/trade test files fail for expected missing
  implementation.
- [x] Task 3.4 — Implement vectorized `rolling_window.py` execution.
- [x] Task 3.5 — Verify GREEN on all synthetic fixtures.
- [x] Task 3.6 — Self-critique entry timing, ATR date, overlap, and process
  safety before validation work.

Phase gate: PASS — Docker rolling/trade tests pass 7/7; cumulative backtest
and Technical regression tests pass 39/39; vectorized future-bar scan,
no-look-ahead, next-open, SL-first, TP/SL level prices, and timeout checks
passed.

### Phase 4 — VN-Index Theme Alignment

- [x] Task 4.1 — Write RED no-theme/as-of/SMA/AND/OR tests.
- [x] Task 4.2 — Verify expected RED failure.
- [x] Task 4.3 — Implement `vnindex_theme.py` with backward/as-of alignment.
- [x] Task 4.4 — Verify GREEN and no-look-ahead review.

Phase gate: PASS — Docker theme tests pass 5/5; cumulative focused suite
passes 44/44; as-of, daily/weekly SMA, no-theme, AND/OR, compile, and
protected-boundary checks passed.

### Phase 5 — Statistical Validation and Certification

- [x] Task 5.1 — Write RED reference math, min-n, block-permutation, and
  deterministic-seed tests.
- [x] Task 5.2 — Verify expected RED failure.
- [x] Task 5.3 — Implement Deflated-Sharpe pre-filter and shortlist-only
  permutation validation.
- [x] Task 5.4 — Verify GREEN and rejected candidates never permute.
- [x] Task 5.5 — Write RED certification/persistence tests for pooled n,
  top-one-per-metric, empty state, two files, overwrite, atomicity, and
  round-trip schema fidelity.
- [x] Task 5.6 — Implement `certify.py` and JSON persistence.
- [x] Task 5.7 — Verify GREEN and review theme-file isolation.

Phase gate: PASS — Phase 5 tests pass 9/9; cumulative backtest and Technical
regression tests pass 53/53 in Docker; compile, atomic overwrite, empty-state,
round-trip, and protected-boundary checks passed.

### Phase 6 — Early Warning Replay and Diff

- [x] Task 6.1 — Write RED replay tests for both theme variants, data-quality
  failure, all current states, timeout resolution, staleness, and diff output.
- [x] Task 6.2 — Verify expected RED failure.
- [x] Task 6.3 — Implement `check_current_situation()` by composing the same
  indicator, score, theme, and trade functions.
- [x] Task 6.4 — Verify GREEN and exact replay-drift parity.

Phase gate: PASS — Phase 6 replay tests pass 7/7; cumulative backtest and
Technical regression tests pass 60/60 in Docker; fresh-data quality rejection,
all four ticker states, timeout parity, both theme modes, persisted-rule
validation, certification age, compile, and protected-boundary checks passed.

### Phase 7 — Offline Job Runner and Status Polling

- [x] Task 7.1 — Write RED job lifecycle tests for immediate submission,
  queued/running/done/failed status, monotonic progress, errors, and worker
  configuration.
- [x] Task 7.2 — Verify expected RED failure.
- [x] Task 7.3 — Implement `job_runner.py` with process workers and atomic JSON
  status sidecars, never blocking Streamlit.
- [x] Task 7.4 — Verify GREEN and process cleanup.

Phase gate: PASS — Phase 7 tests pass 3/3; cumulative backtest and Technical
regression tests pass 63/63 in Docker; queued/running/done/failed lifecycle,
monotonic progress, atomic sidecars, spawned worker pool, worker default,
compile, and protected-boundary checks passed. Superseded for current behavior
by the isolated module-worker repair below.

### Phase 8 — Standalone Backtest Page

- [x] Task 8.1 — Write RED page/AppTest tests for controls, submit-only
  behavior, polling, result sections, empty state, and downloads.
- [x] Task 8.2 — Verify expected RED failure.
- [x] Task 8.3 — Implement `app/pages/backtest_lab.py` and minimal `main.py`
  navigation integration; reuse Plotly and price-output conventions.
- [x] Task 8.4 — Verify GREEN with Docker AppTest/headless smoke and no page
  errors/warnings.

Phase gate: PASS — Phase 8 page/AppTest tests pass 5/5; pipeline composition
and cumulative backtest/Technical regression tests pass 69/69 in Docker;
navigation, submit-only behavior, status polling, three result sections,
empty-state, downloads, compile, and protected-boundary checks passed.

### Phase 9 — Profiling, Verification, and Documentation Handoff

- [x] Task 9.1 — Run the first full 15-year profile and record runtime, RSS,
  workers, combo/window counts, and quality exclusions.
- [x] Task 9.2 — Run full Docker unittest discovery; record exact count.
- [x] Task 9.3 — Run `git diff --check` and protected-boundary diff checks.
- [x] Task 9.4 — Load implementation-review skill and fix all self-critique
  findings.
- [x] Task 9.5 — Update FOCUS, current-status, architecture if needed, and
  the verification report; mark only evidenced phases complete.

Phase gate: PASS WITH DOCUMENTED EXCEPTION — profile evidence, focused 69/69
Docker gate, compile, boundaries, whitespace, and docs pass. Full Docker
discovery is 194/195 with one pre-existing `scripts` package import error
outside this feature.

### Phase 10 — Backtest Page Run Variants and Control Lock

- [x] Task 10.1 — Write RED tests for no-default Horizon radio, one/two exact
  config variants, fixed `AND`, and disabled request controls while busy.
- [x] Task 10.2 — Verify expected RED failures before production changes.
- [x] Task 10.3 — Implement page-only multi-job submission, labelled polling,
  per-variant results, and terminal-state unlock.
- [x] Task 10.4 — Verify GREEN in Docker AppTest and focused Backtest/Technical
  regression gates.
- [x] Task 10.5 — Self-review, profile the two-job request if needed, and
  synchronize context and verification evidence.

Phase gate: PASS — RED/GREEN evidence is recorded; Backtest page tests pass
9/9 and the focused Backtest/Technical Docker gate passes 124/124. Temporary
syntax compilation, protected-boundary, whitespace, and independent review
checks pass. No two-job live profile was needed because this page-only change
reuses the separately profiled existing worker contract.

### Phase 11 — Runtime Configuration Guard and Lab Tab Split

- [x] Task 11.1 — Write and verify RED/GREEN tests for empty explicit database
  URL ports and valid URL preservation.
- [x] Task 11.2 — Persist the existing UI-safe failure status and log one
  job-ID traceback for worker-factory exceptions.
- [x] Task 11.3 — Add native `Collect Signals` and `Validate Signals` tabs;
  retain every existing collection element and automatic polling in Collect.
- [x] Task 11.4 — Run the explicit-module Backtest Docker gate, compilation,
  whitespace, and non-writing live URL preflight.
- [x] Task 11.5 — Diagnose the live `DATABASE_URL` failure as Compose-time
  interpolation before `env_file` injection; user-confirm a successful
  Backtest run after the runtime configuration was corrected.

Phase gate: PASS — 75/75 Backtest Docker tests, compile, whitespace, and a
credential-safe live preflight (`postgresql`, `db`, `5432`) pass. No live job
was submitted during automated verification, so current signal artifacts were
not overwritten. The later user-confirmed live Backtest run completed without
the URL-port failure.

## Archived Backtest Stopping Point

Phase 11 Backtest work is complete and remains documented for reference.
Current task: diagnose empty FPT Backtest signal sets. Task 0 is complete:
both empty FPT artifacts are freshly hashed and the source-conformance Docker
gate passes 9/9. Task 1 is complete: after the live runtime URL was corrected,
its read-only FPT Swing probe selected one all-dimension/60/soft-ADX combo and
measured 3,736 scores, all `50`. Only raw `OBV` matched the seven requested
trend-label inputs; there were zero threshold hits and zero BUY crossings. This
conclusively selects Task 2: repair the score-input contract first. The
URL-port blocker, recovery, and exact output are retained in the triage report.
Task 2 is complete. The approved canonical MA sources are the first existing
pair for each horizon: Swing `5/10` and Mid-term `4/12`. The adapter now adds
seven causal label columns while preserving raw numeric values, and the scorer
uses those labels rather than numeric `OBV`. Its RED gate failed as expected;
the focused adapter/scorer/pipeline/replay/trade gate passes 27/27. The
read-only FPT rerun resolved all seven inputs, reached 60 on 1,358 rows, and
produced 228 BUY crossings. Task 5 is complete: its RED gate exposed entry-bar
historical/replay exits and an accepted three-bar custom hold; the shared
Swing-only `MIN_EXIT_OFFSET_SWING_BARS = 3` boundary now enforces closure from
entry + 3 daily bars, retains stop-first ordering, and rejects a custom hold
below four inclusive bars. Task 6 is complete: its DSR gate passed 5/5; the
read-only full 15-year FPT Swing grid produced 123 qualified no-theme and 43
qualified VN-Index `AND` combos, with no combo below `MIN_N`. The current
engine therefore does not reproduce the old empty artifacts; the detailed
per-combo funnel evidence is in the two dated JSON reports. Overlapping-window
duplicates are material (about 81%) and remain deliberately undeduplicated
pending a separate statistical-design decision. Tasks 3 and 4 remain
unselected. Task 7 is complete: one shared weekly OHLCV adapter now supplies
Mid-term ticker indicators and VN-Index confirmation; Mid-term SL/TP starts at
the next weekly bar and its inclusive timeout is bar 16. The all-weekly Docker
gate passes 42/42 and the preserved Swing lifecycle gate passes 20/20. The
read-only FPT Mid-term baseline transformed 3,736 daily rows into 775 weekly
scores, with 410 scores at or above 60 and 41 BUY crossings. Task 8 is
complete: its exact Backtest Docker suite passes 60/60, including the mocked
diagnostics CLI after its stale mock report was aligned with the existing
summary contract. Host compilation and `git diff --check` pass. Full generic
Docker discovery remains noncanonical because `tests/` is not an importable
package for worker fixtures and `scripts/` is not mounted; this pre-existing
test-layout limitation is recorded separately. The zero-signal investigation
plan is complete. Tasks 3 and 4 remain unselected. Next action: await a new
prioritized WIP item; do not resume the paused comprehensive-unit-test work
without a separate plan. No Task 8 job, signal artifact, status sidecar,
database record, or commit was created.
