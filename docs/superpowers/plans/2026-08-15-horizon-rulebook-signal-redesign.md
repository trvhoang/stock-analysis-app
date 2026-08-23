# Horizon Rulebook Signal Redesign Implementation Plan

> **Active-policy amendment:** This plan is the historical original V3 plan.
> Its entry-gate, ADX, `min_n`, PSR, and DSR rules are superseded by
> [2026-08-21 Horizon Rulebook V3 Gate and Statistics Update](2026-08-21-horizon-rulebook-v3-gate-statistics-update.md).
> Execute that amendment completely, including its Task 7 rerun gate, before
> starting the queued Validate Positions plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three compact indicator strategies and V2 current artifacts
with one causal Swing rulebook and one causal Mid-term rulebook. V3 is the
only current artifact format; user-triggered Backtest runs create it, with one
explicit bulk V3 backfill allowed only after the V3 proof gate and before V2
deletion. Keep PSR/DSR, existing position history, and long-only risk execution
truthful.

**Architecture:** A horizon-owned `RulebookSpec` supplies every indicator,
entry gate, holding rule, and certification minimum. Rulebook entry evaluation
is a causal Boolean trigger: RSI upcross plus shared MA/Alligator joint trend
confirmation,
prior-only volume gate, hard ADX, and optional VN-Index AND eligibility. For
each requested ticker/horizon, a no-theme request executes only no-theme and
uses a one-trial PSR; a themed request also executes the themed treatment and
uses the two-treatment DSR only for that themed result. Persistence writes
schema-V3 horizon-qualified artifacts with fresh audit provenance. All current
readers use V3 only and ignore V2 completely; frozen position snapshots remain
readable without an artifact lookup.

**Tech Stack:** Python 3.12, pandas, NumPy, pandas-ta, SQLAlchemy/PostgreSQL,
Streamlit, existing Docker unittest suite.

## Global Constraints

- Do not commit, amend, reset, stash, or otherwise modify Git history; the
  user manages commits.
- Do not modify `app/common_queries.py`, `app/data_preparation.py`, `.env`,
  Docker files, credentials, BIGINT storage, or dependencies.
- Continue using `get_engine_with_retry()`, `engine.raw_connection()`,
  `sqlalchemy.text()`, and `%(name)s` binding for every database read.
- Keep raw BIGINT prices through indicator, entry, ATR, exit, and certification
  calculations. UI output alone uses the shared display conversion.
- Keep all rules long-only. One rulebook skips later entry signals while an
  earlier trade is open; every completed event is one BUY followed by one SELL.
- Swing is daily with a three-completed-session exit delay and an inclusive
  22-bar timeout. Mid-term is weekly only with a one-weekly-bar exit delay and
  an inclusive 16-bar timeout.
- V3 emits no VN-Index OR treatment. Theme is always `AND` when present.
- Certification uses `n >= 22` for Swing and `n >= 20` for Mid-term, current
  permutation alpha, PSR with `trial_count: 1` for no-theme, and the
  no-theme/AND two-treatment DSR family only for a themed result.
- V2 artifacts have no reader, fallback, conversion, warning, or maintenance
  path. They are not deleted during implementation. After all V3 gates pass
  and a user-triggered Backtest proves one nonempty valid V3 result, the user
  may explicitly start a bulk V3 backfill from legacy **filenames only**. Delete
  V2 only after every requested V3 document exists and the user separately
  approves the exact one-off deletion.
- Do not begin `2026-08-16-validate-positions-risk-and-trade-rows.md` Phase A
  until this entire plan closes Tasks 0--9 in order. V3-only persistence and
  replay/UI cutover are necessary but insufficient; manual V3 proof,
  backfill/tracker completion, and Task 9 V2 cleanup after separate deletion
  approval are also required.
- Existing position snapshots remain immutable historical records and must not
  resolve a V2 artifact.
- Tests use the repository's installed `unittest` framework only. Every test
  snippet is a method on a named `unittest.TestCase`, uses
  `unittest.mock.patch`, and is verified against Streamlit 1.32's actual
  `AppTest` collections (for example `app.markdown[index].value`) before it
  becomes a locked assertion. Do not add pytest or its `mocker` fixture.
  Tests that need a filesystem inherit a small local `TemporaryDirectory`
  `setUp`/`tearDown` base and use `self.tmp_path`; they never use pytest's
  `tmp_path` fixture.

```python
import unittest
from math import sqrt
from pathlib import Path
from statistics import NormalDist
from tempfile import TemporaryDirectory
from unittest.mock import patch


class BacktestTempDirCase(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = TemporaryDirectory()
        self.tmp_path = Path(self._temporary_directory.name)

    def tearDown(self):
        self._temporary_directory.cleanup()
```

Every `def test_...` below is a method to add to the named existing
`unittest.TestCase` (or `BacktestTempDirCase` when it uses `self.tmp_path`),
not a module-level pytest-style test.
- Every task follows DO / CHECK / ACT: prove RED, implement the smallest GREEN
  change, run its focused Docker gate, self-review, and then update `FOCUS.md`
  and `ai-context/current-status.md` truthfully.

## File Map

| File | Responsibility |
|---|---|
| `app/backtest_engine/config.py` | Add immutable horizon rulebook specifications and rule-owned `min_n`/hold values. |
| `app/backtest_engine/models.py` | Represent one V3 rulebook/treatment execution without accepting old compact IDs as new output. |
| `app/backtest_engine/indicators.py` | Build horizon-specific EMA/SMA, RSI, causal Alligator, volume, and ADX inputs. |
| `app/backtest_engine/signal_combos.py` | Replace compact score-cross strategy generation with one rulebook entry trigger per treatment. |
| `app/backtest_engine/rolling_window.py` | Enforce one-open-trade sequencing while retaining proven raw-ATR exits. |
| `app/backtest_engine/validation.py`, `certify.py` | Validate no-theme with one-trial PSR and themed candidates with two-treatment DSR; serialize their explicit significance method. |
| `app/backtest_engine/data_quality.py`, `universe_audit.py`, `pipeline.py`, `diagnostics.py` | Audit the literal frozen roster from its temporary work-item data file before rulebook work, calculate fresh V3 audit eligibility, use derived OHLC only for ordering-only normal runs, execute only requested treatments, and repair stale diagnostics imports/signatures. |
| `app/backtest_engine/persistence.py` | Add V3 horizon-qualified atomic documents, fresh audit metadata, and intentional empty/failure-result markers. |
| `app/backtest_engine/v3_backfill.py`, `scripts/backfill_v3_artifacts.py` | Run the explicit post-proof CLI legacy-filename inventory, full V3 backfill tracker, and terminal report; never parse a V2 payload. |
| `app/backtest_engine/signal_catalog.py`, `result_store.py`, `early_warning.py` | Discover/read V3 only; ignore V2 completely. |
| `app/backtest_engine/validation_advice.py`, `position_identity.py`, `position_store.py` | Replay V3 rulebooks; retain frozen position snapshots without artifact lookup. |
| `app/pages/backtest_lab.py` | Render one rulebook result per horizon/treatment and label PSR or DSR truthfully. |
| `tests/test_backtest_*.py` | Focused RED/GREEN coverage for each contract below. |
| `docs/superpowers/reports/...` | Record no-write multi-ticker evidence, V3 proof, bulk-backfill terminal report, and later deletion-permission gate. |

---

## V3-only Cutover Matrix

