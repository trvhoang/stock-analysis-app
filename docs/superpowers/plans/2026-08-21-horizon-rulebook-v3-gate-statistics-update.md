# Horizon Rulebook V3 Gate and Statistics Update Implementation Plan

> **Status: Superseded.** Replaced on 2026-08-22 by
> [2026-08-22-horizon-v3-exploratory-multi-rulebook.md](2026-08-22-horizon-v3-exploratory-multi-rulebook.md).
> Do not implement this binary-certification schema-3 plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Recalibrate V3 to use horizon-specific historical entry gates, a
five-exit minimum, default permutation-only certification, and paired DSR when
VN-Index AND is selected.

**Architecture:** `RulebookSpec` becomes the immutable owner of entry-gate names,
ADX threshold, minimum exits, and DSR cutoff. Signal composition and diagnostics
read that policy instead of hard-coding four gates. Validation emits either a
single permutation-only no-theme treatment or two DSR treatments based on one
two-Sharpe family; pipeline failure handling preserves that statistical mode.

**Tech Stack:** Python 3.12, pandas, NumPy, Streamlit, existing Docker unittest
suite. No new dependency.

## Global Constraints

- Implement [the approved amendment design](../specs/2026-08-21-horizon-rulebook-v3-gate-statistics-update-design.md) exactly.
- Swing: `joint_trend_pass AND rulebook_rsi_upcross`, `ADX(14) >= 17`,
  `min_n = 5`, paired DSR cutoff `0.90`.
- Midterm: `joint_trend_pass AND rulebook_volume_gate`, `ADX(14) >= 20`,
  `min_n = 5`, paired DSR cutoff `0.85`.
- ADX, RSI, and volume calculations not selected as a horizon entry gate remain
  monitoring/readout data. Do not remove them.
- Default no-theme runs load no VN-Index and certify only with `min_n` and
  deterministic permutation p-value (`count=1000`, `seed=42`, `block=20`,
  `p <= 0.05`). They serialize `permutation`, null score, and zero trials.
- VN-Index checkbox runs no-theme and VN-Index-AND together. Both use their own
  DSR from the same two unrounded sample-Sharpe family, then their own
  permutation p-value. PSR is not a V3 method.
- Preserve raw BIGINT prices, causal completed bars, W-FRI behavior, ATR exits,
  same-bar execution, V3 schema version, and V2 exclusion.
- Pre-amendment V3 artifacts must be unavailable through canonical rulebook
  validation; do not migrate, rewrite, or fall back to them.
- Do not modify `common_queries.py`, price scaling, Docker files, credentials,
  database schema, or the research optimizer. Keep its research-only PSR helper.
- User instruction: **no Git command, staging, commit, reset, or commit-tree
  change.**

---

### Task 1: Encode immutable gate and threshold policy

**Files:**

- Modify: `app/backtest_engine/config.py:34-342`
- Modify: `app/backtest_engine/signal_combos.py:1-59`
- Modify: `app/backtest_engine/diagnostics.py:32-78, 174-175`
- Test: `tests/test_backtest_rulebook_config.py`
- Test: `tests/test_backtest_signal_combos.py`
- Test: `tests/test_backtest_contracts.py`
- Test: `tests/test_backtest_diagnostics.py`

**Interfaces:**

- Produces `RulebookSpec.entry_gate_columns: tuple[str, ...]` and
  `RulebookSpec.dsr_cutoff: float`; later validation reads `dsr_cutoff`.
- Produces `rulebook_entry_signal(frame, execution, theme_eligible=None)` using
  only `execution.rulebook.entry_gate_columns`, plus the missing-input blocker
  and optional theme AND.
- Produces diagnostics whose sequential rejection keys describe only the active
  horizon entry gates plus `missing_required_input` and optional `theme_and`.

