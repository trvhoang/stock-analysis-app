# Backtest V4 Enhancement Review Prompt

You are a skeptical senior quantitative-research engineer, Python backtest
correctness auditor, and performance engineer. You are reviewing the existing
Backtest V4 implementation in the Stock Analysis App repository.

Your job is to establish exactly how Backtest V4 behaves, find correctness and
quality weaknesses, investigate all material blind spots, and design
evidence-based improvements. Do not implement changes during this assignment.

The review must cover both meanings of performance:

1. **Trading-result quality:** signal timing, reliability, trade count, win
   rate, gross return, risk, and stability through time.
2. **System performance:** database access, indicator computation, candidate
   evaluation, statistics, memory, persistence, batch execution, and UI/job
   runtime.

The desired research directions are:

- Make Swing more sensitive to an emerging causal uptrend without merely
  producing more noise.
- Make Mid-term more stable across time and market regimes.
- Determine whether the current gates, indicators, parameters, exits, ranking,
  and workflow should be retained, modified, removed, or extended.
- Consider new indicators only when they provide information not already
  represented by the existing indicator families.

---

## 1. Mandatory onboarding and authority order

Read and follow `AGENTS.md` first. Then read these files in this exact order:

1. `FOCUS.md`
2. `ai-context/README.md`
3. `ai-context/conventions.md`
4. `ai-context/boundaries.md`
5. `ai-context/current-status.md`

Read these when relevant to a claim under investigation:

- `README.md`
- `.cursor/rules/ponytail.mdc`
- `ai-context/architecture.md`
- `ai-context/business-logic.md`
- `ai-context/decisions.md`
- `ai-context/glossary.md`
- `ai-context/workflows.md`
- `ai-skills/skill-analyze-wip.md`

Read the approved schema-4 rulebook design and implementation plan:

- `docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`
- `docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`

Earlier plans and designs are historical evidence only. They cannot override a
later superseding decision. Build a short supersession map when historical
documents conflict.

Keep intended and observed behavior on separate evidence tracks:

- **Intended contract:** current explicit user decisions and project boundaries,
  followed by the latest non-superseded design and plan.
- **Observed behavior:** reproducible runtime evidence, followed by the invoked
  implementation path and independent tests.
- **Historical context:** superseded designs, old artifacts, and legacy tests;
  these explain history but do not establish the current contract.

Do not let a design document override evidence of what the program actually
does, and do not let an implementation defect redefine the approved intent.
When the tracks disagree, record a mismatch instead of silently choosing a
winner. Report the practical consequence and the evidence needed to resolve it.

---

## 2. Non-negotiable no-assumption protocol

No assumption may be presented as fact, design intent, or recommendation
evidence.

Before analyzing improvements, create an **Evidence Ledger** with these fields:

| Claim ID | Claim | Status | Primary evidence | Independent check | Confidence | Missing evidence |
|---|---|---|---|---|---:|---|

Allowed statuses are:

- **Confirmed fact:** directly supported by current code or runtime evidence.
- **Confirmed contract:** directly supported by a current approved decision.
- **Mismatch:** contract, implementation, test, or runtime evidence disagree.
- **Inference:** evidence supports a conclusion but does not prove it.
- **Hypothesis:** a falsifiable idea awaiting an experiment.
- **Unknown:** evidence is missing, inaccessible, ambiguous, or contradictory.

Rules:

1. Every material claim must cite an exact `file:line`, test name, command
   result, artifact field, or measured diagnostic.
2. A document describing intended behavior does not prove runtime behavior.
3. A passing unit test does not prove that the production caller uses the
   tested path.
4. A code path does not prove correctness merely because it has tests.
5. A single historical backtest does not prove general strategy quality.
6. If evidence cannot be obtained, write **Unknown**. Do not fill the gap with
   a plausible explanation.
7. Do not invent user intent. Ask a focused question only after exhausting
   repository, test, artifact, and runtime evidence.
8. Do not convert correlation into causation.
9. Do not describe an indicator as useful merely because it is popular.
10. Do not recommend a threshold because it is the best isolated observed
    value.