| Area | Required V3 behavior | Required V2 handling |
|---|---|---|
| Rule execution | `RulebookExecution` and Boolean entry gates are the only new-run model. | Delete compact strategy IDs, score-crossing replay, and legacy artifact-score branches. |
| Job protocol | Batch config emits and worker accepts `backtest_batch_v3` only; the distinct post-proof bulk command executes V3 jobs. | Reject V2 requests; retain historical status JSON untouched but never execute it. |
| Artifact/root | Schema-3 horizon-qualified documents are the only files current code discovers, parses, renders, downloads, or uses for Group `N/A`. | Remove root migration/recovery; only the post-proof backfill scans filenames to create its target manifest. |
| Certification metadata | Persist rulebook, one all-metrics signal set, exactly one terminal state (`success`/`empty`/`failed`), explicit PSR/DSR metadata, three named date ranges, and freshly calculated `audit_eligibility`. | Never infer, convert, or surface V2 metadata. |
| Validate UI | Partition results and widget identity by ticker, horizon, and theme; use the V3 monitoring-only, gate-weighted match readout. | Never calculate score/threshold match, advice, or details from a V2 document. |
| Current Positions | New saved-set positions use one frozen V3 `(ticker, horizon, theme, rulebook, metric-group)` reference. | Existing pre-V3 records are P&L/manual-management history only, never a signal source or monitor input. |
| Tests/docs | Replace V2 positive tests with V3 contracts and V2-ignore/reject fixtures. | Archived documents stay historical only; no active doc may describe V2 as supported behavior. |

---

### Task 0: Restore Diagnostics and Pass the Frozen-Roster Audit Gate

**Files:**

- Modify: `app/backtest_engine/diagnostics.py`,
  `app/backtest_engine/data_quality.py`, `app/backtest_engine/universe_audit.py`
- Create: `docs/superpowers/work-items/2026-08-15-v3-frozen-roster.json`
  (temporary input) and
  `docs/superpowers/reports/2026-08-15-v3-price-audit.md` (permanent evidence)
- Test: `tests/test_backtest_diagnostics.py`, `tests/test_backtest_data_quality.py`,
  `tests/test_backtest_universe_audit.py`

**Interfaces:**

- Consumes: `pipeline._requested_dates(config)`,
  `pipeline._build_confirmation_frame(vnindex, horizon)`, and
  `pipeline._theme_signal(frame, confirmation_frame)`.
- Produces: importable `collect_backtest_diagnostics()` that writes no database,
  job, or signal artifact state; a temporary literal roster input; and a
  permanent read-only audit report that repeats the locked roster and records
  separate `price_audit_clean` and `study_history_sufficient` booleans per
  ticker. The latter is true only when both native-history floors pass: at
  least five years of daily Swing history and eight years of closed `W-FRI`
  Mid-term history. The report includes both measured coverages.

- [x] **Step 1: Add the regression test.**

```python
class BacktestDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_uses_current_pipeline_date_and_theme_helpers(self):
        module = importlib.import_module("backtest_engine.diagnostics")
        with patch.object(module, "_requested_dates", return_value=(START, END)), \
             patch.object(module, "_build_confirmation_frame", return_value=CONFIRMATION), \
             patch.object(module, "_theme_signal", return_value=pd.Series([True])) as theme_signal:
            module.collect_backtest_diagnostics(THEMED_CONFIG, ENGINE)
        theme_signal.assert_called_once()

    def test_roster_audit_keeps_cleanliness_separate_from_history_coverage(self):
        report = audit_frozen_roster(FROZEN_ROSTER, ENGINE)
        self.assertEqual(tuple(item["ticker"] for item in report), FROZEN_ROSTER)
        self.assertTrue(all({"price_audit_clean", "study_history_sufficient",
                             "swing_history_years", "midterm_history_years"} <= set(item)
                            for item in report))
        self.assertEqual(
            report[0]["study_history_sufficient"],
            report[0]["swing_history_years"] >= 5
            and report[0]["midterm_history_years"] >= 8,
        )
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_diagnostics -v`

Expected: import fails because `diagnostics.py` imports removed
`pipeline._default_dates`; no frozen-roster audit contract exists.

- [x] **Step 3: Make the smallest repair.**

```python
from .pipeline import _build_confirmation_frame, _requested_dates, _theme_signal

# use _requested_dates(config)
confirmation_frame = _build_confirmation_frame(vnindex, config.horizon)
theme_signal = _theme_signal(frame, confirmation_frame)

# docs/superpowers/work-items/2026-08-15-v3-frozen-roster.json
{"tickers": ["VCB", "REE", "FPT", "SSI", "VIC", "PLX", "DHG", "HPG"]}
```

- [x] **Step 4: Run GREEN and prove no-write behavior.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_diagnostics -v`

Expected: diagnostic imports, focused no-write assertions pass, and the
permanent audit report lists every roster ticker with both booleans and its
daily/weekly coverage values. Do not start Task 1 until this report exists;
research later excludes every non-clean or history-insufficient ticker without
changing normal UI availability.

- [x] **Step 5: Self-review.** Confirm no pipeline, persistence, database, or
  artifact behavior changed in this task.

---

### Task 1: Encode the Immutable Horizon Rulebooks

**Files:**

- Modify: `app/backtest_engine/config.py`, `app/backtest_engine/models.py`
- Test: `tests/test_backtest_rulebook_config.py` (new)

**Interfaces:**

- Produces `RulebookSpec` and `rulebook_for(horizon) -> RulebookSpec`.
- Each spec exposes `rule_id`, native timeframe, MA type/pair, RSI period and
  upcross level, Alligator periods/lags, volume window/multiplier, ADX minimum,
  joint-trend requirement, minimum/maximum hold bars, and `min_n`.
- `RulebookExecution` identifies `(rule_id, horizon, theme_variant,
  theme_mode="AND"|None)` and is the only new-run candidate identity.
  Its rule-owned `min_n`, hold clock, and indicator periods cannot be caller
  overrides. `BacktestConfig`/`BacktestBatchConfig` retain no `min_n`,
  `max_hold_bars`, compact threshold, or compact strategy override.

- [x] **Step 1: Write exact configuration tests.**

```python
def test_swing_rulebook_is_the_approved_daily_contract(self):
    rule = rulebook_for("swing")
    assert rule.rule_id == "swing_rulebook_v3"
    assert (rule.ma_kind, rule.ma_pair) == ("EMA", (5, 13))
    assert (rule.rsi_period, rule.rsi_upcross) == (9, 52)
    assert (rule.volume_window, rule.volume_multiplier) == (10, 1.3)
    assert rule.min_n == 22 and rule.max_hold_bars == 22

def test_midterm_rulebook_is_weekly_and_never_or_themed(self):
    rule = rulebook_for("midterm")
    assert (rule.ma_kind, rule.ma_pair) == ("SMA", (8, 21))
    assert (rule.rsi_period, rule.rsi_upcross) == (14, 70)
    assert (rule.volume_window, rule.volume_multiplier) == (8, 1.5)
    assert rule.adx_minimum == 25 and rule.min_n == 20
    with self.assertRaisesRegex(ValueError, "AND"):
        RulebookExecution(rule, theme_variant="background-theme", theme_mode="OR")
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_rulebook_config -v`

Expected: missing `RulebookSpec`, `rulebook_for`, and `RulebookExecution`.

- [x] **Step 3: Add the minimal frozen rulebook registry and remove old
  identities.** Delete `COMPACT_STRATEGY_IDS`,
  `COMPACT_STRATEGY_INDICATORS`, old threshold-grid configuration, and the
  `IndicatorCombo.strategy_id` validation branch. Do not introduce grids,
  user-tunable rule parameters, or a default that permits `OR`. Change both
  direct and batch worker payloads to V3 request types; direct one-ticker work
  uses `backtest_single_v3` but delegates internally to the same batch-of-one
  V3 execution service.

- [x] **Step 4: Run GREEN.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_rulebook_config tests.test_backtest_contracts -v`