- [ ] **Step 1: Write failing policy and entry-gate tests**

  Replace the old 22/20 and 20/25 assertions with the exact immutable contract:

  ```python
  self.assertEqual(swing.entry_gate_columns, (
      "rulebook_joint_trend_pass", "rulebook_rsi_upcross",
  ))
  self.assertEqual((swing.adx_minimum, swing.min_n, swing.dsr_cutoff), (17, 5, 0.90))
  self.assertEqual(midterm.entry_gate_columns, (
      "rulebook_joint_trend_pass", "rulebook_volume_gate",
  ))
  self.assertEqual((midterm.adx_minimum, midterm.min_n, midterm.dsr_cutoff), (20, 5, 0.85))
  ```

  Add entry tests with all required columns present: Swing remains true when
  volume and ADX are false, but turns false when RSI or joint trend is false;
  Midterm remains true when RSI and ADX are false, but turns false when volume
  or joint trend is false. Keep the existing missing-input and theme-AND tests.
  Assert request dataclass fields no longer contain `deflated_sharpe_cutoff`.
  Update diagnostics assertions to expect default method `permutation`, zero
  trials, and no irrelevant `volume`/`adx` Swing rejection key.

- [ ] **Step 2: Run the focused tests and verify old behavior fails**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_rulebook_config tests.test_backtest_signal_combos tests.test_backtest_contracts tests.test_backtest_diagnostics -v
  ```

  Expected: failures asserting the former all-four-gate contract, old ADX/min-n
  values, PSR diagnostics, and the still-present request cutoff.

- [ ] **Step 3: Implement immutable policy and dynamic gate composition**

  In `RulebookSpec`, add these frozen fields after `joint_trend_required` and
  validate nonempty, known, non-duplicate gate names and `0 < dsr_cutoff <= 1`:

  ```python
  entry_gate_columns: tuple[str, ...]
  dsr_cutoff: float
  ```

  Configure the canonical rulebooks exactly:

  ```python
  # Swing
  adx_minimum=17,
  entry_gate_columns=("rulebook_joint_trend_pass", "rulebook_rsi_upcross"),
  dsr_cutoff=0.90,
  min_n=5,

  # Midterm
  adx_minimum=20,
  entry_gate_columns=("rulebook_joint_trend_pass", "rulebook_volume_gate"),
  dsr_cutoff=0.85,
  min_n=5,
  ```

  Remove `deflated_sharpe_cutoff` from both request dataclasses, their
  validation, `BacktestConfig.as_batch()`, and `BacktestBatchConfig.for_ticker()`.
  In signal composition, derive required columns and the AND loop from the
  execution rulebook rather than `_ENTRY_GATE_COLUMNS`:

  ```python
  required = (*execution.rulebook.entry_gate_columns, "rulebook_missing_required_input")
  if any(column not in frame for column in required):
      return pd.Series(False, index=frame.index, dtype=bool)
  entry = ~gate("rulebook_missing_required_input")
  for column in execution.rulebook.entry_gate_columns:
      entry &= gate(column)
  ```

  Make diagnostics build its sequential gates from the same
  `entry_gate_columns`, mapping known column names to current labels
  (`joint_trend`, `rsi_upcross`, `volume`, `adx`). It must return the entry
  function's literal result, so diagnostic counts and execution cannot drift.
  Change the default diagnostic method label to `permutation`; paired labeling
  is handled in Task 2.

- [ ] **Step 4: Run the focused policy gate**

  Run the Step 2 command.

  Expected: PASS. The tests prove inactive gates do not block history entries,
  while all raw indicator columns remain available for monitoring.

- [ ] **Step 5: Record completion without Git**

  Mark this task complete in this plan only after its test gate passes. Do not
  execute any Git command.

### Task 2: Replace V3 PSR with mode-correct permutation and paired DSR validation

**Files:**

- Modify: `app/backtest_engine/validation.py:1-355`
- Modify: `app/backtest_engine/certify.py:23-51`
- Modify: `app/backtest_engine/persistence.py:107-130`
- Test: `tests/test_backtest_validation.py`
- Test: `tests/test_backtest_certification.py`
- Test: `tests/test_backtest_persistence.py`

**Interfaces:**

- `validate_rulebook_treatments(no_theme_events, themed_events, rulebook,
  include_theme, *, permutation_count, permutation_seed,
  permutation_block_size, permutation_alpha)` no longer accepts a score cutoff.
- `ValidatedRulebookTreatment` accepts only:
  `("permutation", None, 0)` or `("dsr", finite_score, 2)` for
  `(significance_method, significance_score, trial_count)`.
- `certify_rulebook_result()` serializes a qualified permutation result with a
  null score and a qualified DSR result with a finite score.

- [ ] **Step 1: Write failing mode and boundary tests**

  Update event fixtures to use five events for both horizons. Mock the moving
  block result at `p_value=0.01`. Add these test cases:

  ```python
  candidate = validate_rulebook_treatments(
      _events(5), None, rulebook_for("swing"), include_theme=False,
  )["no-background-theme"]
  self.assertEqual(
      (candidate.significance_method, candidate.significance_score, candidate.trial_count),
      ("permutation", None, 0),
  )
  self.assertTrue(candidate.qualified)
  ```

  Patch `calculate_deflated_sharpe` to prove Swing accepts exactly `0.90` and
  rejects `0.899999`; prove Midterm accepts exactly `0.85` and rejects
  `0.849999`. In a checkbox-on run, assert both variants are `dsr` with
  `trial_count == 2`, and the patched function receives the two unrounded
  treatment Sharpe values as its trial family. Assert four events reject
  `min_n` for either horizon.

  Add the paired-unavailable case: `include_theme=True` plus `themed_events=None`
  returns a no-theme empty candidate with
  `missing required themed DSR companion`; it must not be a permutation success.
  Replace V3 PSR-specific tests with an assertion that constructing a V3
  treatment using method `psr` raises `ValueError`. Leave
  `calculate_probabilistic_sharpe` available for the isolated optimizer.

  Update certification/persistence fixtures so a no-theme success uses
  `permutation`, `None`, and `0`; a themed success uses `dsr`, a finite score,
  and `2`. Add malformed document cases for permutation-with-score and
  DSR-with-null-score.

- [ ] **Step 2: Run the validation and artifact tests and verify failure**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence -v
  ```

  Expected: failures because V3 still creates PSR no-theme candidates, applies
  a request cutoff, and rejects a null permutation score.