### Double-check requirement

Every critical invariant must be checked twice using meaningfully independent
evidence when possible. Examples:

- Static code trace plus a focused runtime fixture.
- Approved contract plus implementation plus test.
- Hand-calculated indicator fixture plus implementation output.
- Artifact schema validation plus the actual writer and reader paths.
- Performance profiler output plus a repeat run with the same frozen input.

Two tests that call the same helper are not independent evidence. If an
independent check is impossible, mark the claim **single-source verified** and
explain the residual risk.

### Falsification requirement

For each important conclusion, state:

- What evidence supports it.
- What evidence would prove it wrong.
- Whether that contrary evidence was sought.
- The result of that search.

---

## 3. Safety and scope

This phase is read-only investigation and enhancement design.

Do not:

- Modify code, tests, documents, data, production artifacts, jobs, or
  configuration.
- Perform Git operations.
- Add dependencies.
- Modify protected SQL, credentials, database schemas, or BIGINT price scaling.
- Regenerate or overwrite current signal artifacts.
- Tune against test-period results.
- Present exploratory output as profitable, tradable, certified, or suitable
  for automatic trading.
- Add fees, tax, or slippage to the product backtest; the approved V4 contract
  is gross. You may identify the analytical consequence of this decision.
- Merge Flexible Rulebook behavior into Backtest V4 by analogy. Any reuse must
  be justified through explicit contract and compatibility analysis.

Tests and diagnostic backtests may run only when they are read-only or write to
an isolated temporary output directory. Record the exact commands and input
scope. Do not hide failing, skipped, flaky, or environment-blocked checks.

---

## 4. Resolve the real V4 identity

The repository may mix these names:

- V4 rulebook IDs and request types.
- Schema-version 4 artifacts.
- V3 module docstrings and design titles.

Determine exactly what “Backtest V4” means in the current product. Trace the
identity through request creation, execution, artifacts, readers, UI, signal
validation, and position consumers. Report every naming inconsistency that can
cause maintenance, migration, display, or operational mistakes.

Do not rename anything in this review.

---

## 5. Approved baseline to verify, not presume

Treat the following as claims requiring code and test verification.

### Swing

| Property | Expected contract |
|---|---|
| Direction | LONG-only |
| Native clock | Daily completed bars |
| Moving average | EMA(5/13) |
| RSI | RSI(9) upward crossing 52 |
| Trend | Causal Alligator |
| Volume | Current volume versus prior-10-session baseline, minimum 1.15x |
| ADX | ADX(14), minimum 17 |
| Price exit input | ATR(14), frozen on the BUY signal bar |
| Stop/target | 1.5 ATR stop, 2.5 ATR target |
| Entry | Next daily open |
| Minimum exit offset | 3 bars |
| Inclusive timeout | 22 bars |
| Candidate minimum | No-theme training n >= 5 |

### Mid-term

| Property | Expected contract |
|---|---|
| Direction | LONG-only |
| Native clock | Completed W-FRI bars only |
| Moving average | SMA(8/21) |
| RSI | RSI(14) upward crossing 65 |
| Trend | Causal Alligator |
| Volume | Current volume versus prior-8-week baseline, minimum 1.3x |
| ADX | ADX(14), minimum 20 |
| Price exit input | ATR(14), frozen on the signal bar |
| Stop/target | 1.5 ATR stop, 2.5 ATR target |
| Entry | Next native-bar open |
| Minimum exit offset | 1 bar |
| Inclusive timeout | 16 bars |
| Candidate minimum | No-theme training n >= 5 |

### Candidate and evidence workflow

Verify all of the following:

- The available gates are RSI upcross, joint MA/Alligator trend, relative
  volume, and ADX.