Expected: exact values and long-only/themed validation pass.

- [x] **Step 5: Self-review.** Verify a caller cannot override one horizon's
  `min_n`, hold clock, or indicator period into the other horizon, and no
  compact strategy identifier remains a valid new-run model.

---

### Task 2: Build Causal Rulebook Inputs and Entry Gates

**Files:**

- Modify: `app/backtest_engine/indicators.py`, `app/backtest_engine/signal_combos.py`
- Test: `tests/test_backtest_indicators.py`,
  `tests/test_backtest_signal_combos.py`

**Interfaces:**

- Produces `build_rulebook_frame(ohlcv, rulebook)` with native bars and named
  rulebook columns.
- Produces the shared `joint_trend_pass(ma_point, alligator_point) -> bool`
  predicate and a matching frame column; entry and monitoring both use this
  one predicate.
- Produces `rulebook_entry_signal(frame, execution, theme_eligible=None) -> pd.Series[bool]`.
- The signal is `rsi_upcross & joint_trend_pass & volume_gate & adx_gate`,
  then VN-Index AND when themed.

- [x] **Step 1: Add daily and weekly indicator fixture tests.**

```python
def test_volume_gate_excludes_the_current_bar_from_its_baseline(self):
    frame = build_rulebook_frame(DAILY_OHLCV, rulebook_for("swing"))
    assert frame.loc[10, "rulebook_volume_baseline"] == DAILY_OHLCV.loc[:9, "volume"].mean()
    assert bool(frame.loc[10, "rulebook_volume_gate"]) is True

def test_rsi_upcross_is_an_event_not_a_persistent_bullish_label(self):
    values = pd.Series([51.9, 52.0, 55.0])
    assert rsi_upcross(values, 52).tolist() == [False, True, False]

def test_future_rows_cannot_change_prior_swing_or_weekly_rulebook_values(self):
    assert_frame_equal(before.loc[:CUT], after_mutating_future.loc[:CUT])
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_indicators tests.test_backtest_signal_combos -v`

Expected: failing tests for EMA 5/13, SMA 8/21, RSI event columns,
prior-only volume, and rulebook entry predicates.

- [x] **Step 3: Implement only Backtest-owned pure calculations.**
  `backtest_engine/indicators.py` imports no Analyze module or helper. Build
  EMA/SMA, RSI, SMMA Alligator, ATR, ADX, and prior-only volume values locally
  from raw BIGINT OHLCV; do not change live Analyze behaviour. MA has no 2%
  sideways rule. Create named `required_input` and
  `missing_required_input = required_input.isna().any(axis=1)` (including an
  explicit non-finite check) before the entry AND chain. Assign false to each
  missing-input row before combining gates; missing/non-finite MA, Alligator,
  RSI, volume baseline, ADX, or ATR may never rely on pandas comparison
  side-effects. Resample Mid-term as `W-FRI` and drop the final labelled bar
  when Asia/Ho_Chi_Minh today is on or before its Friday label. A Thursday-last
  trading week remains valid after that Friday label has passed. Implement the
  shared `joint_trend_pass(ma_point, alligator_point)` predicate from strict
  Backtest-owned labels (`Down = 1`, `Sideways = 2`, `Up = 3`). It returns true
  only when both points are at least `3`. Do not calculate an average, a
  percentage bucket, or an inherited Analyze strong/weak label for V3.

- [x] **Step 4: Add entry composition tests.**

```python
def test_entry_requires_every_gate_and_theme_is_additional_and(self):
    assert rulebook_entry_signal(frame_with_all_gates, no_theme).iloc[-1]
    assert not rulebook_entry_signal(frame_without_volume, no_theme).iloc[-1]
    assert not rulebook_entry_signal(frame_with_all_gates, themed_false).iloc[-1]
    assert rulebook_entry_signal(frame_with_all_gates, themed_true).iloc[-1]

def test_missing_required_indicator_is_explicitly_not_an_entry(self):
    frame = frame_with_all_gates.copy()
    frame.loc[frame.index[-1], "rulebook_alligator_jaw"] = float("nan")
    self.assertFalse(bool(rulebook_entry_signal(frame, NO_THEME).iloc[-1]))

def test_joint_trend_requires_both_rulebook_indicators_to_be_up(self):
    for ma_point, alligator_point, expected_entry in (
        (3, 2, False),  # Up + Sideways
        (1, 3, False),  # Down + Up
        (3, 3, True),   # Up + Up
    ):
        with self.subTest(ma_point=ma_point, alligator_point=alligator_point):
            frame = frame_with_all_gates.copy()
            frame.loc[frame.index[-1], "rulebook_joint_trend_pass"] = joint_trend_pass(
                ma_point, alligator_point
            )
            self.assertEqual(
                bool(rulebook_entry_signal(frame, NO_THEME).iloc[-1]), expected_entry
            )

def test_midterm_holiday_short_week_boundary_uses_w_fri_label(self):
    for today, expected_last_date in (
        (THURSDAY, PRIOR_FRIDAY),
        (FRIDAY, PRIOR_FRIDAY),
        (SATURDAY, HOLIDAY_WEEK_FRIDAY_LABEL),
        (FOLLOWING_MONDAY, HOLIDAY_WEEK_FRIDAY_LABEL),
    ):
        with self.subTest(today=today):
            weekly = build_rulebook_frame(
                DAILY_THROUGH_HOLIDAY_WEDNESDAY, MIDTERM_RULE, today=today
            )
            self.assertEqual(weekly["date"].max().date(), expected_last_date)
```

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_indicators tests.test_backtest_signal_combos -v`

Expected: all fixtures, no-look-ahead, and AND-only tests pass. Verify volume
is absent from every directional scoring helper.

---

### Task 3: Execute One Flat-to-Flat Trade Sequence per Rulebook

**Files:**

- Modify: `app/backtest_engine/rolling_window.py`,
  `app/backtest_engine/signal_combos.py`
- Test: `tests/test_backtest_trade_execution.py`,
  `tests/test_backtest_rolling_window.py`

**Interfaces:**

- Consumes: one Boolean entry series from Task 2 and Backtest-owned raw-ATR
  exit helpers.
- Produces: chronological non-overlapping `TradeEvent` records.

- [x] **Step 1: Add the non-overlap RED fixture.**

```python
def test_second_entry_is_ignored_until_first_rulebook_trade_is_closed(self):
    events = run_rulebook_trade_sequence(frame_with_two_entries_before_timeout, execution)
    assert [(event.entry_date, event.exit_date) for event in events] == [
        (DATE_1_OPEN, DATE_1_TIMEOUT),
    ]
```

- [x] **Step 2: Add exact horizon-clock tests.**

```python
def test_swing_timeout_is_inclusive_at_bar_twenty_two(self):
    assert event.exit_date == daily_frame.loc[entry_position + 21, "date"]

def test_midterm_exit_can_first_fire_on_next_weekly_bar(self):
    assert event.exit_date == weekly_frame.loc[entry_position + 1, "date"]
```

- [x] **Step 3: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_trade_execution tests.test_backtest_rolling_window -v`

Expected: current loop opens each crossing independently and uses old hold
defaults.