- [ ] **Step 3: Implement the two statistical modes**

  Keep `calculate_probabilistic_sharpe()` exported for
  `research_optimizer.py`, but remove every V3 call to it. In
  `ValidatedRulebookTreatment.__post_init__`, enforce metadata by method:

  ```python
  if self.significance_method == "permutation":
      valid = self.significance_score is None and self.trial_count == 0
  elif self.significance_method == "dsr":
      valid = self.trial_count == 2 and self.significance_score is not None and isfinite(self.significance_score)
  else:
      valid = False
  if not valid:
      raise ValueError("invalid V3 significance metadata")
  ```

  Refactor `_validate_one_treatment()` to use `permutation` with no score gate,
  or `dsr` with `execution.rulebook.dsr_cutoff`, before the unchanged
  permutation test. Do not round returns, Sharpes, DSR, or p-values before a
  comparison. Default no-theme calls the permutation branch. Paired execution
  first requires both treatment return series to produce finite Sharpes; then it
  calls the DSR branch once per treatment with the same ordered tuple:

  ```python
  trial_sharpes = (no_theme_sharpe, themed_sharpe)
  ```

  If the themed event sequence is absent, return no-theme `empty` with
  `missing required themed DSR companion` and a themed `empty` companion result;
  the pipeline may replace that latter row with a concrete source failure in
  Task 3. If a supplied paired sequence cannot yield a finite two-return Sharpe,
  return empty results with a `paired DSR family unavailable` rejection instead
  of substituting zero Sharpe.

  In certification, require only `candidate.permutation` for every qualified
  result. In persistence, validate method/trial/score combinations by metadata,
  not theme path: no-theme may be `permutation` or paired `dsr`; themed may
  only be `dsr`. Preserve the existing canonical embedded-rulebook equality
  validation so old rulebook JSON becomes unavailable.

- [ ] **Step 4: Run the validation and artifact gate**

  Run the Step 2 command.

  Expected: PASS. The test fixture proves no default V3 path calls PSR, paired
  DSR boundaries are horizon-owned and inclusive, and schema-3 accepts the
  nullable permutation score without weakening DSR validation.

- [ ] **Step 5: Record completion without Git**

  Mark this task complete in this plan only after its test gate passes. Do not
  execute any Git command.

