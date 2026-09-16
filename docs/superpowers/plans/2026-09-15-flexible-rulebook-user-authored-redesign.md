# Flexible Rulebook User-Authored Redesign Implementation Plan

> **For agentic workers:** Execute tasks in order with TDD. Do not commit,
> stage, inspect, or run Git commands. Finish authorized tasks without asking
> for approval between individual steps. Stop before any legacy-data deletion.

**Goal:** Replace automated Flexible Rulebook discovery with a usable
user-authored rulebook builder, database-backed train/test evaluator, immutable
library, and optional Backtest Collect integration while preserving Standard
behavior.

**Architecture:** Build a clean `flexible_rulebook.v2` vertical slice beside
the current runtime. Reuse proven calendar, data-quality, exact indicator,
execution, fingerprint, cache, metric, and atomic-write concepts through tested
adapters. Cut the page and Backtest integrations over only after v2 passes.
Then remove old discovery code/tests while leaving every v1 runtime artifact
read-only.

**Tech stack:** Python 3.12, Streamlit, pandas, NumPy, SQLAlchemy, PostgreSQL,
unittest, Docker. No new dependency.

**Design:**
`docs/superpowers/specs/2026-09-15-flexible-rulebook-user-authored-redesign-design.md`

## Global constraints

- Standard remains the default Collect Signals mode and its schema-5 behavior
  must not change.
- Long-only; one native timeframe per rulebook; Daily Swing or completed W-FRI
  Mid-term.
- No future data, partial weekly bar, intraday logic, automatic order, or
  Position mutation.
- BUY is ALL/ANY selected conditions plus ALL gates. SELL is ANY technical or
  price exit, with mandatory timeout.
- Fixed `min_hold_bars=3`; user timeout 4–64 native bars.
- Gross results only; no fees, tax, slippage, certification, or performance
  gate for publishing.
- Default Lifetime range and 65/35 split; allowed train ratios are
  50/55/60/65/70/75/80.
- Use exact full IDs backstage. UI displays `Standard` or
  `Flexible · FR-<collision-safe-short-id>`.
- Flexible validation classifications are: Closely Match `>85%`, Nearly Match
  `65%..85%`, and No Match `<65%` or Weakening/Invalidated.
- Read current database data through existing engine/retry patterns. Preserve
  raw BIGINT price storage and divide by 1000 only at UI boundaries.
- Respect VN-Index session alignment and live Listed/Delisted status.
- Never modify `common_queries.py`, credential loading, BIGINT scaling, or
  Docker files.
- Existing v1 Flexible artifacts remain read-only and invisible to v2. Do not
  migrate, move, or delete them.
- Use `apply_patch` for source/document edits. No Git action.
- If Docker is unavailable, retry once and then use the safest available host
  verification while reporting the limitation.

## Delivery phases

| Phase | Tasks | Outcome |
|---|---|---|
| A — Safety and contracts | 0–1 | Frozen baseline, v2 grammar and registry |
| B — Trusted evaluation core | 2–4 | Causal indicators, history, cache, execution, metrics |
| C — Usable Flexible page | 5–6 | Draft/evaluate/publish/retire workflow |
| D — Backtest integration | 7 | Standard/Flexible Collect and downstream adapters |
| E — Retirement and closure | 8–9 | Old runtime removed, artifacts quarantined, docs/tests current |

Must-have functionality is not complete until Task 6. The approved Backtest
integration is not complete until Task 7. Old logic is not cleaned up until
Task 8. Do not mark the plan complete earlier.

---

## Task 0: Freeze behavior, inventory legacy references, and add cutover guards

**Files:**

- Create: `tests/test_flexible_rulebook_v2_cutover.py`
- Create: `scripts/audit_flexible_rulebook_legacy.py`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

### Steps

- [x] Add a read-only inventory script that reports current v1 files by kind,
  path root, and count without parsing them as v2 or modifying them.
- [x] Inventory all Python imports, Streamlit page routes, subprocess entry
  points, tests, `/data/flexible-benchmark` references, and Backtest/Position
  references to the current package.
- [x] Add a failing cutover test declaring the intended final public surface:
  three workspaces, no Discover/benchmark/activation/scope-expansion controls,
  and Standard as the default Backtest source.