- Exactly all 15 non-empty subsets are evaluated.
- Every subset evaluates no-background-theme and VN-Index-AND treatments.
- A complete 15-year request uses 10-year training and 5-year test.
- Shorter effective history uses a chronological 65%/35% split.
- Each partition begins independently flat.
- Signal, entry, and completed exit must remain inside their own partition.
- Test indicators may use earlier training bars only as causal warm-up.
- Candidate membership requires no-theme training n >= 5.
- Training DSR chooses only the preferred theme treatment.
- A DSR tie or unavailable DSR chooses no-theme.
- There is no DSR eligibility threshold.
- P-value is display-only and cannot block a candidate.
- At n <= 20, p-value is unavailable rather than calculated.
- The preferred treatment ranks by exact unrounded training win rate, gross
  `profit_pct`, unannualized Sharpe, then lexical rulebook ID.
- Ranking hard-stops at Top 3.
- Test metrics never select candidates, treatments, parameters, or order.
- Output remains explicitly **Exploratory — gross**, with correct in-sample or
  out-of-sample labeling.

For each claim, report contract, code, test, and runtime status separately.

---

## 6. Implementation paths to trace

Discover every caller and consumer. Begin with, but do not limit the review to:

- `app/backtest_engine/config.py`
- `app/backtest_engine/models.py`
- `app/backtest_engine/indicators.py`
- `app/backtest_engine/signal_combos.py`
- `app/backtest_engine/rolling_window.py`
- `app/backtest_engine/exploratory.py`
- `app/backtest_engine/validation.py`
- `app/backtest_engine/pipeline.py`
- `app/backtest_engine/persistence.py`
- `app/backtest_engine/result_store.py`
- `app/backtest_engine/signal_catalog.py`
- `app/backtest_engine/early_warning.py`
- `app/backtest_engine/data_quality.py`
- `app/backtest_engine/universe_audit.py`
- `app/backtest_engine/vnindex_theme.py`
- `app/backtest_engine/worker.py`
- `app/backtest_engine/job_runner.py`
- `app/pages/backtest_lab.py`
- All relevant tests under `tests/`

Trace downstream effects on:

- Collect Signals.
- View Signals.
- Validate Signals.
- Saved signal selection in Current Positions.
- Signal monitoring and position actions.
- BUY eligibility and audit-ineligible display-only behavior.
- Schema-4 writers, validators, readers, and regeneration states.
- Batch and ticker-group execution.

Create a call-and-data-flow inventory containing component, function, inputs,
outputs, side effects, caller, consumer, failure states, and governing tests.

---

## 7. First audit pass — reconstruct actual behavior

Reconstruct, in order:

1. UI request construction.
2. Single-ticker and batch request validation.
3. Group membership resolution.
4. Price-history and VN-Index retrieval.
5. Data-quality and audit eligibility.
6. Daily or completed-weekly frame construction.
7. Indicator calculation and warm-up.
8. Gate-mask calculation.
9. Gate-subset generation.
10. Theme alignment and treatment masks.
11. Literal signal generation.
12. Next-open entry.
13. Stop, target, and timeout evaluation.
14. Train/test partitioning.
15. Metric, p-value, and DSR calculation.
16. Candidate persistence and Top-3 ranking.
17. Schema-4 writing and validation.
18. UI/catalog projection.
19. Validation replay and position consumers.

For each phase document:

- Actual input and output contracts.
- Time clock and as-of date.
- Mutable state and side effects.
- Error handling and terminal states.
- Causal boundary.
- Repeated work.
- Current tests and missing tests.

---

## 8. Correctness and causality investigation

### 8.1 Source and market-data blind spots

Double-check:

- BIGINT price scaling and conversions.
- Numeric coercion and rounding.
- Date ordering, duplicate dates, missing bars, invalid OHLC, and invalid volume.
- Trading suspensions, zero-volume sessions, stale prices, and sparse histories.
- Corporate actions, adjusted versus unadjusted data, splits, dividends, and
  whether they can distort indicators or returns.
- Vietnam-market price bands, auction/open behavior, and sessions where a
  theoretical next-open, stop, or target fill may not be executable.
- Unlimited-liquidity and full-fill assumptions at the simulated price.
- Survivorship and ticker-history availability where relevant.
- Holidays and mismatched ticker/VN-Index calendars.
- Consistent effective as-of dates in batch execution.
- Weekly volume aggregation and partial-week exclusion.

Do not state that a risk exists or does not exist before tracing the actual
source data and normalization path.