- [x] **Step 4: Implement a single explicit position-state loop.** Advance to
  the next eligible entry only after the selected SL, TP, or timeout exit.
  Reuse current conservative same-bar stop-first behavior and raw ATR levels;
  do not add optimistic gap fills or fees in this task. Replace score-based
  crossing calls with the Task 2 Boolean entry series, then delete
  `score_combo`, `detect_buy_crossings`, and legacy-artifact score replay.
  Preserve `TradeEvent` raw-BIGINT values and give its V3 serializer separate
  signal, effective-data, and event-range sources rather than one ambiguous
  `date_range`.

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_trade_execution tests.test_backtest_rolling_window -v`

Expected: golden daily/weekly traces, non-overlap, minimum holds, and inclusive
timeouts pass.

---

### Task 4: Use One-trial PSR for No-theme and DSR Only for Themed Results

**Files:**

- Modify: `app/backtest_engine/validation.py`, `app/backtest_engine/certify.py`,
  `app/backtest_engine/pipeline.py`, `app/backtest_engine/diagnostics.py`
- Test: `tests/test_backtest_validation.py`,
  `tests/test_backtest_certification.py`, `tests/test_backtest_pipeline.py`,
  `tests/test_backtest_diagnostics.py`

**Interfaces:**

- `calculate_probabilistic_sharpe(returns, expected_sharpe=0.0) -> float`
  implements the exact locked PSR formula and rejects insufficient/non-finite
  inputs or a non-positive denominator. It uses sample skew and **Pearson**
  kurtosis (`pandas` Fisher kurtosis plus 3), then calculates
  `NormalDist().cdf((SR - 0) * sqrt(n - 1) / sqrt(1 - skew * SR +
  ((kurtosis - 1) / 4) * SR**2))`; `trial_count` is exactly one.
- `validate_rulebook_treatments(no_theme_events, themed_events, rulebook,
  include_theme)` validates no-theme with its single Sharpe/PSR and validates a
  requested themed result against the exact two-observed-Sharpe DSR family. A
  missing or too-thin no-theme companion produces the explicit themed-only
  terminal `empty` rejection `missing required no-theme DSR companion`.
- `certify_rulebook_result(candidate)` returns zero or one V3-ready signal set
  whose `metrics` are registry ordered and whose `significance_method`,
  `significance_score`, and `trial_count` are explicit.
- Pipeline does not load/build VN-Index confirmation when `include_theme` is
  false. When it is true, no-theme remains a PSR result and themed is a
  two-trial DSR result; both requested artifacts persist.

- [x] **Step 1: Write DSR-family RED tests.**

```python
def test_no_theme_candidate_is_a_genuine_one_trial_psr_without_theme_execution(self):
    result = validate_rulebook_treatments(NO_THEME_EVENTS, None, SWING_RULE, include_theme=False)
    assert result["no-background-theme"].significance_method == "psr"
    assert result["no-background-theme"].trial_count == 1

def test_psr_uses_the_locked_zero_benchmark_and_pearson_kurtosis(self):
    score = calculate_probabilistic_sharpe(RETURNS)
    expected = NormalDist().cdf(
        (sample_sharpe(RETURNS) - 0.0) * sqrt(len(RETURNS) - 1)
        / sqrt(1 - sample_skew(RETURNS) * sample_sharpe(RETURNS)
               + ((sample_pearson_kurtosis(RETURNS) - 1) / 4) * sample_sharpe(RETURNS) ** 2)
    )
    self.assertAlmostEqual(score, expected)

def test_themed_candidate_uses_exact_two_treatment_dsr_family(self):
    result = validate_rulebook_treatments(NO_THEME_EVENTS, THEMED_EVENTS, SWING_RULE, include_theme=True)
    assert result["no-background-theme"].trial_count == 1
    assert result["background-theme"].significance_method == "dsr"
    assert result["background-theme"].trial_count == 2

def test_missing_theme_companion_refuses_only_themed_certification(self):
    result = validate_rulebook_treatments(NO_THEME_EVENTS, None, SWING_RULE, include_theme=True)
    self.assertEqual(result["no-background-theme"].terminal_state, "success")
    self.assertEqual(result["background-theme"].terminal_state, "empty")
    self.assertEqual(result["background-theme"].rejection_reason,
                     "missing required no-theme DSR companion")

def test_single_qualified_rulebook_serializes_one_all_metrics_result(self):
    assert certified["metrics"] == ["win_rate", "profit", "sharpe"]
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_pipeline -v`

Expected: current code requires at least two trial Sharpes and evaluates compact
strategies rather than explicit one-trial PSR and treatment-specific DSR.

- [x] **Step 3: Implement treatment-owned statistics without mixing horizons.**
  A no-theme-only request runs no-theme only and calculates PSR with expected
  maximum Sharpe zero and `trial_count: 1`; it has no VN-Index preflight,
  computation, status message, or hidden artifact. A themed request runs both
  treatments in the same ticker/horizon: no-theme persists PSR, and themed uses
  their two Sharpe values for DSR with `trial_count: 2`. A companion without a
  finite observed Sharpe writes only the themed treatment as terminal `empty`
  with `rejection_reason: "missing required no-theme DSR companion"`; it never
  fabricates a second trial or blocks a no-theme PSR result. Apply the same
  `0.95` score cutoff and then the same seeded moving-block permutation stage
  to both methods.

- [x] **Step 4: Add per-horizon minimum tests.**

```python
def test_swing_requires_twenty_two_and_midterm_requires_twenty(self):
    assert reject(SWING_EVENTS_21, SWING_RULE).rejection_reason == "min_n"
    assert accept(SWING_EVENTS_22, SWING_RULE).n == 22
    assert reject(MIDTERM_EVENTS_19, MIDTERM_RULE).rejection_reason == "min_n"
    assert accept(MIDTERM_EVENTS_20, MIDTERM_RULE).n == 20
```

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_pipeline tests.test_backtest_diagnostics -v`

Expected: no-theme has exactly one PSR trial; themed DSR has exactly two trials;
persistence labels both methods explicitly; and no daily/weekly return series
share a DSR family.

---

### Task 5: Introduce V3 Horizon-qualified Artifacts and Remove V2 Current-Artifact Support

**Files:**

- Modify: `app/backtest_engine/config.py`, `app/backtest_engine/worker.py`,
  `app/backtest_engine/job_runner.py`, `app/backtest_engine/persistence.py`,
  `app/backtest_engine/result_store.py`, `app/backtest_engine/signal_catalog.py`,
  `app/backtest_engine/early_warning.py`, `app/backtest_engine/data_quality.py`,
  `app/backtest_engine/pipeline.py`
- Test: `tests/test_backtest_persistence.py`,
  `tests/test_backtest_signal_catalog.py`, `tests/test_backtest_result_store.py` (new),
  `tests/test_backtest_early_warning.py`, `tests/test_backtest_worker.py`,
  `tests/test_backtest_pipeline.py`

**Interfaces:**

- `signal_artifact_path(ticker, horizon, theme_variant, output_dir) -> Path`
  resolves only V3 paths.
- `save_rulebook_result(...)` atomically writes one V3 terminal document with
  exactly one `terminal_state` of `success`, `empty`, or `failed`. It always
  contains `requested_date_range`, `effective_data_range`, and
  `trade_event_range`, each shaped as `{start, end, reason}`. Unavailable
  ranges use paired null dates with their reason; no-trade completed runs use
  `{start: null, end: null, reason: "no trades generated"}` for the event
  range. Empty documents use a controlled `rejection_reason`; failed documents
  require `failure_reason` and never leave a stale result readable.
- `fresh_v3_audit_eligibility(raw_history, audit, effective_bounds)` records
  source `fresh_v3_raw_history`, the exact `clean`/`indeterminate`/`invalid`
  decision, warnings, reasons, and effective first/last dates; it accepts no
  artifact input. A pre-data terminal failure writes explicit
  audit-unavailable metadata instead.
- `load_rulebook_result(path)` accepts schema 3 only. V2 has no outcome,
  fallback, conversion, warning, or maintenance interface.