### Task 3: Preserve statistical mode through pipeline, diagnostics, and UI

**Files:**

- Modify: `app/backtest_engine/pipeline.py:211-255, 290-353`
- Modify: `app/backtest_engine/diagnostics.py:113-175`
- Modify: `app/backtest_engine/early_warning.py:111-144`
- Modify: `app/backtest_engine/validation_advice.py:130-157`
- Modify: `app/pages/backtest_lab.py:145-147`
- Test: `tests/test_backtest_pipeline.py`
- Test: `tests/test_backtest_diagnostics.py`
- Test: `tests/test_backtest_early_warning.py`
- Test: `tests/test_backtest_validation_advice.py`
- Test: `tests/test_backtest_page.py`

**Interfaces:**

- `_evaluate_ticker_treatments(..., include_theme=True,
  confirmation_frame=None)` returns a paired-validation result with no-theme
  blocked, rather than evaluating it as a default permutation run.
- `run_backtest_pipeline()` and `run_backtest_batch_pipeline()` persist an empty
  no-theme result plus a themed `failed(reason)` result after a VN-Index
  preflight failure.
- `_format_certification_caption(item: dict[str, object]) -> str` renders
  `Permutation only` without showing a null score and retains the DSR/trial
  details for paired rows.
- `check_current_situation()` and `validate_saved_signals()` preserve the
  certified artifact `p_value` so the caption reports it.

- [ ] **Step 1: Write failing source-failure and presentation tests**

  Change the theme-preflight test so it requires:

  ```python
  self.assertEqual(no_theme["terminal_state"], "empty")
  self.assertEqual(no_theme["rejection_reason"], "missing required themed DSR companion")
  self.assertEqual(themed["terminal_state"], "failed")
  self.assertIn("VN unavailable", themed["failure_reason"])
  ```

  Keep the default no-theme test and assert it never loads VN-Index. Add a
  diagnostics test asserting default `statistical_method == "permutation"` and
  checkbox-on `statistical_method == "dsr"`. Add direct caption tests:

  ```python
  self.assertEqual(
      backtest_lab._format_certification_caption(
          {"significance_method": "permutation", "significance_score": None,
           "trial_count": 0, "p_value": 0.01}
      ),
      "Certification: Permutation only; p-value: 0.01.",
  )
  ```

  Add the matching DSR caption assertion with its score and `trials: 2`.

- [ ] **Step 2: Run the pipeline, diagnostics, and page tests and verify failure**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_pipeline tests.test_backtest_diagnostics tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_page -v
  ```

  Expected: the old source-failure path writes an independently evaluated
  no-theme candidate, diagnostics reports PSR, and no formatter exists.

- [ ] **Step 3: Implement mode-preserving orchestration and rendering**

  Remove the `score_cutoff` argument from the pipeline validation call. Build
  no-theme events first. When `include_theme` is true and confirmation is
  unavailable, pass those events and `themed_events=None` to paired validation;
  do not call validation with `include_theme=False`. The single pipeline then
  persists that no-theme empty row and replaces only the themed row with its
  concrete failed document. The batch pipeline must pass
  `include_theme=config.include_theme` even after shared preflight failure so
  each no-theme result is likewise blocked before themed failures are persisted.

  Update diagnostics labels to `permutation` by default and `dsr` when paired;
  its treatment evidence stays literal from validation. Pass
  `document["signal_set"]["p_value"]` through `check_current_situation()` and
  `_replay_rulebook()` into the Validate result. Add this page helper and call
  it instead of interpolating `None` directly:

  ```python
  def _format_certification_caption(item: dict[str, object]) -> str:
      if item["significance_method"] == "permutation":
          return f"Certification: Permutation only; p-value: {item.get('p_value')}."
      return (
          f"Certification: DSR {item['significance_score']}; "
          f"trials: {item['trial_count']}; p-value: {item.get('p_value')}."
      )
  ```

  Keep existing UI labels, saved-set identity, raw-price conversion, and
  VN-Index checkbox behavior unchanged.

- [ ] **Step 4: Run the pipeline and presentation gate**

  Run the Step 2 command.

  Expected: PASS. Checkbox-off does not touch VN-Index; checkbox-on never
  silently mixes permutation-only and paired-DSR certification after failure.

- [ ] **Step 5: Record completion without Git**

  Mark this task complete in this plan only after its test gate passes. Do not
  execute any Git command.

### Task 4: Update downstream fixtures, documentation, and regression evidence

**Files:**

- Modify: `tests/test_backtest_signal_catalog.py`
- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `docs/superpowers/plans/2026-08-15-horizon-rulebook-signal-redesign.md:1-33`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Test: the complete focused V3 Backtest suite

**Interfaces:**

- Downstream read-only fixtures use valid current schema-3 statistical metadata:
  no-theme default uses `("permutation", None, 0)`; themed uses
  `("dsr", finite_score, 2)`.
- The historic 2026-08-15 plan remains a record but links to this amendment as
  the active implementation authority. `FOCUS.md` keeps the Horizon plan ahead
  of Validate Positions and records the exact post-change stopping point.

- [ ] **Step 1: Run the existing downstream fixture tests and verify expected failure**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_validation_advice tests.test_backtest_early_warning tests.test_backtest_persistence -v
  ```

  Expected: former no-theme PSR fixtures fail schema validation because Task 2
  accepts only current V3 statistical metadata.