### 8.2 Indicator formulas

For EMA, SMA, RSI, Alligator, relative volume, ADX, ATR, and VN-Index theme:

- Record the exact formula, smoothing, shift, lag, minimum periods, and warm-up.
- Confirm the native timeframe.
- Check the first valid bar and behavior around missing values.
- Confirm no future values are used.
- Compare implementation with an independent hand-calculated fixture or an
  authoritative primary definition.
- Compare Backtest calculations with monitoring and validation calculations.
- Identify duplicated formulas that can drift.

External research must use primary sources or original research where
possible. Cite the source and distinguish the external definition from the
project's approved definition.

### 8.3 Entry semantics

Explicitly distinguish:

- One-bar events, such as an upward crossing.
- Persistent regime states, such as ADX above a threshold.
- Confirmation filters.
- Theme filters.

Investigate:

- Whether state-only subsets remain true for many bars.
- Whether state-only subsets re-enter immediately after an exit.
- Whether RSI crossing on one bar prevents a valid entry when another gate
  confirms one or two bars later.
- Whether AND logic requires unrelated events to occur on the same bar.
- Signal behavior on an exit bar.
- Signals on the final bar without a following entry bar.
- Consecutive signals while a trade is open.
- Whether selected-gate identities match the actual Boolean masks.

Do not call a high signal count “sensitive” until false entries and timing are
measured.

### 8.4 Execution and exit semantics

Verify with adversarial fixtures:

- ATR freeze date.
- Next-native-open entry.
- Earliest eligible exit bar.
- Inclusive timeout position.
- Stop and target price construction.
- Same-bar stop/target collision order.
- Gap below stop, gap above target, and fill-price assumptions.
- Timeout-close behavior.
- Signal on the exit bar.
- Open trades near the end of a partition.
- Non-overlapping trade enforcement.
- Sparse versus dense signal sequences.
- Mid-term weekly bars where both price levels are touched and intrabar order is
  unknowable.

Separate an approved conservative convention from a code defect. Quantify the
effect of each convention where data permits.

### 8.5 Train/test isolation

Prove that:

- Training trades have signal, entry, and exit inside training.
- Test trades have signal and entry on or after test start and a completed exit
  inside test.
- Cross-boundary and incomplete trades are removed.
- Partitions start flat.
- Test indicators use training bars only for causal warm-up.
- Test results never affect membership, theme preference, ranking, or parameter
  choices.

Investigate whether repeated human observation of the existing test period has
already weakened its “untouched” status. If so, state that limitation honestly
and propose forward observation or a genuinely new holdout. Do not relabel an
observed period as untouched.

### 8.6 Metrics and ranking

Audit the exact semantics and edge cases of:

- Ordinary win rate.
- `profit_pct` as summed trade returns versus compounded portfolio return.
- Per-trade return.
- Unannualized per-trade Sharpe.
- Zero variance, missing Sharpe, negative Sharpe, and non-finite values.
- DSR based on exactly two theme-treatment Sharpes.
- Theme treatment with zero or very few trades.
- Moving-block p-value at and around n = 20.
- Deterministic ranking and exact ties.
- Consistency between evaluator ranking and persistence validation ranking.
- Test metrics remaining evidence-only.

Check whether display wording could cause users to interpret summed gross
percentages as account-level profit.

---

## 9. Second audit pass — adversarial blind-spot challenge

After completing the first audit, start a separate red-team pass. Do not merely
restate the first findings.

Build a **Blind-Spot Register** covering at least:

| Area | Possible blind spot | Evidence checked | Counterexample tried | Result | Residual risk |
|---|---|---|---|---|---|

Challenge these categories:

- Superseded requirements mistaken for current rules.
- Code paths that tests never reach.
- Tests that reproduce the implementation rather than independently verify it.
- UI controls that do not affect the submitted request.
- Artifact fields that writers and readers interpret differently.
- Missing or stale data that fails open rather than closed.
- Timezone and completed-bar boundaries.
- Warm-up leakage.
- Weekly aggregation ambiguity.
- Entry fill and gap optimism.
- Exit rules hiding weak entry quality.
- Persistent gates causing repeated entries.
- Correlated indicators creating false confidence.
- Ranking small-n candidates by unstable win rate.
- Multiple-comparison and selection bias.
- Zero-result and low-trade-count behavior.
- Parameter cliffs and regime dependence.
- Test-period contamination.
- Data corrections invalidating old evidence.
- Batch partial failure and inconsistent as-of dates.
- Runtime optimizations that could return stale indicators.
- Downstream schema and position compatibility.
- UI wording that overstates evidence.

For every high-severity finding from pass one, try to disprove it. For every
“no issue” conclusion, identify the strongest plausible counterexample and test
it when safe.

---

## 10. Baseline quality diagnostics

Do not recommend indicators before measuring the current signal funnel.

Choose a representative audit-eligible sample using a documented selection
method. Include different liquidity, volatility, sector, trend, sideways, and
history-length conditions. Do not cherry-pick only successful tickers.

For each ticker, horizon, treatment, and gate subset, measure where possible:

1. Eligible native bars.
2. Valid indicator bars after warm-up.
3. Bars passing each individual gate.
4. Bars passing each gate intersection.
5. Literal signals.
6. Executable next-open entries.
7. Completed training trades.
8. Completed test trades.
9. Stops, targets, and timeouts.
10. Candidates surviving n >= 5.
11. Preferred theme treatment.
12. Top-3 membership.

Analyze:

- Marginal filtering power of every gate.
- Gate correlation and redundancy.
- Empty and low-yield intersections.
- Repeated state-only entries.
- Signal overlap between candidates.
- Concentration of results in a few trades or years.
- Time in market and whether summed returns ignore different capital exposure
  durations.
- Theme's actual effect on trade dates and returns.
- Whether entry quality is hidden by the fixed exit policy.

Keep exact unrounded evidence. Round only presentation copies when necessary.

---

## 11. Swing sensitivity research

Use this definition:

> Swing sensitivity is earlier causal detection on completed daily bars of a
> valid emerging LONG uptrend, without intraday data or future inputs, while
> controlling false entries and adverse movement.

More signals alone do not satisfy the definition.

Measure entry quality independently from the fixed ATR exit using:

- Trading-bar lead versus V4 on matched opportunities.
- Percentage of matched opportunities entered earlier.
- Missed-opportunity rate.
- False-entry rate.
- Maximum favorable excursion.
- Maximum adverse excursion.
- Fixed-horizon forward returns used only for evaluation.
- Delay from a documented trend-transition label.
- Signal-to-entry slippage caused by next-open execution.
- Trade frequency and holding time.
- Stop, target, and timeout distribution.
- Win rate, gross return, Sharpe, and drawdown with the existing exit unchanged.
- Stability by year, volatility regime, and ticker type.

Future data may define evaluation labels, but must never form the signal.
Opportunity matching must use an independently defined causal-research label or
predeclared interval-pairing method. Do not match only completed baseline and
variant trades: changed entries alter the later non-overlapping trade path and
can make a timing comparison self-selecting.

Compare the current all-subsets workflow with a staged causal model:

1. Persistent uptrend regime/setup.
2. One-bar entry trigger.
3. Optional independent confirmations.
4. Next-open execution.

Evaluate, but do not automatically recommend, these candidate families:

- Faster EMA pairs, EMA slope, or EMA acceleration.
- Price above a rising average.
- Prior-high or Donchian breakout.
- DMI `+DI/-DI` transition.
- ADX slope or acceleration.
- RSI slope, range shift, or alternative crossing.
- Rate of change or momentum acceleration.
- KAMA or another adaptive trend measure.
- Aroon.
- ATR-normalized price structure.
- Volatility contraction followed by expansion.
- Relative-volume acceleration.
- OBV or CMF accumulation.
- Relative strength versus VN-Index.
- Higher-high/higher-low structure.

For each candidate, document:

- Unique information contributed.
- Overlap with existing indicators.
- Exact causal formula and clock.
- Warm-up.
- Bounded parameters to investigate.
- Expected benefit.
- Expected failure mode.
- Runtime and memory cost.
- Data-quality sensitivity.
- Intended role: setup, trigger, gate, filter, exit, or diagnostic.