- `BacktestConfig.to_dict()` emits `request_type: "backtest_single_v3"` and
  internally delegates to V3 batch-of-one execution. `BacktestBatchConfig`
  emits `request_type: "backtest_batch_v3"`; the worker rejects missing, V2,
  and unknown explicit request types.
- The replacement result-root helper only creates/returns V3 and Group roots.
  It has no legacy directory argument, migration journal, recovery, or
  artifact-copy side effect.

- [x] **Step 1: Write V3-cutover boundary tests.**

```python
def test_swing_and_midterm_have_distinct_current_v3_paths(self):
    assert signal_artifact_path("VCB", "swing", "no-background-theme", self.tmp_path) != \
           signal_artifact_path("VCB", "midterm", "no-background-theme", self.tmp_path)

def test_empty_v3_marker_atomically_replaces_only_its_own_horizon_path(self):
    save_rulebook_result("VCB", SWING_EMPTY, self.tmp_path)
    assert load_rulebook_result(SWING_PATH)["empty"] is True
    assert not MIDTERM_PATH.exists()

def test_v2_is_ignored_by_current_catalog_and_readers(self):
    catalog = list_current_signal_set_rows(self.tmp_path)
    assert catalog["valid"] == []
    assert catalog["warnings"] == []

def test_worker_accepts_v3_and_rejects_a_retained_v2_request(self):
    assert _config_from_payload(V3_BATCH_PAYLOAD) == EXPECTED_CONFIG
    with self.assertRaisesRegex(ValueError, "not supported"):
        _config_from_payload(V2_BATCH_PAYLOAD)

def test_v3_calculates_audit_eligibility_from_its_fresh_raw_history(self):
    audit = audit_history("VCB", MATERIAL_OHLC_MISMATCH)
    metadata = fresh_v3_audit_eligibility(MATERIAL_OHLC_MISMATCH, audit, EFFECTIVE_BOUNDS)
    saved = save_rulebook_result("VCB", SWING_RESULT, self.tmp_path, audit_eligibility=metadata)
    audit = load_rulebook_result(saved)["audit_eligibility"]
    assert audit["source"] == "fresh_v3_raw_history"
    assert audit["status"] == "invalid"
    assert audit["eligible"] is False
    assert audit["effective_date_range"] == ["2012-01-03", "2026-08-14"]

def test_v3_indeterminate_discontinuity_stays_available_but_audit_ineligible(self):
    audit = audit_history("VCB", UNEXPLAINED_FIFTEEN_PERCENT_MOVE)
    metadata = fresh_v3_audit_eligibility(UNEXPLAINED_FIFTEEN_PERCENT_MOVE, audit, EFFECTIVE_BOUNDS)
    saved = save_rulebook_result("VCB", SWING_RESULT, self.tmp_path, audit_eligibility=metadata)
    audit = load_rulebook_result(saved)["audit_eligibility"]
    assert audit["status"] == "indeterminate"
    assert audit["eligible"] is False

def test_terminal_document_requires_consistent_state_reason_and_date_pairs(self):
    self.assertTrue(validate_rulebook_document(SUCCESS_DOCUMENT))
    self.assertTrue(validate_rulebook_document(
        EMPTY_DOCUMENT_WITH_NULL_EVENT_RANGE_AND_NO_TRADES_REASON
    ))
    self.assertTrue(validate_rulebook_document(FAILED_DOCUMENT_WITH_NULL_EFFECTIVE_AND_EVENT_RANGES))
    with self.assertRaisesRegex(ValueError, "terminal_state"):
        validate_rulebook_document(NONTERMINAL_DOCUMENT)
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_result_store tests.test_backtest_signal_catalog tests.test_backtest_early_warning tests.test_backtest_worker tests.test_backtest_pipeline -v`

Expected: current V2 theme-only paths collide across horizons; root reads can
migrate V2 files; current readers accept V2; and the worker accepts V2 batch
requests.

- [x] **Step 3: Implement the V3-only cutover.** Keep V2 physical files
  untouched, but remove V2 reader/fallback/deprecation-warning paths, the
  V2 root-migration journal/recovery/copy code, `LEGACY_SIGNAL_DIR`, and every
  migration side effect from group/catalog calls. Add V3 `empty` markers;
  catalog ignores empty and failed markers as saved signals but preserves their
  terminal state for truthful job/result status. Update `N/A` artifact discovery
  to count only readable nonempty V3 documents across both horizons. For every
  V3 execution, audit
  the freshly loaded raw DB history, persist the exact fresh status/reasons and
  actual effective bounds, and never accept audit metadata from an artifact.
  A terminal pre-data failure is explicitly audit-unavailable, never copied or
  fabricated. A structural invalidity fails the run; an ordering-only mismatch uses the
  existing derived OHLC envelope for the normal result while retaining
  audit-ineligible status; a >=15% discontinuity remains normal but
  indeterminate/audit-ineligible. A requested range longer than available DB
  history uses the actual full history without a coverage failure. Normal V3
  documents are created or replaced only by a user-triggered Backtest run for
  their ticker/horizon/theme. On every requested treatment, write exactly one
  terminal document: `success`, `empty`, or `failed` with reason. Switch both
  single and batch request protocols to V3 and make missing/V2 request payloads
  terminally unsupported. Preserve the Group move journal; remove only
  V2-specific root-migration hooks.

- [x] **Step 4: Add no-V2-support regression coverage.** Fixtures may place V2
  files in a temporary directory, but every current catalog, replay, and
  discovery call must ignore them without warnings, conversion, mutation, or
  fallback. A V2 status sidecar/output path must not reach a result reader or
  download control. Task 8 alone may enumerate V2 filenames after the proof
  gate; it must not parse their contents or become a product current-reader.

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_result_store tests.test_backtest_signal_catalog tests.test_backtest_early_warning tests.test_backtest_worker tests.test_backtest_pipeline -v`

Expected: V3 is horizon-isolated; V2 is ignored by current code; normal jobs
only create/replace the requested ticker's V3 artifact and never remove V2;
the worker accepts only the V3 request protocol; and result-root access has no
V2 migration side effect.

---

### Task 6: Preserve Position History and Update Replay/UI Consumers

**Files:**

- Modify: `app/backtest_engine/early_warning.py`,
  `app/backtest_engine/validation_advice.py`, `app/backtest_engine/signal_catalog.py`,
  `app/backtest_engine/position_identity.py`, `app/backtest_engine/position_store.py`,
  `app/backtest_engine/manual_position_store.py`,
  `app/backtest_engine/position_overview.py`, `app/pages/backtest_lab.py`
- Test: `tests/test_backtest_validation_advice.py`,
  `tests/test_backtest_position_store.py`, `tests/test_backtest_page.py`,
  `tests/test_backtest_position_monitor.py`, `tests/test_backtest_early_warning.py`

**Interfaces:**

- New V3 signal references include ticker, `rule_id`, horizon, treatment, and
  one frozen all-metrics snapshot. Their link key covers the complete
  `(ticker, horizon, theme_variant, rule_id, metrics)` identity, so exactly one
  OPEN position is permitted for that saved rulebook set.
- `validate_v3_position_snapshot(snapshot)` accepts only new
  `schema_version: 3` frozen references. The existing V2-shaped combo/metric
  validator accepts absent/`2` schema-version pre-V3 records read-only and is
  never used for a V3 write; an unknown explicit version is rejected. Current
  Positions labels those rows `Historical saved set` rather than exposing an
  old strategy ID.
- V3 replay returns independently addressable horizon results for each theme,
  with rulebook gate/match data rather than V2 `current_score` and
  `threshold_score_buy` fields. The current match is monitoring only. Each
  factor is the capped current-to-saved-rulebook-threshold ratio for RSI,
  current/prior-only volume ratio, ADX, and—only when themed—VN-Index close to
  its current theme SMA. Trend is instead exactly `1.0` when the shared
  `joint_trend_pass(ma_point, alligator_point)` predicate succeeds and `0.0`
  otherwise; it never uses an average bucket or a near-miss ratio. Themed Swing weights those
  factors at 15% each plus theme at 40%; themed Mid-term weights them at 20%
  each plus theme at 20%; either no-theme result redistributes to 25% per
  ticker factor with a zero theme share. Missing/non-finite numeric inputs, a
  negative factor input, or a non-positive required denominator make the
  monitoring readout unavailable. Its exclusive
  classes are Swing themed `No Match <=50`, `Weak >50 and <65`,
  `Nearly >=65 and <90`, `Closely >=90`; Swing no-theme `No Match <=50`,
  `Weak >50 and <65`, `Nearly >=65 and <80`, `Closely >=80`; Mid-term themed
  `No Match <=40`, `Weak >40 and <60`, `Nearly >=60 and <85`, `Closely >=85`;
  and Mid-term no-theme `No Match <=40`, `Weak >40 and <60`, `Nearly >=60 and
  <80`, `Closely >=80`. It must not alter rulebook entry,
  certification, DSR, or position-action eligibility.
- Existing pre-V3 position records use their frozen snapshots without an
  artifact lookup. They remain P&L/manual-management history only; they never
  receive Validate advice, a V3 monitor, BUY/SELL eligibility, or saved-set
  selection.
- Every Collect/Validate result, JSON/Markdown download, signal-choice label,
  Current Positions row, locator, edit confirmation, and widget key includes
  horizon. V3 rulebook/gate labels replace V2 strategy/score labels; Backtest
  performance shows artifact-owned `PSR` or `DSR` plus trial count, never a
  fixed V2 `Deflated Sharpe` label.

- [x] **Step 1: Write V3 replay and frozen-position RED tests.**

```python
def test_validate_lists_v3_swing_and_midterm_without_overwriting_either(self):
    result = validate_saved_signals("VCB", engine, signal_dir)
    self.assertEqual(
        {row["horizon"] for row in result["variants"]["no-background-theme"]["results"]},
        {"swing", "midterm"},
    )

