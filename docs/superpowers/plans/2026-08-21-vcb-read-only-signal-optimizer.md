# VCB Read-Only Signal Optimizer — Implementation Plan

> **For Codex:** Required skill: use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add a manual, read-only VCB research optimizer that searches every non-empty subset of the four existing V3 entry gates over the full available 15-year VCB history, independently for Swing and Midterm and with and without VNIndex confirmation. It must identify exact in-sample winners for win rate, cumulative per-trade profit, and unannualized Sharpe.

**Architecture:** Keep V3 rulebook configuration, signal generation, execution, and saved-result code untouched. The new `backtest_engine.research_optimizer` module will build the existing per-horizon V3 indicator frame once, generate research-only subset entry signals, run the existing causal execution engine, and apply the existing validation statistical primitives across each horizon's full search family. The runner writes Markdown only to stdout; the host captures it into `docs/superpowers/reports/` because Docker does not mount `docs/`.

**Tech Stack:** Python 3.12, pandas, existing app backtest-engine modules, PostgreSQL through the existing engine helper, Docker, unittest.

**Design:** `docs/superpowers/specs/2026-08-21-vcb-read-only-signal-optimizer-design.md`

## Global constraints

- Research scope is VCB only; all price history available in the database is the in-sample window.
- Evaluate 15 gate subsets × 2 theme modes = 30 candidates for each horizon, 60 total.
- Allowed gates only: `rulebook_rsi_upcross`, `rulebook_joint_trend_pass`, `rulebook_volume_gate`, and `rulebook_adx_gate`. Thresholds, ATR exits, holding rules, and all V3 presets remain canonical.
- A missing required input always blocks an entry. Theme mode is strict `background-theme/AND` over the selected price gates and the existing aligned VNIndex confirmation.
- Use `run_rulebook_trade_sequence` and `RulebookExecution` for every simulation. Do not duplicate trade timing or exits.
- Candidate eligibility is `n >= 5`, `PSR >= 0.95`, `DSR >= 0.95`, and moving-block permutation `p <= 0.05` (1,000 draws, seed 42, block size 20).
- Compute DSR against every finite-Sharpe candidate with `n >= 5` in the same horizon before statistical eligibility filters. Never calculate a pairwise-only DSR.
- Winners are exact-value ties on the complete floating-point values: separately best win rate, `profit_pct = sum(per-trade percentage returns)`, and unannualized Sharpe. A candidate can win more than one metric.
- No migrations, persistence, V3 result writes, rulebook configuration changes, new dependencies, Docker changes, or modifications to `common_queries.py`.

## File structure

| File | Responsibility |
|---|---|
| Create `app/backtest_engine/research_optimizer.py` | Candidate enumeration, subset entry signals, execution evaluation, search-wide statistics, Markdown renderer, manual CLI. |
| Create `tests/test_research_optimizer.py` | Deterministic unit and integration-boundary tests for the research module. |
| Create after a successful live run `docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md` | Captured manual research result; do not create a placeholder. |
| Update after implementation `FOCUS.md` and `ai-context/current-status.md` | Accurate completion state, report path, command, and research-only boundary. |

## Task 1: Define candidates and causally safe subset entry signals

**Files:**

- Create: `app/backtest_engine/research_optimizer.py`
- Create: `tests/test_research_optimizer.py`

**Step 1: Write failing tests for candidate enumeration and entry semantics.**

Add test cases that prove:

1. Each horizon has exactly 30 candidates: all 15 non-empty subsets in both `no-theme` and `background-theme/AND` modes.
2. Candidate identities are deterministic, gate order is canonical, duplicates or unknown gates are rejected, and the zero-gate subset cannot exist.
3. A subset requires only its selected gate columns, while `rulebook_missing_required_input` is always required.
4. Any missing required input produces `False` even when selected gates pass.
5. A themed candidate is an AND of the price-side subset signal and the aligned theme signal; an unthemed candidate does not read theme.