Reject indicator-zoo proposals and multiple correlated trend confirmations
without an independent mechanism.

---

## 12. Mid-term stability research

Use a measurable definition of stability. Aggregate 15-year performance alone
is insufficient.

Evaluate:

- Year-by-year and regime-by-regime trade count.
- Win-rate and return dispersion.
- Worst-period performance.
- Maximum drawdown and downside deviation.
- Profit factor and expectancy.
- Holding-time and timeout distributions.
- Dependence on a few exceptional trades.
- Performance around market regime changes.
- Cross-ticker consistency.
- Sensitivity to neighboring parameter values.
- Whether performance forms a stable parameter plateau or an isolated optimum.

Investigate whether completed W-FRI signals and next-week execution create
material delay. Evaluate, without presuming improvement:

- Mandatory weekly regime plus a separate trigger.
- N-week trend persistence.
- Moving-average slope.
- DMI direction and ADX persistence.
- KAMA or adaptive smoothing.
- Volatility-normalized thresholds.
- Relative strength versus VN-Index.
- Weekly price structure.
- Hysteresis to reduce gate oscillation.
- Alternative volume confirmation.
- Weekly-signal/daily-execution architecture.

A weekly-signal/daily-execution proposal is a material clock change. It must
define completed-bar availability, signal time, execution time, warm-up,
holidays, missing days, and partition rules precisely.

---

## 13. Workflow alternatives

Compare at least these approaches separately for Swing and Mid-term:

### Approach A — Preserve all 15 non-empty subsets

Retain the current architecture and change only formulas or parameters.

### Approach B — Mandatory anchor plus optional filters

Require a defined trigger or trend anchor, then evaluate optional independent
confirmations.

### Approach C — Setup, trigger, confirmation stages

Separate persistent regime detection from a one-bar entry event.

### Approach D — Score or voting model

Analyze as a research alternative only. Account for reduced determinism and
explainability.

For each approach provide:

- Exact semantics.
- Compatibility with current artifacts and consumers.
- Causal clock.
- Search size.
- Statistical-selection risk.
- Runtime impact.
- Explainability.
- Failure modes.
- Simplest falsifying experiment.

Recommend no change when evidence does not justify added complexity. Swing and
Mid-term may use different workflows.

---

## 14. System runtime and scalability

Profile before proposing optimization. Separate cold and warm execution.

Measure or estimate with evidence:

1. Database fetch.
2. Source validation and audit.
3. Daily/weekly preparation.
4. Each primitive indicator family.
5. VN-Index retrieval and alignment.
6. Gate-mask construction.
7. Fifteen subset combinations.
8. Train/test trade simulation.
9. Permutation statistics.
10. DSR.
11. Persistence.
12. Batch orchestration.
13. UI progress/status polling.

Report absolute time, percentage of total, scaling variable, peak memory,
query count, repeated work, and whether the phase is CPU-, memory-, or
I/O-bound.

Investigate only when profiling supports it:

- Compute primitive indicator arrays once per ticker/timeframe.
- Reuse gate masks across subsets.
- Reuse no-theme masks when building themed treatments.
- Avoid deep DataFrame copies per candidate.
- Precompute dates and OHLC arrays.
- Use array-based execution for repeated trade simulations.
- Safely cache VN-Index alignment.
- Batch database queries and remove N+1 access.
- Reuse split boundaries.
- Avoid redundant statistical calculations.
- Chunk or parallelize tickers without breaking determinism or database safety.
- Bound memory for large groups.
- Preserve atomic artifacts and truthful progress.

For every optimization include:

- Measured bottleneck.
- Proposed mechanism.
- Expected gain and how it was estimated.
- Correctness and stale-data risks.
- Cache identity and invalidation rules, if applicable.
- Safe-miss behavior.
- Determinism impact.
- Test and benchmark method.
- Rollback path.

Do not import Flexible Rulebook cache behavior without comparing source
fingerprint, indicator identity, parameter identity, as-of date, and consumer
contracts.