def test_frozen_pre_v3_position_is_history_not_validate_signal_evidence(self):
    write_malformed_v2_artifact(v2_only_signal_dir)
    result = validate_saved_signals("VCB", engine, v2_only_signal_dir, positions_dir)
    self.assertEqual(result["historical_positions"][0]["signal_snapshot"], FROZEN_SNAPSHOT)
    self.assertEqual(result["variants"]["no-background-theme"]["availability"], "unavailable")

def test_v3_positions_of_one_ticker_theme_can_coexist_across_horizons(self):
    self.assertNotEqual(open_position_from(SWING_REFERENCE).id, open_position_from(MIDTERM_REFERENCE).id)

def test_position_snapshot_version_routes_only_to_its_own_validator(self):
    self.assertEqual(validate_position_snapshot(V3_SNAPSHOT), V3_REFERENCE)
    self.assertEqual(validate_position_snapshot(LEGACY_V2_SNAPSHOT), LEGACY_REFERENCE)
    with self.assertRaisesRegex(ValueError, "schema_version"):
        validate_position_snapshot(UNKNOWN_VERSION_SNAPSHOT)

def test_v3_monitoring_uses_joint_trend_and_horizon_weights(self):
    swing_current = {
        "rsi": 52.0, "ma_point": 3, "alligator_point": 3, "volume_ratio": 0.65,
        "adx_14": 10.0, "vnindex_close": 100.0, "vnindex_theme_sma": 100.0,
    }
    swing = monitoring_match_level("swing", "background-theme", swing_current, SWING_RULEBOOK)
    self.assertEqual(swing, (85.0, "nearly_match"))

    midterm_current = {
        "rsi": 70.0, "ma_point": 3, "alligator_point": 3, "volume_ratio": 0.0,
        "adx_14": 0.0, "vnindex_close": 100.0, "vnindex_theme_sma": 100.0,
    }
    midterm = monitoring_match_level("midterm", "background-theme", midterm_current, MIDTERM_RULEBOOK)
    self.assertEqual(midterm, (60.0, "nearly_match"))

def test_v3_monitoring_keeps_fractional_weak_and_no_theme_redistribution(self):
    weak_current = {
        "rsi": 70.0, "ma_point": 3, "alligator_point": 3, "volume_ratio": 0.15,
        "adx_14": 2.5, "vnindex_close": 30.0, "vnindex_theme_sma": 100.0,
    }
    self.assertEqual(
        monitoring_match_level("midterm", "background-theme", weak_current, MIDTERM_RULEBOOK),
        (50.0, "weak"),
    )

    no_theme_current = {
        "rsi": 52.0, "ma_point": 3, "alligator_point": 3, "volume_ratio": 1.3, "adx_14": 0.0,
    }
    self.assertEqual(
        monitoring_match_level("swing", "no-background-theme", no_theme_current, SWING_RULEBOOK),
        (75.0, "nearly_match"),
    )

def test_v3_monitoring_failed_joint_trend_cannot_be_closely_matched(self):
    cases = (
        ("swing", "background-theme", SWING_RULEBOOK, 85.0),
        ("swing", "no-background-theme", SWING_RULEBOOK, 75.0),
        ("midterm", "background-theme", MIDTERM_RULEBOOK, 80.0),
        ("midterm", "no-background-theme", MIDTERM_RULEBOOK, 75.0),
    )
    for ma_point, alligator_point in ((3, 2), (1, 3)):
        for horizon, theme_variant, rulebook, ceiling in cases:
            with self.subTest(
                ma_point=ma_point, alligator_point=alligator_point,
                horizon=horizon, theme_variant=theme_variant,
            ):
                current = {
                    "rsi": rulebook.rsi_upcross_level,
                    "ma_point": ma_point,
                    "alligator_point": alligator_point,
                    "volume_ratio": rulebook.volume_multiplier,
                    "adx_14": rulebook.adx_minimum,
                    "vnindex_close": 100.0,
                    "vnindex_theme_sma": 100.0,
                }
                self.assertEqual(
                    monitoring_match_level(horizon, theme_variant, current, rulebook),
                    (ceiling, "nearly_match"),
                )

def test_v3_monitoring_is_unavailable_for_missing_or_invalid_required_values(self):
    self.assertIsNone(
        monitoring_match_level("swing", "background-theme", {"rsi": 52.0}, SWING_RULEBOOK)
    )
```

- [x] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_page tests.test_backtest_early_warning -v`

Expected: replay assumes a single V2 ticker/theme document and metric-keyed
current candidates.