Use a tiny timestamp-indexed DataFrame that supplies every gate column, `rulebook_missing_required_input`, and a theme Series. First run:

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchCandidateTests -v
```

Expected: failure because the module does not yet exist.

**Step 2: Implement the immutable candidate contract and deterministic grid.**

In `research_optimizer.py`:

- Define ordered constants mapping the four allowed gate identifiers to existing frame columns.
- Define frozen `ResearchCandidate` with `horizon`, registered-V3 `theme_variant`, and canonical non-empty `gates`. Validate horizon against `HORIZONS`, variant against `THEME_VARIANTS`, exact canonical ordering, uniqueness, and membership.
- Expose a stable human-readable candidate identity such as `swing:no-background-theme:rsi_upcross+joint_trend`.
- Implement `enumerate_candidates(horizon)` with `itertools.combinations` in the fixed gate order, emitting no-theme then themed variants for each subset.

**Step 3: Implement the subset signal builder.**

Implement `candidate_entry_signal(frame, candidate, theme_signal=None)`:

```python
entry = ~frame["rulebook_missing_required_input"]
for column in selected_gate_columns:
    entry &= frame[column]
if candidate.theme_variant == "background-theme":
    entry &= aligned_theme_signal
return entry.fillna(False).astype(bool)
```

Raise a clear `ValueError` for non-DataFrame input, a missing required price-side column, absent theme when theme mode requires it, or a theme index that does not exactly match the price frame. Missing data is not a selectable research gate and cannot be bypassed.

**Step 4: Run tests and inspect the public contract.**

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchCandidateTests -v
git diff --check
```

Expected: candidate tests pass and no whitespace errors.

## Task 2: Reuse native execution and apply search-wide statistical eligibility

**Files:**

- Modify: `app/backtest_engine/research_optimizer.py`
- Modify: `tests/test_research_optimizer.py`

**Step 1: Write failing tests for result evaluation, family bounds, and winner ties.**

Add tests which patch only the existing statistical primitives to make the decision table deterministic:

1. `evaluate_horizon` routes each candidate's signal through `RulebookExecution` and `run_rulebook_trade_sequence`, never a local exit simulator.
2. Results below five completed exits receive an ineligible `min_n` state without PSR, DSR, or permutation calls.
3. The DSR trial family contains all same-horizon candidates with `n >= 5` and finite Sharpe, including candidates that later fail PSR or permutation eligibility.
4. DSR uses the same family length for no-theme and theme candidates; it is never a pairwise comparison.
5. A candidate must pass PSR, DSR, and permutation in that order to be eligible, with a transparent rejection reason.
6. `rank_winners` preserves every exact equal winner per metric and lets one candidate hold multiple metric labels.