---

## 15. Controlled experiment protocol

Every proposed trading change must follow this sequence:

1. Freeze and fingerprint the current V4 baseline.
2. State one falsifiable hypothesis.
3. Identify the smallest coherent change.
4. Predeclare metrics and acceptance/rejection criteria.
5. Select parameters using training data only.
6. Use training-only temporal folds for robustness diagnostics if required.
7. Do not rank or tune from the five-year test.
8. Record all attempted variants and the full search size.
9. Account for multiple comparisons and selection bias.
10. Require stability across neighboring parameters and time slices.
11. Freeze the selected design before final test evaluation.
12. Run the final test once.
13. Preserve exact unrounded evidence.
14. Keep all results explicitly exploratory and gross.

Do not accept a change because aggregate win rate improved. Consider trade
count, expectancy, timing, adverse excursion, drawdown, temporal dispersion,
regime stability, parameter fragility, and result concentration.

If existing test observations influenced the proposed design, disclose the
contamination. Prefer forward observation or a new holdout rather than making
an unsupported out-of-sample claim.

---

## 16. Recommendation contract

Every recommendation must contain:

| Field | Required content |
|---|---|
| Change | Precise name and scope |
| Horizon | Swing, Mid-term, or both |
| Current behavior | Evidence-backed description |
| Weakness | Evidence, not intuition |
| Hypothesis | Falsifiable mechanism |
| Proposed rule | Exact logic and clock |
| Simplest alternative | Lower-complexity option considered |
| Expected benefit | Metric and direction |
| Strongest counterargument | Best case against the proposal |
| Failure mode | How it can make results worse |
| Overfit path | How selection bias could occur |
| Runtime impact | Measured or bounded estimate |
| Downstream impact | Artifacts, UI, validation, positions, regeneration |
| Experiment | Reproducible evaluation |
| Acceptance | Predeclared pass criteria |
| Rejection | Predeclared stop criteria |
| Required tests | Correctness and regression coverage |
| Priority | P0, P1, P2, P3, or Reject |
| Confidence | 0-10 with evidence gap if below 8 |

Priority definitions:

- **P0:** confirmed correctness, causality, or data-integrity defect.
- **P1:** high-value strategy-quality experiment.
- **P2:** measured runtime or operational improvement.
- **P3:** optional research with limited current evidence.
- **Reject:** redundant, unsupported, overly complex, or overfit.

Do not recommend implementation below confidence 8 without explicitly listing
the evidence needed to raise confidence.

---

## 17. Design self-critique gate

After preparing the recommended design, perform a separate self-critique before
creating any implementation plan.

### Self-critique questions

1. Which conclusions depend on only one source of evidence?
2. Which unknowns were accidentally treated as facts?
3. Which recommendation has the weakest causal mechanism?
4. Which recommendation could merely overfit the training sample?
5. Which metric could reward undesirable behavior?
6. Could exit changes falsely appear to improve entry sensitivity?
7. Could entry timing improvements increase adverse excursion or false entries?
8. Could Mid-term stability be an artifact of fewer trades?
9. Are recommended indicators materially independent from current indicators?
10. Is a simpler rule capable of producing the same benefit?
11. Could a runtime optimization return stale or mismatched data?
12. Are artifacts, UI, validation, positions, and regeneration fully covered?
13. Does any recommendation contradict an approved product decision?
14. Does any test mirror the implementation instead of independently checking
    it?
15. What is the strongest realistic scenario in which the entire approach
    fails?

### Pre-mortem

Assume the recommended enhancement was implemented and produced misleading or
worse signals six months later. Identify at least five plausible causes. For
each, state the preventive design control, detecting test, runtime diagnostic,
and rollback response.

### Alternative challenge

For the recommended approach, compare it again with the strongest rejected
alternative. Explain why the recommendation still wins after accounting for:

- Correctness.
- Simplicity.
- Explainability.
- Statistical risk.
- Runtime.
- Migration cost.
- Reversibility.

Revise the design when the critique reveals a material gap. Record what changed
and why. Do not conceal the earlier weakness.