- [x] **Step 3: Implement V3-only consumer paths.** Replace V2
  `IndicatorCombo`/score replay in `early_warning` and `validation_advice` with
  the V3 rulebook replay contract. Implement one pure
  `monitoring_match_level(horizon, theme_variant, current, rulebook)` helper.
  It calculates capped fractional strength from current numeric values against
  the saved rulebook thresholds: RSI/upcross, volume-ratio/multiplier,
  ADX/minimum, and themed VN-Index close/theme-SMA. It imports and invokes the
  same `joint_trend_pass(ma_point, alligator_point)` helper that entry uses,
  mapping its result to trend strength `1.0` or `0.0`; do not duplicate the
  condition or create a bucket/percentage substitute. A failed joint trend is
  intentionally zero rather than a capped classification override, so the
  displayed percentage and class remain consistent.
  It returns unavailable for missing/non-finite inputs, negative factor inputs,
  or non-positive required denominators; otherwise it returns the weighted
  percentage and exact stable class `no_match`, `weak`, `nearly_match`, or
  `closely_match`. The no-theme branch has four 25% ticker factors and does not
  require VN-Index inputs. Add a regression where all fractional strengths are
  100% but the RSI is not a new upcross, and another where VN-Index close equals
  its SMA: both retain their monitor readout but fail their literal entry gate.
  Add the four-treatment ceiling regression: when joint trend fails and every
  other factor is 100%, `85/75/80/75` are `nearly_match`, never `closely_match`.
  Do not call `match_level(current_score, threshold_score_buy)`, and do not
  feed the monitoring result into entry, certification, DSR, or position-action
  eligibility. Validate groups each theme title by horizon, with no-theme
  first. View Signals lists one row per V3 ticker/horizon/theme rulebook.
  Render/download only schema-3 job output, including `audit_eligibility`; V2
  output paths are ignored. Reuse the generic/manual position store for new V3
  saved-set records rather than the metric-file legacy store. Keep pre-V3
  position rows available only as P&L/manual-management history. No consumer
  resolves, labels, or maintains V2 artifacts. Add
  `validate_v3_position_snapshot()` rather than extending the legacy validator:
  new references include `schema_version: 3`; legacy snapshots with absent or
  `2` schema version route only to the old read-only validator, while unknown
  explicit versions are rejected.

- [x] **Step 4: Add UI contract tests.**

```python
def test_validate_uses_distinct_widget_identity_for_two_horizons_of_one_theme(self):
    app.run()
    assert [item.label for item in app.expander].count("Swing — No theme") == 1
    assert [item.label for item in app.expander].count("Mid-term — No theme") == 1

def test_validate_can_filter_the_new_weak_monitoring_classification(self):
    app.run()
    assert "Weak" in app.multiselect(key="backtest_validate_match_classifications_v3").options

def test_v3_backtest_performance_labels_psr_and_dsr_by_artifact_method(self):
    app.run()
    markdown_values = [str(item.value) for item in app.markdown]
    self.assertTrue(any("PSR" in value for value in markdown_values))
    self.assertTrue(any("DSR" in value for value in markdown_values))
    self.assertFalse(any("Deflated Sharpe" in value for value in markdown_values))

def test_current_positions_saved_set_label_includes_horizon(self):
    app.run()
    assert "Swing" in app.dataframe[0].value["Saved signal set"].iloc[0]
```

- [x] **Step 5: Run GREEN and self-review.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_position_monitor tests.test_backtest_page tests.test_backtest_early_warning -v`

Expected: V3 replay/UI/downloads work independently per horizon/theme; every
new saved-set position has one horizon-qualified rulebook identity; frozen
pre-V3 history remains manually manageable without becoming V2 signal evidence;
and no widget collides when a ticker has both V3 horizons.

---

### Task 7: Multi-ticker Evidence, Performance Review, and Documentation

**Files:**

- Modify: `app/backtest_engine/diagnostics.py`, `FOCUS.md`,
  `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-15-horizon-rulebook-signal-redesign-verification.md`
- Test: `tests/test_backtest_diagnostics.py` and all focused Backtest tests.

- [x] **Step 1: Add a read-only evidence test.**

```python
def test_rulebook_diagnostic_declares_v3_rules_and_no_write_boundary(self):
    report = collect_rulebook_diagnostics(THEMED_CONFIG, engine)
    assert report["write_boundary"] == {"database": False, "jobs": False, "artifacts": False}
    assert report["trial_family"] == ["no-background-theme", "background-theme:AND"]

def test_no_theme_diagnostic_has_one_psr_trial_and_no_theme_preflight(self):
    report = collect_rulebook_diagnostics(NO_THEME_CONFIG, engine)
    assert report["trial_family"] == ["no-background-theme"]
    assert report["statistical_method"] == "psr"

def test_v2_files_and_status_paths_are_not_v3_evidence_sources(self):
    write_valid_v2_artifact_and_terminal_status(self.tmp_path)
    assert list_current_signal_set_rows(self.tmp_path)["valid"] == []
    assert renderable_v3_output_paths(read_status(self.tmp_path)) == ()
```

- [x] **Step 2: Run RED and implement the smallest report extension.** Read the
  Task 0 literal roster/report; do not dynamically select eight clean tickers.
  Include only tickers whose independently recorded `price_audit_clean` and
  `study_history_sufficient` are both true in aggregate study conclusions.
  The report records inputs, both booleans, coverage, entries rejected by each
  gate (including joint-trend rejection), non-overlap skips, exits, and `n`
  independently per ticker/horizon before certification, plus PSR/DSR/p-value
  and calibration/holdout metrics. It reports excluded tickers transparently
  and does not inspect or maintain V2 artifacts. It must include this scope
  statement verbatim:
  `Roster was selected for long observed histories and blue-chip liquidity; it
  is not evidence of edge or generalization across thin or small-cap names.`

- [x] **Step 3: Run full focused verification in Docker.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_data_quality tests.test_backtest_rulebook_config tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_trade_execution tests.test_backtest_rolling_window tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence tests.test_backtest_result_store tests.test_backtest_signal_catalog tests.test_backtest_pipeline tests.test_backtest_worker tests.test_backtest_diagnostics tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_position_monitor tests.test_backtest_page tests.test_backtest_early_warning -v`

Expected: every focused test passes. Investigate any failure before proceeding;
do not weaken a test or adjust rule values to force qualification.

- [x] **Step 4: Run static and live-safe checks.**

Run:

```text
docker exec stock_app python -m compileall backtest_engine pages/backtest_lab.py
git diff --check
docker exec stock_app python -c "from backtest_engine.diagnostics import collect_rulebook_diagnostics; print('import ok')"
```

Expected: compilation and whitespace pass; diagnostic imports. Run the
read-only multi-ticker report only after focused tests pass. Record exact
current database bounds, coverage exclusions, runtime, and no-write result.

- [x] **Step 5: Self-critique and documentation.** Confirm the report includes
  the roster scope statement and does not claim adjusted-price proof, a VCB
  guarantee, portfolio returns, or live fill/cost realism. Update `FOCUS.md`
  and `current-status.md` only with
  evidenced task status. Confirm every active design, plan, UI label, and test
  names V3 as the only valid result/source; completed archives remain historical
  records only. If measured strict joint-trend counts leave a
  coverage-qualified ticker/horizon below its locked `min_n`, report it without
  changing a gate, band, or minimum; do not tune to force qualification. Do not
  delete or otherwise maintain V2 artifacts.

- [ ] **Step 6: Prove one manual V3 signal result.** Only after Steps 1--5
  pass, ask the user to trigger Collect Signals manually for a ticker. Inspect
  the resulting V3 document and job outcome read-only. It must be valid and
  nonempty with at least one certified signal set. If it is empty or invalid,
  report that fact and stop; do not start bulk backfill.

---

### Task 8: Bulk V3 Backfill Before the V2-deletion Permission Gate

**Files:**

- Create: `app/backtest_engine/v3_backfill.py`
- Create: `scripts/backfill_v3_artifacts.py`
- Modify: `app/backtest_engine/persistence.py`, `app/backtest_engine/pipeline.py`,
  `app/backtest_engine/result_store.py`, `FOCUS.md`, `ai-context/current-status.md`
- Test: `tests/test_backtest_v3_backfill.py`, `tests/test_backtest_persistence.py`,
  `tests/test_backtest_pipeline.py`
- Create: `docs/superpowers/reports/2026-08-15-v3-bulk-backfill-report.md`

**Interfaces:**

- `legacy_ticker_manifest(legacy_root) -> tuple[str, ...]` returns uppercase,
  stable-order unique ticker symbols from the exact pre-V3
  `<TICKER>_signals_<THEME_VARIANT>.json` filename shape only. It ignores every
  horizon-qualified V3 filename and does not open, parse, validate, or expose
  a V2 JSON payload.