Run:

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchStatisticsTests -v
```

Expected: failure because evaluation and ranking are not yet implemented.

**Step 2: Add result models and direct reuse of native execution.**

Define frozen `ResearchResult` with at least:

- candidate identity and underlying `ResearchCandidate`;
- emitted `TradeEvent` sequence and completed-exit count;
- exact `win_rate`, `profit_pct`, and `sharpe`;
- `psr`, `dsr`, `permutation_p_value`, `trial_count`;
- `state` (`eligible` or `ineligible`) and a single machine-readable `reason`.

Implement an internal canonical execution factory:

```python
spec = rulebook_for(candidate.horizon)
return (
    RulebookExecution(spec)
    if candidate.theme_variant == "no-background-theme"
    else RulebookExecution(
        spec,
        theme_variant="background-theme",
        theme_mode="AND",
    )
)
```

For every candidate, pass `candidate_entry_signal(...)` to existing `run_rulebook_trade_sequence(frame, execution, entry_signal)`. Derive the three metrics from the returned completed `TradeEvent` sequence with the existing return convention:

```python
returns = [event.return_pct for event in events]
profit_pct = float(sum(returns))
win_rate = sum(value > 0 for value in returns) / len(returns) * 100.0
sharpe = calculate_unannualized_sharpe(returns)
```

Do not change or invoke `validate_rulebook_treatments`: its V3 minimum sample requirements and pair comparisons are intentionally not this research contract.

**Step 3: Implement the search-wide eligibility pass.**

Implement `apply_search_statistics(results)` after raw candidate execution:

1. Mark any candidate with `n < 5` as `min_n`.
2. Build the one same-horizon DSR family from all remaining candidates with finite Sharpe.
3. For each family member calculate `calculate_probabilistic_sharpe(returns, benchmark=0.0)` and `calculate_deflated_sharpe(observed_sharpe, family_sharpes)`.
4. If PSR is below 0.95, mark `psr`; else if DSR is below 0.95, mark `dsr`; else calculate `moving_block_permutation_test(returns, observed_sharpe, n_permutations=1000, block_size=20, seed=42)` and mark `permutation` if p exceeds 0.05; otherwise mark `eligible`.
5. Record the exact score values and the family trial count in every evaluated result. A non-finite Sharpe is ineligible as `non_finite_sharpe` and never enters the DSR family.

Implement `rank_winners(eligible_results)` without rounded comparison:

```python
best = max(result.sharpe for result in eligible_results)
winners = [result for result in eligible_results if result.sharpe == best]
```

Repeat separately for `win_rate` and `profit_pct`. Return no winner for a metric if that horizon has no eligible candidates.

**Step 4: Run focused tests.**

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchStatisticsTests -v
git diff --check
```

Expected: statistics tests pass and ties remain uncollapsed.

## Task 3: Load once, render Markdown to stdout, and provide the manual CLI

**Files:**

- Modify: `app/backtest_engine/research_optimizer.py`
- Modify: `tests/test_research_optimizer.py`

**Step 1: Write failing runner and rendering tests.**

Cover:

1. The database wrapper loads VCB history exactly once and VNINDEX history exactly once for the declared research bounds.
2. Both raw histories are validated with the existing data-quality functions before research starts; the VCB quality audit is retained in the run metadata.
3. Each horizon builds its own canonical V3 frame and existing VNIndex confirmation from the loaded raw data; no cached Swing frame is reused for Midterm.
4. Markdown explicitly says `in-sample`, displays start/end bounds, `n >= 5`, statistical thresholds, seed, permutation count, block size, and the DSR search-family definition.
5. Markdown includes both winner tables and the complete candidate audit table with raw metrics, exact values, state/reason, and trial count.
6. The module has no report filesystem write path and no persistence call, especially no `save_rulebook_result`.

Run:

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchRunnerTests -v
```

Expected: failure until orchestration and rendering are present.

**Step 2: Implement raw-history collection and per-horizon orchestration.**

Add:

- `collect_vcb_research(engine, as_of)`: calculate the 15-year bounds, call `load_ticker_history` once for `VCB` and once for `VNINDEX`, validate both, and audit VCB.
- `collect_research_from_histories(vcb_raw, vnindex_raw, as_of)`: the testable in-memory core. For each horizon, call `build_rulebook_frame(vcb_raw, rulebook_for(horizon))` and `build_vnindex_confirmation(vnindex_raw, horizon)`, align with `align_vnindex_asof`, then evaluate all 30 candidates and apply the horizon-local statistics pass.
- A small immutable `ResearchRun` container for bounds, audit information, and per-horizon results.

Use the existing `_database_url()` helper and `get_engine_with_retry()` only in the database wrapper. Do not use pipeline persistence or the normal V3 validation/save path.

**Step 3: Implement Markdown rendering and CLI.**

Implement `render_markdown(run)` and `main(argv=None)`:

- `python -m backtest_engine.research_optimizer --as-of YYYY-MM-DD` is the only supported manual entry point.
- stdout contains one self-contained Markdown document and nothing else. Operational diagnostics belong on stderr.
- State that all results are full-history in-sample research, not a production recommendation or out-of-sample validation.
- Include a concise methodology block, a Swing section, a Midterm section, exact winner rows for all ties, and an exhaustive candidate audit.
- Preserve exact Python numeric values with `repr` or equivalent; never use rounded display values for selection or reporting.
- Render a clear `no eligible candidate` row when any metric has no winner.

Do not write the report inside the container. The approved host capture command is:

```powershell
docker exec stock_app python -m backtest_engine.research_optimizer --as-of 2026-08-21 |
    Set-Content -Encoding utf8 docs\superpowers\reports\2026-08-21-vcb-15y-signal-optimizer.md