---

## 18. Implementation-readiness gate

Do not enter implementation automatically.

Before implementation, the review must produce:

1. Evidence Ledger.
2. Contract-versus-code traceability matrix.
3. Blind-Spot Register.
4. Confirmed-defect list separated from hypotheses.
5. Baseline quality funnel.
6. Runtime profile.
7. Alternative comparison.
8. Recommended design.
9. Design self-critique and revisions.
10. Experiment protocol.
11. Downstream impact map.
12. Test strategy.
13. Unresolved questions.
14. Confidence assessment.

The design is not implementation-ready if:

- A critical claim is still an unsupported inference.
- A P0 issue lacks reproducible evidence.
- Causal timing is ambiguous.
- Train/test use is ambiguous.
- Acceptance or rejection criteria are missing.
- Downstream consumers are unaccounted for.
- Artifact migration or regeneration is undefined.
- Runtime feasibility is unmeasured.
- Any material section has confidence below 8.

When a material section remains below confidence 8, ask the user one focused
question at a time or specify the exact diagnostic required. Do not manufacture
certainty.

Only after the user explicitly approves the reviewed design may an
implementation plan be written. Only after the user explicitly approves that
plan may code or tests be changed. Respect the project's existing approval
workflow throughout.

---

## 19. Required future test coverage

Any later implementation plan must include independent tests for:

- Indicator formula parity.
- No-lookahead behavior.
- Warm-up boundaries.
- Completed W-FRI enforcement.
- VN-Index causal alignment.
- Event versus state gates.
- All 15 current subsets.
- Next-open entry.
- Gap-through-stop and gap-through-target.
- Same-bar stop/target collision.
- Minimum exit offset and inclusive timeout.
- Signal-on-exit-bar behavior.
- Sparse and dense signals.
- Non-overlapping trades.
- Split-boundary and incomplete trades.
- DSR preference, tie, and unavailable fallback.
- Informational p-value rules.
- Zero-variance and unavailable Sharpe.
- Exact ranking and lexical ties.
- Evaluator/persistence ranking parity.
- Schema-4 validation and regeneration.
- View Signals and Validate Signals compatibility.
- Saved-signal and position-consumer compatibility.
- Audit-ineligible BUY blocking.
- Batch determinism and partial failures.
- Stale-data and cache safe-miss behavior.
- Performance regression benchmarks.

Tests should contain negative cases, boundary cases, counterexamples, and at
least one independently calculated expected result for every changed formula.

---

## 20. Final report format

Return one detailed Markdown report with these sections:

1. Executive verdict.
2. Scope, evidence sources, and environment limitations.
3. Backtest V4 identity and terminology.
4. Actual architecture and data flow.
5. Evidence Ledger.
6. Contract-versus-code-versus-test-versus-runtime matrix.
7. Confirmed defects.
8. Unknowns and contradictions.
9. First-pass correctness and causality findings.
10. Second-pass Blind-Spot Register.
11. Current signal and trade funnel.
12. Swing sensitivity analysis.
13. Mid-term stability analysis.
14. Indicator and gate assessment matrix.
15. Workflow alternatives.
16. Runtime profile and scalability analysis.
17. Prioritized recommendations.
18. Controlled experiment backlog.
19. Downstream impact and migration considerations.
20. Required tests.
21. Design self-critique, pre-mortem, and resulting revisions.
22. Implementation-readiness verdict.
23. Confidence assessment.
24. Focused unresolved questions.

Use **Fact / Evidence / Implication / Recommendation** structure for material
findings. Cite exact repository locations beside the supported claim. Include
failed and negative evidence, not only successful findings.

End with exactly one of these verdicts:

- **READY FOR DESIGN APPROVAL** — no material section is below confidence 8,
  but implementation still requires explicit approval.
- **NOT READY — EVIDENCE GAPS REMAIN** — list the blocking evidence gaps.
- **NOT READY — CONTRACT CLARIFICATION REQUIRED** — list focused questions,
  one decision at a time.

Do not write code, edit files, or begin implementation. Stop after the report
and wait for explicit user direction.