- `run_v3_bulk_backfill(manifest, engine, output_dir) -> V3BackfillReport`
  runs every target sequentially for Swing and Mid-term with theme enabled.
  It makes two named `backtest_single_v3` calls per ticker—one per horizon;
  each `include_theme=True` call writes its no-theme and themed V3 terminal
  documents. The admin CLI is the only entry point; it is not rendered in
  Streamlit.
- `V3BackfillReport` records every target/treatment path and outcome. A
  terminal document is exactly `success`, `empty`, or `failed`; failed paths
  include `failure_reason` and audit-unavailable metadata where no raw data was
  loaded. Neither result retains a V2 artifact as current evidence. Its fields are
  `requested: frozenset[tuple[str, str, str]]`, `output_paths: tuple[Path,
  ...]`, and per-treatment terminal records. It atomically updates one tracker
  at `app/backtest-result/v3-backfill/<run-id>.json`; callers cannot treat an
  omitted path or nonterminal tracker as a successful backfill.

- [ ] **Step 1: Write RED inventory and terminal-result tests.**

```python
def test_legacy_manifest_reads_only_v2_filenames_not_json_payloads(self):
    vcb_dir = self.tmp_path / "VCB"
    fpt_dir = self.tmp_path / "FPT"
    vcb_dir.mkdir()
    fpt_dir.mkdir()
    (vcb_dir / "VCB_signals_no-background-theme.json").write_text("not json")
    (fpt_dir / "FPT_signals_background-theme.json").write_text("not json")
    hpg_dir = self.tmp_path / "HPG"
    hpg_dir.mkdir()
    (hpg_dir / "HPG_signals_swing_no-background-theme.json").write_text("not json")
    assert legacy_ticker_manifest(self.tmp_path) == ("FPT", "VCB")

def test_bulk_backfill_writes_four_v3_documents_for_every_legacy_ticker(self):
    report = run_v3_bulk_backfill(("FPT",), engine=ENGINE, output_dir=self.tmp_path)
    assert report.requested == {
        ("FPT", "swing", "no-background-theme"),
        ("FPT", "swing", "background-theme"),
        ("FPT", "midterm", "no-background-theme"),
        ("FPT", "midterm", "background-theme"),
    }
    assert all(path.exists() for path in report.output_paths)

def test_backfill_tracker_requires_all_four_terminal_paths(self):
    report = run_v3_bulk_backfill(("FPT",), engine=ENGINE, output_dir=self.tmp_path)
    tracker = load_v3_backfill_tracker(report.tracker_path)
    self.assertEqual(set(tracker["requested"]), set(report.requested))
    self.assertTrue(all(item["terminal_state"] in {"success", "empty", "failed"}
                        for item in tracker["treatments"]))
    self.assertEqual({item["path"] for item in tracker["treatments"]},
                     {str(path) for path in report.output_paths})

def test_terminal_backfill_failure_replaces_requested_v3_path_with_explicit_empty(self):
    report = run_v3_bulk_backfill(("VCB",), engine=FAILING_ENGINE, output_dir=self.tmp_path)
    failed = load_rulebook_result(signal_artifact_path("VCB", "swing", "background-theme", self.tmp_path))
    assert failed["empty"] is True
    assert failed["terminal_state"] == "failed"
    assert failed["failure_reason"]
    assert failed["audit_eligibility"]["source"] == "unavailable"
    assert failed["audit_eligibility"]["eligible"] is False
    assert report.failures[0].ticker == "VCB"

def test_shared_theme_preflight_failure_keeps_no_theme_and_marks_every_themed_path(self):
    report = run_v3_bulk_backfill(("FPT", "VCB"), engine=THEME_FAILING_ENGINE, output_dir=self.tmp_path)
    assert load_rulebook_result(signal_artifact_path("FPT", "swing", "no-background-theme", self.tmp_path))["terminal_state"] in {"success", "empty"}
    for ticker in ("FPT", "VCB"):
        for horizon in ("swing", "midterm"):
            themed = load_rulebook_result(signal_artifact_path(ticker, horizon, "background-theme", self.tmp_path))
            assert themed["empty"] is True
            assert themed["terminal_state"] == "failed"
            assert themed["audit_eligibility"]["source"] == "unavailable"
```

- [ ] **Step 2: Run RED.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_v3_backfill tests.test_backtest_persistence tests.test_backtest_pipeline -v`

Expected: no one-off filename-only manifest/backfill reporter exists; current
pipeline does not guarantee an empty V3 document after a terminal failure.

- [ ] **Step 3: Implement the explicit, user-triggered backfill.** It runs
  only after Task 7's manual V3 proof and only when the user starts it. It uses
  legacy filenames as a read-only target manifest and processes one ticker at a
  time. For each horizon it runs no-theme normally, then uses the shared theme
  result for the themed execution. If the shared theme preflight fails after
  its one retry, complete no-theme PSR work normally and write explicit
  `failed` empty documents for every affected themed path; do not
  suppress, invent, or DSR-adjust no-theme. It writes every requested V3 path
  atomically. Do not parse a V2 document, copy V2 contents, or expose V2 in a
  current UI reader. Report every success, no-certified empty result, and
  terminal failure separately. A failed target still receives its explicit
  V3-empty failure document; it is not a reason to retain a V2 file later. Each
  path is tmp-and-rename atomic; write/update the small tracker after each path
  reaches a terminal state. Preserve the Group move journal unchanged.

- [ ] **Step 4: Run GREEN and publish the terminal report.**

Run: `docker exec stock_app python -m unittest tests.test_backtest_v3_backfill tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_worker -v`

Expected: every legacy target has four horizon/treatment-qualified terminal V3
documents, each V2 payload remains unread, and the completed tracker records
every path. Terminal failures are truthful empty V3 results with reasons.

- [ ] **Step 5: Ask the V2-deletion permission question.** Read-only list the
  exact V2 paths, include the completed V3 backfill report and tracker, and ask the user
  for explicit deletion approval. The backfill, its report, and any V3 empty
  failures are not deletion permission. This plan ends at that question.

---

### Task 9: Close the Approved Cleanup and Remove Temporary Audit Input

**Files:**

- Delete only after separate approval: exact V2 files listed by Task 8 and
  `docs/superpowers/work-items/2026-08-15-v3-frozen-roster.json`
- Modify: `FOCUS.md`, `ai-context/current-status.md`,
  `docs/superpowers/reports/2026-08-15-v3-bulk-backfill-report.md`

**Gate:** This task is prohibited until the user explicitly approves the exact
V2 deletion list produced by Task 8. It uses that same approval for the
temporary roster input because the user has already required its removal only
after the whole plan completes. The permanent Task 0 audit report remains. It
never deletes any other report, Group JSON, status sidecar, position record,
or V3 artifact.

- [ ] **Step 1: Re-read the completed tracker and deletion approval.** Confirm
  every requested tuple is terminal in the tracker and its artifact path still
  exists. If either check fails, stop without deletion.

- [ ] **Step 2: Delete the exact approved V2 paths and temporary roster input.**
  Do not use a glob, recursive target, or inferred path. Preserve the Group
  move journal and all V3/backfill evidence.

- [ ] **Step 3: Verify and document closure.** Confirm every approved target
  no longer exists, the completed tracker/V3 paths remain readable, and update
  the report, `FOCUS.md`, and `current-status.md` with the exact deleted list.
  This closure completes the V3 prerequisite and releases only Phase A of
  `2026-08-16-validate-positions-risk-and-trade-rows.md`; Phase B still needs
  its separate risk-contract approval.