- [ ] **Step 2: Update downstream fixtures and add old-artifact rejection evidence**

  Change synthetic no-theme success documents in catalog, validation-advice, and
  early-warning tests to:

  ```python
  "n": 5,
  "significance_method": "permutation",
  "significance_score": None,
  "trial_count": 0,
  "p_value": 0.01,
  ```

  Retain a themed fixture with `"significance_method": "dsr"`, a finite score,
  and `"trial_count": 2`. Add a persistence/read test that a document created
  from the former 22/20/old-ADX canonical rulebook is rejected by
  `load_rulebook_result()` rather than offered as a current signal.

- [ ] **Step 3: Run downstream tests and verify current fixtures pass**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_validation_advice tests.test_backtest_early_warning tests.test_backtest_persistence -v
  ```

  Expected: PASS. The valid current fixtures load, while the deliberately
  old-rulebook fixture remains unavailable.

- [ ] **Step 4: Update docs to exact implemented behavior**

  Add a visible supersession note near the top of the 2026-08-15 plan linking
  this plan and the approved amendment design. Do not rewrite its completed
  historical tasks. After all code gates pass, update `FOCUS.md` and
  `ai-context/current-status.md` from “design/plan pending” to the tested
  implementation state; retain the explicit block that Task 7's former proof is
  pre-amendment and must be rerun before Tasks 8–9 or Validate Positions.

  Confirm the amendment design still states: min-n five for both horizons;
  ADX 17/20 monitoring-only; no V3 PSR; default permutation-only; checkbox-on
  paired DSR 0.90/0.85; no migration/fallback for old V3 artifacts.

- [ ] **Step 5: Run complete focused V3 verification**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_rulebook_config tests.test_backtest_contracts tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_trade_execution tests.test_backtest_rolling_window tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_diagnostics tests.test_backtest_signal_catalog tests.test_backtest_validation_advice tests.test_backtest_early_warning tests.test_backtest_page -v
  docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py
  ```

  Expected: all selected tests pass and compilation emits no project error.
  Do not run a Collect/backfill or alter existing result artifacts as part of
  this implementation. The amended Task 7 manual proof remains a separate,
  user-visible next gate.

- [ ] **Step 6: Record completion without Git**

  Mark this task complete in this plan and report the exact test count. Do not
  execute any Git command.

## Coverage self-review

- Entry gates, ADX 17/20, and `n >= 5`: Task 1.
- PSR removal, no-theme permutation metadata, paired DSR math/cutoffs, and
  nullable artifact score: Task 2.
- Checkbox execution, paired-source failure, diagnostics, and user-facing
  certification label: Task 3.
- Existing V3 artifact invalidation, downstream readers, docs, full regression
  gate, and Task 7/backlog order: Task 4.
- No database schema, price scaling, dependencies, V2 fallback, research
  optimizer, or Git operations appear in any task.