```

**Step 4: Run runner tests.**

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer.ResearchRunnerTests -v
git diff --check
```

Expected: runner and renderer tests pass, and the static test confirms no filesystem or result persistence side effects.

## Task 4: Verify isolation, execute the approved manual research run, and record status

**Files:**

- Modify: `tests/test_research_optimizer.py`
- Create after verified live execution: `docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Step 1: Add the isolation and full-grid integration-boundary test.**

Write one final test that uses synthetic valid data and confirms:

- exactly 30 candidates are assessed for Swing and 30 for Midterm;
- no mutation occurs to `RULEBOOK_SPECS` or a canonical `RulebookSpec`;
- an evaluation invokes neither V3 persistence nor any source-tree or docs write path.

Run the entire new test module:

```powershell
docker exec stock_app python -m unittest tests.test_research_optimizer -v
```

Expected: all new optimizer tests pass.

**Step 2: Run regression coverage for the touched integration seams.**

```powershell
docker exec stock_app python -m unittest \
  tests.test_backtest_rulebook_config \
  tests.test_backtest_indicators \
  tests.test_backtest_trade_execution \
  tests.test_backtest_validation \
  tests.test_backtest_pipeline \
  tests.test_research_optimizer -v
git diff --check
```

Expected: all listed suites pass and no whitespace errors. If a failure occurs, stop implementation and use the project bug-diagnosis workflow before proposing a repair.

**Step 3: Run VCB research through the approved host-owned report capture.**

Only after tests pass, run:

```powershell
docker exec stock_app python -m backtest_engine.research_optimizer --as-of 2026-08-21 |
    Set-Content -Encoding utf8 docs\superpowers\reports\2026-08-21-vcb-15y-signal-optimizer.md
Get-Content docs\superpowers\reports\2026-08-21-vcb-15y-signal-optimizer.md -TotalCount 80
```

Inspect that the report has both horizons, all 60 candidate rows, exact metrics, eligibility reasons, and no claim of out-of-sample validity. If Docker or database access is unavailable, do not fabricate results; retain the tested implementation and record the live-run blocker.

**Step 4: Perform required self-review and document the accurate stopping point.**

Load and execute `ai-skills/skill-implementation-review.md`. Check especially:

- canonical V3 frame and execution reuse;
- no changes to V3 configs, results, database schemas, or common query code;
- no price scaling or time-zone path touched;
- complete search family is used for DSR and exact ties are preserved;
- report is host-captured only and no filesystem/persistence side effect exists in the optimizer.

Resolve all findings, rerun the relevant tests, then update `FOCUS.md` and `ai-context/current-status.md` with the final test evidence, report path, manual command, research-only status, and any blocker.

**Step 5: Commit in reviewable increments.**

After each task's checks pass, create a focused commit:

```powershell
git add app/backtest_engine/research_optimizer.py tests/test_research_optimizer.py
git commit -m "feat: add read-only VCB signal optimizer"
git add docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md FOCUS.md ai-context/current-status.md
git commit -m "docs: record VCB optimizer research results"
```

Before each commit, inspect `git status --short` and stage only files belonging to this plan; preserve unrelated user changes.