- [x] Record the exact focused and full test baselines. Do not "fix" unrelated
  pre-existing failures inside this plan.
- [x] Record in FOCUS/current status that v1 is frozen: correctness fixes only,
  no new discovery features during replacement.

### Verification

```powershell
python scripts/audit_flexible_rulebook_legacy.py
python -m unittest tests.test_flexible_rulebook_v2_cutover -v
docker compose --env-file .env -f docker/docker-compose.yml exec -T app python -m unittest discover -s tests -p "test_flexible_rulebook_*.py" -v
```

Expected RED: only the new v2 cutover assertions fail. Inventory produces no
filesystem mutation.

**Task 0 completed 2026-09-15.** Pre-contract baselines: Flexible Rulebook
suite **327/327** in **22.755s**; full suite **925/925** in **46.332s**.
The read-only inventory found **26** v1 runtime modules, **26** v1 test files,
one active benchmark-policy reference, no Backtest/Position package reference,
and empty existing v1 artifact roots at `/app/Flexible-Rulebook` and
`/data/flexible-benchmark` (both SHA-256 empty-tree digest
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
The cutover contract is intentionally RED with exactly three deferred failures;
its read-only inventory assertion passes. The post-contract focused run was
**331 tests in 23.161s: 328 passed and exactly 3 expected RED**.

---

## Task 1: Define v2 contracts, lifecycle, rule grammar, and indicator metadata

**Files:**

- Create: `app/flexible_rulebook/v2/__init__.py`
- Create: `app/flexible_rulebook/v2/contracts.py`
- Create: `app/flexible_rulebook/v2/registry.py`
- Create: `tests/test_flexible_rulebook_v2_contracts.py`
- Create: `tests/test_flexible_rulebook_v2_registry.py`

### Contracts

- `RulebookDraft`: UUID, revision, name, description, horizon, semantic
  definition, timestamps, lifecycle state.
- `RulebookDefinitionV2`: entry operator, typed BUY predicates, gates,
  technical exits, ATR exits, fixed min hold, timeout, semantic revision.
- `IndicatorSpec`: family/revision, native inputs, roles, output names,
  parameter schema, warm-up, predicates, support projection.
- `PredicateV2`: role, family revision, settings, operator/condition, direction
  lookback.
- `EvaluationRequest`: rule digest, tickers, selected range, training ratio,
  cache choice.
- `EvaluationResult`: source, split, metrics, trades, warnings, terminal state.
- `PublishedRulebook`: full immutable `frb2_` ID and semantic definition.

### Steps

- [x] Write RED tests for canonical ordering, scalar normalization, invalid
  settings, duplicate predicates, ALL/ANY entry, ALL gates, ANY exits, at least
  one BUY condition, mandatory timeout, fixed min hold, and one timeframe.
- [x] Write RED lifecycle tests: draft revision increments; editing changes
  semantic digest; old evidence cannot mark edited content Evaluated; publish
  is immutable; retire preserves identity.
- [x] Write RED short-ID tests, including a forced prefix collision that extends
  both display IDs while full IDs remain unchanged.
- [x] Implement only the contracts needed to make those tests pass.
- [x] Define registry metadata and validated bounds for SMA, EMA, RSI,
  Alligator, ADX/DMI, Stochastic, breakout, relative volume, OBV, ATR,
  Bollinger Bands, and Supertrend.
- [x] Reject unsupported roles and predicates at draft validation, not during a
  worker run.
- [x] Ensure operational fields—ticker, range, split, cache, names, timestamps,
  and results—never enter the published definition hash.

### Verification

```powershell
python -m unittest tests.test_flexible_rulebook_v2_contracts tests.test_flexible_rulebook_v2_registry -v
```

**Task 1 completed 2026-09-15.** TDD began with the expected missing-v2
import failure, then covered semantic grammar, lifecycle, immutable IDs,
collision-safe display IDs, registry roles/bounds, and metadata. Host
verification passed **15/15** in **0.003s**; Python compilation of all three
new v2 modules passed. Docker was unavailable after its one required retry, so
no Docker-specific Task 1 verification was claimed. No SQL, database, price,
dependency, Docker, Standard Backtest, or v1 runtime change was made.

---

## Task 2: Establish authoritative causal indicator primitives

**Files:**

- Create: `app/commons/causal_indicators.py`
- Create: `app/flexible_rulebook/v2/features.py`
- Modify: `app/backtest_engine/indicators.py`
- Modify: `app/commons/technical_analysis.py`
- Create: `tests/test_causal_indicator_primitives.py`
- Create: `tests/test_flexible_rulebook_v2_features.py`
- Modify: `tests/test_backtest_indicators.py` or the existing exact indicator
  test module selected by inventory
- Modify: `tests/test_technical_analysis_indicators.py`

### Steps

- [x] Write golden fixtures for SMA, EMA, exact SMA-seeded Wilder RSI/ATR/ADX
  and DMI, HL2 Alligator SMMA, Stochastic, relative volume, OBV, and prior-bar
  extrema.
- [x] Add prefix-invariance tests: appending future rows cannot change any
  earlier output or mask.
- [x] Move/expose one authoritative implementation per formula in
  `commons.causal_indicators`; leave compatibility wrappers so Standard and
  Technical Analysis produce byte/float-equivalent existing results.
- [x] Write Bollinger fixtures for middle/upper/lower, bandwidth, percent-B,
  warm-up, flat bands, and `ddof=1`; migrate the current implementation behind
  the authoritative primitive without changing its public output.
- [x] Write Supertrend fixtures before implementation: first finite state,
  recursively carried final bands, bullish/bearish flips, gaps, equal-band
  behavior, missing warm-up, and prefix invariance.
- [x] Implement exact HL2 + Wilder ATR Supertrend under a versioned formula ID.
- [x] Implement registry-driven component building. Component cache identity
  includes family revision and math settings, while threshold-only predicate
  changes reuse the component.
- [x] Implement exact predicate masks and post-event support projections.
  Direction means current versus exactly N prior completed native bars;
  equality does not pass.
- [x] Assert all unavailable/warm-up values produce False masks and explicit
  diagnostics, never accidental truth through NaN comparison.
- [x] Run Standard and Technical Analysis parity tests before proceeding.

Task 2 is complete. The initial finite Supertrend state is confirmed bullish
(`+1`) and uses the final lower band. Fresh Docker verification passed **100/100**
across v2 contracts/registry, causal primitives, FeatureStore masks, Backtest
indicator regression, and Technical Analysis parity.

### Verification

```powershell
python -m unittest tests.test_causal_indicator_primitives tests.test_flexible_rulebook_v2_features tests.test_technical_analysis_indicators -v
docker compose --env-file .env -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_indicators tests.test_technical_analysis_indicators -v
```

Use the actual existing Backtest indicator test module name found in Task 0 if
it differs. Do not create a duplicate just to satisfy this command.

---

## Task 3: Implement database history, native bars, adjustable splits, and cache

**Files:**

- Create: `app/flexible_rulebook/v2/history.py`
- Create: `app/flexible_rulebook/v2/cache.py`
- Create: `tests/test_flexible_rulebook_v2_history.py`
- Create: `tests/test_flexible_rulebook_v2_cache.py`

### Steps

- [x] Write RED tests for ticker normalization, Lifetime and explicit bounded
  ranges, existing retry/connection behavior, raw integer OHLCV, source
  fingerprint, and calendar fingerprint.
- [x] Load only currently Listed tickers. Report Delisted as an item skip and
  automatically accept it again when its latest date matches VN-Index.
- [x] Align every source to the VN-Index calendar before indicators.
- [x] Create `NativeBar` with W-FRI bucket label, actual first session, actual
  last session, and OHLCV. Daily bars use the same actual session for all three
  dates.
- [x] Prove weekly aggregation uses first open, max high, min low, last close,
  summed volume, no partial current bucket, and no fictional Friday execution
  date when Friday is a holiday.
- [x] Write RED split tests for every allowed ratio. Floor the training count,
  require at least one native bar in each partition after warm-up, and persist
  exact ordinals/dates.
- [x] Permit earlier causal rows for feature warm-up while requiring signal,
  entry, and exit to remain inside their partition.
- [x] Port the safe per-component cache into the v2 namespace. Require full
  source/calendar/build identity, digest verification, contained paths, atomic
  writes, and safe misses on corruption or mismatch.
- [x] Load/fingerprint each ticker once per operation and reuse unique
  components across selected rulebooks.

### Verification

```powershell
python -m unittest tests.test_flexible_rulebook_v2_history tests.test_flexible_rulebook_v2_cache -v
```

**Task 3 completed 2026-09-16.** TDD covered Lifetime and bounded source
loads, raw BIGINT preservation, live Listed/Delisted handling, calendar/source
fingerprints, Daily and completed W-FRI native bars, all approved chronological
splits, and partition trade containment. The v2 cache persists computed arrays
only under contained v2 paths and binds source, calendar, build revision,
formula revision, and math settings; corrupt, mismatched, interrupted, locked,
or nondeterministic items are safe misses. Cache timestamps normalize to
`Asia/Ho_Chi_Minh`. Host compilation and the focused Docker verification passed
**15/15** in **0.268s**. No v1 runtime/artifact, SQL schema, prices,
dependencies, Docker configuration, or Git history changed.

---

## Task 4: Implement composition, execution, metrics, and validation facts

**Files:**

- Create: `app/flexible_rulebook/v2/execution.py`
- Create: `app/flexible_rulebook/v2/metrics.py`
- Create: `app/flexible_rulebook/v2/validation.py`
- Create: `tests/test_flexible_rulebook_v2_execution.py`
- Create: `tests/test_flexible_rulebook_v2_metrics.py`
- Create: `tests/test_flexible_rulebook_v2_validation.py`

### Steps

- [x] Write composition tests for ALL and ANY BUY conditions, zero/multiple
  gates, gate hard requirements, zero/multiple technical exits, and ANY-exit
  behavior.
- [x] Port the reference flat-to-flat state machine to `NativeBar` dates.
- [x] Cover next-open BUY/technical SELL, suppressed signals while open,
  same-exit-bar re-entry behavior, fixed min hold, user timeout, sparse/dense
  signals, and partition start-flat behavior.
- [x] Cover ATR frozen on signal bar, open gaps, stop, target, trailing prior
  high-water, stop-first same-bar collision, and timeout close.
- [x] Prove Swing dates are sessions and Mid-term signal/fill/exit dates use
  actual last/first sessions rather than W-FRI labels.
- [x] Calculate exact unrounded n, win rate, total gross return, mean gross
  return, and per-trade Sharpe. Return N/A where mathematically unavailable.
  Do not implement qualification thresholds or Top 3.
- [x] Build registry-owned supportive facts. Entry cross support persists only
  while its resulting relation holds; it never becomes a new event.
- [x] Compute support percentage from Boolean facts: ALL BUY exposes each
  condition; ANY BUY exposes one combined fact; each gate is one fact.
- [x] Classify unrounded support as Closely Match `>85`, Nearly Match `65..85`,
  or No Match `<65`. Force No Match for Weakening/Invalidated.
- [x] Require a real prior event, Fresh/On-going state, live post-event support,
  all gates, evidence availability, Listed status, and no duplicate open
  Position before `can BUY`.

### Verification

```powershell
python -m unittest tests.test_flexible_rulebook_v2_execution tests.test_flexible_rulebook_v2_metrics tests.test_flexible_rulebook_v2_validation -v
```

**Task 4 completed 2026-09-16.** The v2 executor is a linear, flat-to-flat
native-bar state machine: BUY and technical SELL fill at the next actual native
open, ATR freezes on the signal bar, trailing uses only prior high-water, and
gap/stop-first/target/deadline precedence is explicit. Completed W-FRI trades
use actual last/first session dates, never fictional Friday execution dates.
Metrics are exact gross per-trade evidence without a qualification threshold.
Boolean composition implements ALL/ANY BUY, ALL gates, and SELL-OR; current
support maps only to Closely Match, Nearly Match, or No Match and BUY eligibility
requires every live fact. Host compilation and focused Docker verification
passed **14/14** in **0.009s**. No v1 runtime/artifact, SQL schema, prices,
dependencies, Docker configuration, or Git history changed.

---

## Task 5: Add v2 storage, draft lifecycle, evaluation service, and publication

**Files:**

- Create: `app/flexible_rulebook/v2/storage.py`
- Create: `app/flexible_rulebook/v2/service.py`
- Create: `tests/test_flexible_rulebook_v2_storage.py`
- Create: `tests/test_flexible_rulebook_v2_service.py`

### Steps

- [x] Write storage tests for the exact v2 directory layout, contained paths,
  canonical JSON, atomic replace, create-or-verify immutability, corrupt files,
  unsupported schema/kind, and no v1 traversal.
- [x] Implement revision-checked draft writes. A stale expected revision fails
  without overwriting a newer draft.
- [x] Implement immutable published definitions and evaluation artifacts.
- [x] Derive Evaluated only when a completed evaluation matches the current
  draft semantic digest. Zero trades still count as a completed evaluation,
  with explicit evidence.
- [x] Require explicit publication intent and a matching completed train/test
  evaluation, but no performance threshold.
- [x] Implement retire/unretire policy only if the design tests prove historical
  references remain readable. Retired rules never appear in new Collect runs.
- [x] Implement clone and draft discard. Draft discard must use a confirmation,
  remove no immutable evaluation, and touch no published/Position reference.
- [x] Implement sequential multi-ticker evaluation with item terminal states
  and progress events for source, features, execution, metrics, and persistence.
- [x] Ensure a failed ticker cannot erase successful results from the same run.
- [x] Implement collision-safe short-ID resolution from the loaded published
  library; never persist or join by the short ID.

### Verification

```powershell
python -m unittest tests.test_flexible_rulebook_v2_storage tests.test_flexible_rulebook_v2_service -v
```

**Task 5 completed 2026-09-16.** V2 now persists only contained
v2/drafts, v2/definitions, v2/evaluations, and cache paths. Draft writes are
atomic and optimistic-revision checked; definitions, evaluation evidence,
retirement, and unretirement events are immutable create-or-verify documents.
Read paths reject corrupt, unsupported, escaped, or content/identity-mismatched
documents and never traverse V1. The service evaluates tickers sequentially,
reports terminal progress, retains completed items when another ticker fails,
and writes exact raw-identity train/test evidence. It uses the Task 3 primitive
cache only when requested, binding source, calendar, formula build, native
timeframe, and math settings; a cache miss or write failure remains in-memory
only. A draft is Evaluated only by matching completed train/test evidence;
explicit publication has no performance gate. Host and Docker verification
passed **21/21** across v2 contracts/storage/service. A read-only Docker
database smoke evaluation of VCB completed from 2010-08-17 through 2026-09-15
on 4,005 Swing bars in a temporary artifact root. No V1 runtime/artifact, SQL
schema, price scaling, dependency, Docker configuration, or Git history
changed.

---

## Task 6: Replace the Flexible Rulebook page with the three-workspace UI

**Files:**

- Rewrite: `app/pages/flexible_rulebook.py`
- Modify: `tests/test_flexible_rulebook_page.py`
- Create: `tests/test_flexible_rulebook_v2_page.py`
- Modify: `tests/test_main_entrypoint.py`

### Steps

- [x] Replace the Workspace choices with Rulebook Builder, Rulebook Backtest,
  and Rulebook Library.
- [x] Builder: implement metadata, horizon, BUY ALL/ANY, dynamic typed
  conditions, gates, technical exits, ATR exits, timeout, readable summary,
  validation errors, save/reset/clone, and revision-conflict handling.
- [x] Populate all indicator and predicate controls from registry metadata;
  never duplicate parameter bounds in UI code.
- [x] Backtest: implement draft/published selector, available Listed database
  tickers/groups, Lifetime/date range, training ratio, cache choice, progress,
  cancel-safe item boundaries, result summary, trades, and diagnostics.
- [x] Library: show status, name, horizon, collision-safe short ID, current
  evidence badge, evaluation history, and actions to edit/clone/publish/retire.
- [x] Hide full hashes in primary UI. Keep them only in collapsed technical
  diagnostics and backstage widget values.
- [x] Use Streamlit callbacks or pre-widget state transitions so reset/add/remove
  actions never mutate a widget key after instantiation.
- [x] Remove all current Discover, benchmark activation, scope expansion,
  qualification, and current-scan UI imports and controls.
- [x] Ensure an empty library gives a useful path: Create Rulebook, not an
  activation-policy error.
- [x] Make the page functional with no `/data/flexible-benchmark` directory.

### Verification

```powershell
python -m unittest tests.test_flexible_rulebook_v2_page tests.test_main_entrypoint -v
docker compose --env-file .env -f docker/docker-compose.yml exec -T app python -m unittest tests.test_flexible_rulebook_v2_page tests.test_main_entrypoint -v
```

Manual smoke test: create RSI/EMA draft, save, evaluate one ticker, publish,
reload the page, and confirm the immutable library entry remains.

---

## Task 7: Integrate Published Flexible rules with Backtest Collect and consumers

**Files:**

- Create: `app/backtest_engine/flexible_adapter.py`
- Modify: `app/backtest_engine/config.py`
- Modify: `app/backtest_engine/signal_catalog.py`
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `app/backtest_engine/signal_removal.py`
- Modify: `app/backtest_engine/manual_position_store.py`
- Modify: `app/pages/backtest_lab.py`
- Create: `tests/test_backtest_flexible_adapter.py`
- Modify: `tests/test_backtest_page.py`
- Modify: relevant existing signal-catalog, validation, signal-removal, and
  manual-position tests found by Task 0

### Steps

- [x] Add an explicit UI source selector with `Standard` first/default and
  `Flexible` second. Do not change Standard `RulebookSpec` or schema-5 pipeline.
- [x] In Flexible mode, list only Published, non-Retired definitions compatible
  with the selected horizon. Allow one or more selections.
- [x] Dispatch a distinct Flexible collection request. Evaluate each
  ticker × definition independently and sequentially through v2 services.
- [x] Persist a distinct Flexible signal artifact kind/schema containing the
  full rulebook ID, semantic digest, evaluation reference, current signal
  events, and source fingerprint. Never serialize it as Standard schema-5.
- [x] Add a unified read-only signal-catalog projection with origin,
  full backstage identity, short display identity, ticker, horizon, metrics,
  signal date, and removal key.
- [x] Update View Signals to display `Standard` or
  `Flexible · FR-<short-id>`, while filtering/removing by full backstage key.
- [x] Update Validate Signals to dispatch Standard candidates to unchanged
  Standard replay and Flexible candidates to v2 validation.
- [x] Expose exactly Closely Match, Nearly Match, and No Match for both origins.
  Preserve Standard artifact/scoring behavior but normalize its raw `weak`
  value to No Match in the shared display/filter projection.
- [x] Extend saved Position signal references with an origin/version union.
  Store the full Flexible ID and evaluation identity; display only short ID.
- [x] Preserve the manual Buy date and all existing P&L/risk behavior.
- [x] Extend signal-removal guards so a Flexible artifact referenced by any
  Position cannot be removed. Valid empty result behavior remains origin-aware.
- [x] Prove switching tabs/session reruns does not change the selected origin,
  corrupt group/ticker state, or mix Standard/Flexible candidates.

### Verification

```powershell
python -m unittest tests.test_backtest_flexible_adapter tests.test_backtest_page -v
docker compose --env-file .env -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_flexible_adapter tests.test_backtest_page -v
```

Manual smoke test: publish one Swing and one Mid-term rule; run Collect in
Standard default, then Flexible; confirm View, Validate, and New Position show
short IDs while artifact/Position JSON contains the full ID.

---

## Task 8: Cut over imports and retire automated discovery code and tests

**Files:**

- Modify: `app/flexible_rulebook/__init__.py`
- Delete after reference proof: the retired modules listed in the design
- Delete after replacement coverage: their behavior-specific test modules
- Modify: all historical Flexible design/plan documents listed by Task 0
- Modify: `tests/test_flexible_rulebook_v2_cutover.py`

### Steps

- [x] Re-run the Task 0 inventory. Stop if any live app route, Backtest path,
  script, current test, or `__init__` export still requires a retired module.
- [x] Export only the v2 public API from the package root.
- [x] Remove retired source modules: activation, benchmark/cap runners,
  campaigns, fixed catalog, current scan, discovery activation, runner,
  scope-expansion workers, search, and worker contracts.
- [x] Remove only tests whose sole subject is retired behavior. Preserve or
  migrate reusable causal, storage, and execution fixtures into v2 tests first.
- [x] Remove obsolete subprocess entry points and active-policy UI paths.
- [x] Do not remove `/data/flexible-benchmark`, v1 Flexible root files, or any
  legacy artifact. Run the audit script afterward and prove counts/digests did
  not change.
- [x] Add a **Superseded by 2026-09-15 user-authored redesign** banner to the
  old Flexible specs/plans. Do not rewrite their historical content.
- [x] Make the cutover test GREEN: only three workspaces and no old runtime
  import/reference from active application code.

### Verification

```powershell
python scripts/audit_flexible_rulebook_legacy.py
python -m unittest tests.test_flexible_rulebook_v2_cutover -v
rg -n "discovery_activation|scope_expansion|cap_benchmark|Current Group BUY Scan|Cross-ticker Qualification" app
```

Expected `rg` output: none from active runtime. Historical strings may remain
only in explicitly superseded documents and read-only audit classifications.

---

## Task 9: Full verification, practical database smoke test, and context closure

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify if architecture changed: `ai-context/architecture.md`
- Modify if business semantics changed: `ai-context/business-logic.md`
- Modify if workflows changed: `ai-context/workflows.md`

### Steps

- [x] Compile all changed Python modules.
- [x] Run all v2 tests, affected Standard Backtest/Position tests, then the full
  suite once. Stop verification when these appropriate gates pass.
- [x] With Docker/database available, evaluate at least one Listed ticker for
  Swing and Mid-term using deterministic small rules. Confirm source range,
  W-FRI actual dates, splits, metrics, persistence, reload, publication, and
  Collect adapter.
- [x] Confirm a Delisted ticker is skipped and a ticker automatically returns
  when its latest date matches VN-Index.
- [x] Confirm no primary UI exposes a full Flexible hash.
- [x] Confirm Standard remains the initial Collect selection and produces the
  same schema-5 output under the same fixture.
- [x] Confirm the legacy audit before/after counts and digests match.
- [x] Update context with exact commands/counts, practical evidence, known
  limitations, and final stopping point.

### Verification

```powershell
python -m compileall app\flexible_rulebook app\pages\flexible_rulebook.py app\backtest_engine
python -m unittest discover -s tests -p "test_flexible_rulebook_v2*.py" -v
docker compose --env-file .env -f docker/docker-compose.yml exec -T app python -m unittest discover -s tests -v
```

**Completion evidence (2026-09-17):** Docker compilation passed; v2 regression
passed **77/77** and full discovery passed **696/696**. The focused Flexible
artifact regression passed **9/9**, including tagged-Decimal round-trip
coverage. A temporary real-database VCB collection/reload smoke succeeded for
both Swing (4,005 daily bars; 283 current events) and Mid-term (830 completed
W-FRI bars; 59 current events). The persisted 65% split boundaries were Swing
training end `2021-01-19` / test start `2021-01-20` and Mid-term training end
`2021-01-22` / test start `2021-01-25`. The temporary directory was removed on
exit. The final legacy audit reported zero v1 runtime modules and zero v1
behavior tests; both preserved v1 artifact roots remained empty with their
original SHA-256 digest.

## Final acceptance checklist

- [x] User can create, validate, save, edit, and clone a rulebook draft.
- [x] Builder exposes the approved indicators with editable validated settings.
- [x] Bollinger and Supertrend causal/golden tests pass.
- [x] Evaluator uses Listed database history, VN-Index sessions, and the chosen
  Daily/W-FRI timeframe without future data.
- [x] All seven train ratios work and preserve immutable split evidence.
- [x] User can publish the exact evaluated draft without a performance gate.
- [x] UI shows collision-safe short IDs; full IDs remain backstage.
- [x] Collect defaults to Standard and can run one or more compatible Published
  Flexible definitions.
- [x] View, Validate, removal guards, and Position references resolve Flexible
  results by full immutable identity.
- [x] Flexible validation uses >85 / 65–85 / <65 classification and never uses
  the old directionless threshold-ratio model.
- [x] Old discovery runtime and UI are removed only after all replacement gates.
- [x] V1 artifacts remain byte-for-byte untouched.
- [x] Focused, affected Standard, and full regression tests pass.
