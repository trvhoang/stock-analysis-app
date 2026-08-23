# Backtest Zero-Signal Investigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to execute each task in order. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify the earliest stage that turns the 15-year FPT Swing
Backtest into zero certified sets, repair only that confirmed cause, apply the
separately approved long-only exit policy before downstream measurement, and
record a reproducible read-only evidence report.

**Architecture:** First freeze the two completed-job artifacts, then run an
existing-code, live read-only score probe for one all-indicator, threshold-60,
soft-ADX FPT Swing combination. Its explicit route identifies the first failed
stage: score-input resolution, score coverage, crossing semantics, execution,
or certification. The new minimum-hold policy is deliberately downstream of
that root-cause route; no later task runs until its preceding measurement
supports it.

**Tech Stack:** Python 3.12, `unittest`, pandas, the existing Backtest engine,
and PostgreSQL through the already configured Docker application container.

## Global Constraints

- Do not modify `app/common_queries.py`, ingestion BIGINT scaling,
  `get_engine_with_retry()`, the `.env`/`main.py` credential-loading pattern,
  or Docker files.
- Preserve raw BIGINT engine prices, long-only entries, next-open entry,
  ATR exits, score grid, `MIN_N`, Deflated Sharpe, permutation settings, and
  existing theme semantics.
- `VNINDEX` is a non-tradeable confirmation series. A Phase 1 ticker position
  is one implicit-unit BUY entry and one equal implicit-unit SELL closure; no
  short entry, short closure, or unbalanced position is permitted. Swing SL,
  TP, and timeout closures are ineligible until
  `exit_position - entry_position >= 3` daily bars. Mid-term is all-weekly:
  its ticker OHLCV, indicators, ATR, crossings, execution, and timeout use
  weekly bars only; exits are ineligible on the entry bar and first eligible
  on the next weekly bar. `MAX_HOLD_MIDTERM_BARS = 16` is inclusive: entry is
  bar 1 and timeout closes at bar 16. The current schema has no quantity or
  multi-fill records, so multi-fill support is explicitly out of scope for
  this repair and needs a separate approved model migration.
- This incident is FPT, Swing, and 15 years only. Do not claim Mid-term is
  repaired from this evidence; Task 7 performs its separately gated all-weekly
  conformance repair only after the FPT Swing cause and regression gates pass.
- The Swing three-session minimum hold is a new approved lifecycle policy, not
  a hypothesis for missing scores or BUY crossings. Apply it after a positive
  FPT Swing crossing is proven and before a downstream full-grid measurement.
- The current job runner launches one isolated module-worker subprocess; the
  computational pipeline evaluates its combo/window loops sequentially. Its
  reaper thread is lifecycle handling, not Backtest parallelism. This plan
  therefore contains no executor/thread-pool diagnosis.
- Report both overlapping-window event totals and unique events, but preserve
  current validation input unchanged. Deduplicating candidates before
  `validate_candidates()` is a separate statistical-design decision.
- Do not lower thresholds or significance gates, or change ATR/Bollinger
  semantics, merely to produce a certified set.
- The Step 0 and diagnostic commands are read-only: no job submission,
  database mutation, status-sidecar write, or ticker-signal overwrite.
- Write one failing regression test before each production change. Make one
  confirmed repair, rerun Step 0, then reassess; never patch Tasks 2–4 in a
  bundle. No commit is created.

---

### Task 0: Freeze the existing incident evidence before any new probe

**Files:**
- Modify: `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`

**Interfaces:**
- Consumes `read_job_status(job_id, "backtest-status")` and each returned
  artifact path as JSON.
- Produces an immutable report baseline only; it submits no job and does not
  write a status sidecar or signal artifact.

- [x] **Step 1: Read both terminal statuses and their artifacts in Docker.**

  ```powershell
  docker exec stock_app python -c "import hashlib,json; from pathlib import Path; from backtest_engine.job_runner import read_job_status; ids=('24bac55bd995444eaf4dc6a9118f5758','6086db3928344074b0046a7a4234c9ef'); [print({'job_id': job_id, 'status': status.to_dict(), 'artifacts': [{'path': str(path), 'exists': path.exists(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None, 'payload': {key: json.loads(path.read_text(encoding='utf-8')).get(key) for key in ('empty','signal_sets')} if path.exists() else None} for path in map(Path, status.output_paths)]}) for job_id in ids for status in (read_job_status(job_id, 'backtest-status'),)]"
  ```

  Expected: each job is terminal with its persisted path; each artifact records
  `empty: true` and no populated metric set. If a file is missing, malformed,
  or differs from the recorded job output, stop: that is a persistence/status
  investigation, not a scoring repair.

- [x] **Step 2: Append the exact baseline.**

  Record job ID, state, progress, output path, artifact `empty` value, metric
  keys, and the SHA-256 of the raw artifact bytes. Treat this report section as
  the comparison baseline for all later diagnostic output.

- [x] **Step 3: Run the source-conformance audit before interpreting live results.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_combos tests.test_backtest_validation -v
  ```
  Expected: PASS. Then record these source facts in the triage report:

  - Hard ADX removes `trend_direction` only on rows where ADX is below 20,
    divides by the per-row remaining weight, and retains the `/ 4 * 100`
    points-scale normalization. A passing characterization is not a formula
    repair.
  - `calculate_deflated_sharpe()` consumes unannualized trade returns and
    calculates Pearson/non-excess kurtosis directly; no annual factor or
    library-default excess-kurtosis path is allowed.
  - The ticker Mid-term indicator/execution frame is traced separately from the
    VN-Index theme frame. A daily ticker frame alongside weekly VN-Index
    confirmation is recorded as the separate conformance issue repaired only
    by Task 7's approved all-weekly change.

---

### Task 1: Run and record the mandatory Step 0 live probe

**Execution status (2026-08-06):** Complete. After the live runtime URL was
corrected, the read-only probe connected to PostgreSQL at `db:5432`, selected
exactly one baseline combination, and found 3,736 score values all equal to
`50`. Only `OBV` matched the seven requested trend-label inputs; threshold hits
and BUY crossings were both zero. The result selects Task 2. The preceding
URL-port blocker and exact metrics are recorded in the triage report.

**Files:**
- Modify: `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`

**Interfaces:**
- Consumes `load_ticker_history()`, `build_indicator_frame()`,
  `generate_signal_combos()`, `score_combo()`, and `detect_buy_crossings()`.
- Produces a report section with one score summary and a route selection; no
  application file is created or modified.

- [x] **Step 1: Select the exact baseline combination.**

  From `generate_signal_combos("swing", include_theme=False)`, select the one
  combination with all four voting dimensions, threshold `60`, and
  `adx_gate_mode="soft"`. Use FPT from 2011-08-04 through 2026-08-04. Do not
  use a worker or `run_backtest_pipeline()` because either path can overwrite
  the current FPT artifact.

- [x] **Step 2: Run this read-only probe in Docker.**

  ```powershell
  docker exec stock_app python -c "from datetime import date; from commons import technical_analysis as ta; from pages.data_preparation import get_engine_with_retry; from backtest_engine.pipeline import _database_url; from backtest_engine.data_quality import load_ticker_history; from backtest_engine.indicators import build_indicator_frame; from backtest_engine.signal_combos import generate_signal_combos, score_combo, detect_buy_crossings; e=get_engine_with_retry(_database_url()); raw=load_ticker_history('FPT',date(2011,8,4),date(2026,8,4),e); f=build_indicator_frame(raw,'swing'); expected=tuple((d,ta.TECHNICAL_DIMENSIONS[d]) for d in ta.TECHNICAL_GROUP_WEIGHTS); c=next(x for x in generate_signal_combos('swing',False) if x.indicators==expected and x.threshold_score_buy==60 and x.adx_gate_mode=='soft'); s=score_combo(f,c); required=tuple(name for _, names in c.indicators for name in names); print({'raw_rows':len(raw),'required_inputs':required,'input_matches':sorted(set(f.columns)&set(required)),'describe':s.describe().to_dict(),'value_counts':s.value_counts(dropna=False).to_dict(),'nan_count':int(s.isna().sum()),'at_or_above_60':int(s.ge(60).sum()),'crossing_count':int(detect_buy_crossings(s,60).sum())}); e.dispose()"
  ```

  Expected: one dictionary containing `describe` (count, mean, min, max),
  `value_counts`, `nan_count`, `at_or_above_60`, `crossing_count`, required
  inputs, and matched inputs. The command may read the database only and must
  not create a job/status/artifact.

- [x] **Step 3: Record the route without changing source.**

  Append the exact output and one selected route to the triage report:

  | Observation | Single next route |
  |---|---|
  | Any required trend-label input is absent, or the score is flat at the neutral fallback | Task 2: repair the score-input contract first. |
  | Score varies but remains below 60 with every required input resolved | Task 3: investigate one score-formula/coverage cause; do not reinterpret ATR without product approval. |
  | Score reaches 60 but crossing count is zero | Task 4: investigate crossing/warm-up semantics. |
  | Crossing count is positive | Task 5: enforce the required long-only lifecycle, then Task 6: measure trade and certification gates. |

  Do not advance on a missing, errored, or ambiguous measurement.

### Task 2: Repair the score-input contract only if Step 0 selects it

**Execution status (2026-08-06):** Complete. The approved canonical MA sources
are Swing `5/10` and Mid-term `4/12`. The RED gate failed for the missing
contract and numeric-OBV fallback; the full Task 2 gate passed 27/27. The
read-only FPT rerun resolved all seven inputs, reached the 60 threshold 1,358
times, and produced 228 BUY crossings. This selects Task 5; Tasks 3 and 4 are
not selected.

**Files:**
- Modify: `tests/test_backtest_indicators.py`
- Modify: `tests/test_backtest_signal_combos.py`
- Modify: `tests/test_backtest_pipeline.py`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `app/backtest_engine/indicators.py`
- Modify: `app/backtest_engine/signal_combos.py`

**Interfaces:**
- Produce `BACKTEST_SIGNAL_COLUMNS`, mapping `MA`, `MA cross`, `RSI`,
  `Stochastic`, `OBV`, `ATR`, and `Bollinger` to distinct label columns.
- Enrich `build_indicator_frame(ohlcv, horizon) -> pd.DataFrame` itself with
  those canonical label columns. Do not introduce an uncalled second adapter:
  both `run_backtest_pipeline()` and `check_current_situation()` already call
  `build_indicator_frame()`.
- `score_combo()` resolves each requested indicator through that mapping; raw
  `OBV` and `ATR_14` remain numeric calculation/trade columns.

- [x] **Step 1: Write the failing regression test.**

  Use a numeric indicator frame containing `SMA_*`, `cross_*`, `RSI_14`, `%K`,
  `%D`, `ATR_14`, numeric `OBV`, Bollinger columns, and `ADX_14`. Assert that
  `build_indicator_frame()` adds seven mapped trend-label columns while
  preserving numeric `OBV` and `ATR_14`. Assert `score_combo()` reads the
  mapped labels, not numeric `OBV` as a neutral fallback.
  Add one pipeline and one early-warning fixture that each use the enriched
  frame and produce the same score through the shared scorer.

- [x] **Step 2: Verify RED.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_indicators tests.test_backtest_signal_combos -v
  ```
  Expected: failure because the named signal-label adapter does not exist or
  the scorer still uses raw numeric columns.

- [x] **Step 3: Implement only the label adapter and mapped lookup.**

  Build labels inside `build_indicator_frame()` once per row using only history
  through that row: four rows for
  MA reversal, accumulated last-three events for MA Cross, thirty rows for
  RSI, one current row for Stochastic/Bollinger, twenty-one rows for ATR, and
  eleven rows for OBV. Reuse the existing `calculate_*_trend` classifiers.
  `score_combo()` must prefer mapped label columns and use the current
  bare-name columns only for existing synthetic unit fixtures.

- [x] **Step 4: Verify GREEN and no look-ahead.**

  Mutate rows after date `T` and assert labels/scores through `T` are
  unchanged. Assert the pipeline and early-warning fixtures observe identical
  canonical label columns and score values. Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_pipeline tests.test_backtest_early_warning tests.test_backtest_trade_execution -v
  ```
  Expected: all selected tests pass and numeric raw-price/indicator columns
  remain unchanged.

- [x] **Step 5: Rerun Step 0 before any full-grid work.**

  Run the exact Task 1 command, append before/after metrics, and select one
  later route. If the score still never reaches 60, advance only to Task 3; if
  it reaches 60 with crossings, advance to Task 5 before any downstream
  full-grid measurement.

### Task 3: Investigate one score-formula cause only when labels are present

**Files:**
- Modify: `tests/test_backtest_signal_combos.py`
- Modify: `app/backtest_engine/signal_combos.py` only if the focused test
  proves the selected formula defect

**Interfaces:**
- `score_combo(indicator_frame, combo) -> pd.Series`
- Add `score_combo_breakdown(indicator_frame, combo) -> ScoreBreakdown`, where
  `ScoreBreakdown` exposes the final score, per-dimension score series,
  low-ADX mask, and effective denominator series. `score_combo()` delegates to
  this helper and returns only `breakdown.score`, so diagnostics and production
  scoring cannot diverge.

- [ ] **Step 1: Write failing breakdown and formula-characterization tests.**

  First assert importing `score_combo_breakdown()` fails. Then use canonical
  labels to isolate any measured volatility contribution. Do not change ATR's
  meaning from volatility to bullishness without an explicit product decision.
  Add three full-score hard-ADX rows: high ADX retains the four-dimension
  denominator, low ADX removes only `trend_direction` and renormalizes to 100,
  and missing ADX retains all four dimensions. This proves the gate is per row,
  not a static mode-wide trend removal. The fixed `/ 4 * 100` scale remains
  unchanged in every row; only effective dimension weights renormalize.

- [ ] **Step 2: Verify RED, add the shared breakdown, and correct at most one proven formula.**

  Run the focused test and confirm the new breakdown import fails. Implement
  the shared breakdown without changing score values. Run the characterization
  rows: if they pass, do not modify ADX logic; if one fails, modify only that
  proven formula. Do not replace the fixed points-scale divisor with the count
  of active dimensions. A volatility-polarity change requires explicit user
  approval.

- [ ] **Step 3: Verify GREEN, then rerun Step 0.**

  Run the focused score tests and the exact Task 1 probe. Record whether score
  maximum, threshold reach, and crossing count changed as predicted. If score
  reaches the threshold but crossings remain zero, advance only to Task 4. If
  score still cannot reach the threshold, stop and return to diagnosis.

### Task 4: Investigate crossing/warm-up logic only when Step 0 selects it

**Files:**
- Modify: `tests/test_backtest_signal_combos.py`
- Modify: `app/backtest_engine/signal_combos.py`

**Interfaces:**
- `detect_buy_crossings(score: pd.Series, threshold: int) -> pd.Series`

- [ ] **Step 1: Write failing warm-up boundary tests.**

  Assert the first row never fires; a `NaN` predecessor follows the documented
  no-trigger rule; and a later valid 59-to-60 transition fires once. The test
  must state whether the first non-NaN at/above 60 is intentionally ignored or
  is a desired entry, before code changes.

- [ ] **Step 2: Verify RED, then choose the smallest no-look-ahead rule.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_combos -v
  ```
  Expected: the chosen boundary behavior fails under the current crossing
  function. If requirements do not decide first-valid-entry behavior, stop and
  ask the user rather than assuming it.

- [ ] **Step 3: Implement and verify one crossing correction.**

  Keep all score values intact, alter only crossing eligibility, rerun the
  focused score/trade tests, and then rerun Step 0. Confirm the only predicted
  difference is crossing count. Advance to Task 5 only when a crossing is
  present; otherwise stop and record the disproved hypothesis.

### Task 5: Apply the Swing-only minimum-hold policy after the FPT Swing crossing cause is confirmed

**Execution status (2026-08-06): Complete.** The RED gate failed as expected
because historical and replay exits could close on the entry bar, and a custom
Swing hold of three bars was accepted. `MIN_EXIT_OFFSET_SWING_BARS = 3` now
feeds one shared historical/replay eligibility boundary; the Swing-only GREEN
gate passed 17/17. No job, artifact, status, database, or persistence path was
executed by this task.

**Files:**
- Modify: `tests/test_backtest_trade_execution.py`
- Modify: `tests/test_backtest_rolling_window.py` only if an existing timeout
  expectation encodes an earlier exit
- Modify: `app/backtest_engine/config.py`
- Modify: `app/backtest_engine/rolling_window.py`

**Interfaces:**
- Add `MIN_EXIT_OFFSET_SWING_BARS = 3` to `backtest_engine.config`.
- `run_combo_window()` and `evaluate_current_combo()` must share one exit
  eligibility rule: an entry at raw daily-frame row `i` can close only at row
  `i + 3` or later.
- Do not alter Mid-term execution in this task. Its current ticker-frame
  mismatch is repaired only by Task 7's all-weekly change; treating its daily
  rows as weekly bars here would create a second timeframe defect.
- A current `TradeEvent` remains one implicit unit BUY and one equal implicit
  unit SELL. Do not add a quantity field or multi-fill behavior in this task.
- This task is policy compliance only. It must not be reported as the cause of
  a missing score or BUY crossing, and it runs only after Task 1/2/3/4 reaches
  a positive FPT Swing crossing.

- [x] **Step 1: Write failing lifecycle regression tests.**

  Construct daily OHLC fixtures with an entry at row `i`, SL/TP hits at
  `i`, `i + 1`, or `i + 2`, and another hit at `i + 3`. Assert the event exits
  on the eligible `i + 3` row, never on an earlier row. Construct an eligible
  `i + 3` bar that hits both levels and assert `stop_loss` wins. Assert a
  timeout cannot resolve before `i + 3`; reject Swing `max_hold_bars < 4`, because
  the existing inclusive entry-bar window otherwise cannot contain row
  `i + 3`. Cover
  `evaluate_current_combo()` with the same early-hit fixture so replay and
  historical execution cannot drift.

- [x] **Step 2: Verify RED.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_trade_execution tests.test_backtest_rolling_window -v
  ```
  Expected: the early SL/TP or timeout test fails because current code scans
  from the entry bar and permits an immediate closure.

- [x] **Step 3: Implement one shared eligibility boundary.**

  Define the named Swing-only minimum-exit offset. Retain the next-open BUY,
  original signal-bar ATR, raw BIGINT prices, and existing SL-first ordering.
  Restrict Swing `_first_exit()` and timeout selection to bars with positional
  distance at least three from entry. Make invalid Swing custom hold lengths
  fail explicitly rather than silently producing an early timeout. Use the
  same Swing helper in `run_combo_window()` and `evaluate_current_combo()`.

- [x] **Step 4: Verify GREEN and lifecycle invariants.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_trade_execution tests.test_backtest_rolling_window tests.test_backtest_early_warning -v
  ```
  Assert all emitted
  Swing `TradeEvent`s have `exit_date` on or after the third subsequent daily
  bar, retain one long entry and one equal implicit closure, and never
  introduce a short entry or technical SELL signal. Re-run the
  protected-boundary check.

### Task 6: Measure downstream trade and certification gates only after crossings and Task 5

**Execution status (2026-08-06): Complete.** The DSR conformance gate passed
5/5. The read-only collector and regression gate passed 17/17 (one CLI test is
host-only because Docker does not mount `scripts/`), and its mocked container
CLI test passed. Full 15-year FPT Swing reports are retained at
`2026-08-06-fpt-swing-no-theme-funnel.json` and
`2026-08-06-fpt-swing-vnindex-and-funnel.json`. Neither measurement submitted a
job, wrote a signal artifact or status sidecar, certified a set, or changed the
database.

**Files:**
- Create: `app/backtest_engine/diagnostics.py`
- Create: `scripts/debug_backtest_zero_signal.py`
- Create: `tests/test_backtest_diagnostics.py`
- Modify: `app/backtest_engine/rolling_window.py`
- Modify: `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`

**Interfaces:**
- `collect_backtest_diagnostics(config, engine) -> dict[str, object]`
- CLI: `python scripts/debug_backtest_zero_signal.py --ticker FPT --horizon swing --years 15 --output <report.json>`
- `run_combo_window(..., diagnostic_counters: Counter[str] | None = None)`;
  production callers omit this optional argument, while diagnostics pass one
  counter owned by the current combo/window invocation. The production and
  diagnostic paths therefore share every candidate rejection decision.
- `combo_key(combo) -> str` is
  `json.dumps(combo.to_dict(), sort_keys=True, separators=(",", ":"))`; the
  current `IndicatorCombo` has no `combo_id` field. The diagnostics report uses
  this key without adding a persisted model field.
- Each counter uses only these keys: `ticker_crossings`, `theme_crossings`,
  `missing_next_bar`, `invalid_atr`, `invalid_entry_price`,
  `insufficient_window`, `pre_hold_exit_hit`, and `completed_trades`. The
  caller initializes one empty counter per combo and aggregates it only across
  that combo's overlapping windows.

- [x] **Step 1: Verify the DSR conformance gate before any statistical conclusion.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_validation -v
  ```
  Expected: PASS. In the report, state that the checked DSR path uses
  unannualized per-trade returns, manual Pearson/non-excess kurtosis, observed
  trial-Sharpe variance, and the permutation gate only after DSR. If this gate
  fails, stop: investigate the named statistical convention before treating a
  DSR rejection as valid.

- [x] **Step 2: Write failing read-only funnel tests.**

  Assert the document includes the canonical combo key and counts per combo for ticker crossings,
  theme-confirmed crossings, missing next bars, invalid ATR/entry bars,
  early SL/TP hits ignored by the minimum-hold rule, completed raw trades,
  unique `(combo_key, signal_date)` trades, and
  `duplicate_event_count = raw_event_count - unique_event_count`. Assert it
  then reports `min_n`,
  Deflated Sharpe, permutation outcome, and qualified count. Mock persistence
  and job submission; assert neither is called.

- [x] **Step 3: Verify RED and implement the shared read-only diagnostic.**

  Reuse the production loader, quality validation, score, crossing,
  `run_combo_window()`, and `validate_candidates()` calls. Record total and
  unique overlapping-window events and the duplicate-event count separately,
  but pass the existing total event sequence unchanged to
  `validate_candidates()`. Import `Counter` from `collections` and `json` for
  the defined counter/key interfaces. Do not invoke
  `run_backtest_pipeline()`, `certify_top_sets()`, or
  `save_certified_signals()`. The CLI writes only the explicit report path.

- [x] **Step 4: Verify GREEN and run the full-grid funnel.**

  Run the diagnostics tests, then FPT no-theme first and VN-Index `AND`
  second. Record `elapsed_seconds`, combo count, and window count before each
  run so an unexpected large-query delay is attributable. Report `(combo_key,
  ticker_crossings, theme_crossings,
  completed_trade_count, unique_trade_count, duplicate_event_count,
  passed_min_n, dsr, passed_dsr, passed_permutation)` for every combo. For
  every combination below `MIN_N`,
  name the first insufficient funnel stage. If ticker crossings are the first
  insufficient stage and later execution/theme counters do not explain the
  loss, return to Task 3 for score-coverage diagnosis; do not accept `min_n`
  as a final statistical explanation. Interpret a DSR/permutation rejection as
  valid only after the preceding funnel stages are evidenced. If duplicate
  events exist, record their count and rate but do not deduplicate or alter
  `MIN_N`; request a separate statistical-design decision before changing the
  approved pooled-window validation input.

### Task 7: Restore the approved all-weekly Mid-term contract after FPT Swing gates pass

**Execution status (2026-08-07): Complete.** One shared weekly adapter now
supplies Mid-term ticker indicators and VN-Index confirmation. The focused
all-weekly contract gate passed 42/42; the preserved Swing lifecycle gate
passed 20/20. The bounded read-only FPT Mid-term probe returned 775 weekly
scores, 410 at or above 60, and 41 BUY crossings. No job, artifact, status
sidecar, database write, or commit was made.

**Files:**
- Create: `app/backtest_engine/timeframes.py`
- Modify: `app/backtest_engine/config.py`
- Modify: `app/backtest_engine/indicators.py`
- Modify: `app/backtest_engine/rolling_window.py`
- Modify: `app/backtest_engine/vnindex_theme.py`
- Modify: `tests/test_backtest_contracts.py`
- Modify: `tests/test_backtest_indicators.py`
- Modify: `tests/test_backtest_trade_execution.py`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `tests/test_backtest_vnindex_theme.py`
- Modify: `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`

**Interfaces:**
- `to_weekly_ohlcv(frame: pd.DataFrame) -> pd.DataFrame` is the single shared
  daily-to-weekly adapter. It aggregates `open:first`, `high:max`, `low:min`,
  `close:last`, and `volume:sum`, drops weeks lacking required OHLC values, and returns a
  date-sorted frame without mutating daily input.
- `MAX_HOLD_MIDTERM_BARS = 16` replaces the ambiguous Mid-term hold constant.
  The inclusive execution window is entry bar 1 through timeout bar 16.
- Mid-term `build_indicator_frame()` uses the weekly adapter before every
  indicator and ATR calculation; Swing continues to use daily input.
- `run_combo_window()` and `evaluate_current_combo()` use the same
  horizon-specific exit offset: Swing 3 daily bars; Mid-term 1 weekly bar.
  They preserve the inclusive 16-bar Mid-term timeout, so only SL/TP scanning
  starts at weekly bar 2; timeout still resolves at weekly bar 16.
- `build_vnindex_confirmation()` reuses the same weekly adapter. No Mid-term
  path reads daily execution bars after a weekly signal.

- [x] **Step 1: Write failing all-weekly conformance tests.**

  Use daily OHLCV spanning two complete weeks. Assert the shared adapter
  produces exactly two weekly rows with the documented aggregation and leaves
  the daily input unchanged. Assert a Mid-term indicator frame has those two
  weekly rows before `calculate_ma_cross()` and `calculate_atr()` run, while a
  Swing frame retains daily rows. Assert VN-Index confirmation uses the same
  weekly dates as the ticker path.

  Use a 17-row weekly fixture: a signal before entry, entry at weekly bar 1,
  SL/TP hits on bar 1 and bar 2, and no later hit. Assert bar-1 hits are
  ignored, the bar-2 hit closes the trade, a custom Mid-term hold below 2 is
  rejected, and a no-hit 16-bar future times out at bar 16. Replay the fixture
  through `evaluate_current_combo()` and assert identical eligibility and
  timeout dates.

- [x] **Step 2: Verify RED.**

  Run:
  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_indicators tests.test_backtest_trade_execution tests.test_backtest_early_warning tests.test_backtest_vnindex_theme -v
  ```
  Expected: failure because Mid-term indicators currently consume daily ticker
  rows and execution currently allows the entry-bar exit.

- [x] **Step 3: Implement one shared weekly clock and horizon-specific exits.**

  Move VN-Index's existing weekly aggregation into `timeframes.py`; do not
  duplicate its aggregation. Route both Mid-term ticker indicators and
  VN-Index confirmation through it. Rename the Mid-term constant to
  `MAX_HOLD_MIDTERM_BARS` and update all imports/tests in this task. Keep the
  16-row inclusive future window; pass only `future.iloc[1:]` to Mid-term
  SL/TP detection and retain `future.iloc[-1]` for timeout. Preserve the
  Swing offset introduced by Task 5. Do not query, join, or inspect daily bars
  after a Mid-term weekly entry.

- [x] **Step 4: Verify GREEN, no-look-ahead, and FPT Swing regression.**

  Re-run the Step 2 command. Mutate daily rows after a completed weekly bar
  and assert earlier Mid-term labels, scores, and exits do not change. Re-run
  the Task 5 Swing gate and confirm its daily exit dates are unchanged. Record
  the former daily-ticker/weekly-VN-Index mismatch and the corrected
  all-weekly contract in the triage report.

- [x] **Step 5: Run the bounded Mid-term score probe only after Step 4 passes.**

  Run Task 1's read-only FPT probe with `horizon='midterm'`, using the same
  historical dates and reporting weekly-row count, required/matched inputs,
  score distribution, threshold hits, and BUY crossings. A failure starts a
  separate Mid-term diagnosis and never changes the completed FPT Swing
  evidence.

### Task 8: Final verification and documentation

**Execution status (2026-08-07): Complete.** The complete explicit Backtest
Docker gate passed 60/60 with the diagnostics CLI test temporarily made
available inside the container. The previously skipped test exposed and then
proved a stale mock-payload repair; production diagnostics behavior was
unchanged. Compilation and whitespace checks passed. The all-suite discovery
topology remains noncanonical and is documented separately.

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`

- [x] **Step 1: Run focused Backtest tests.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_trade_execution tests.test_backtest_rolling_window tests.test_backtest_pipeline tests.test_backtest_early_warning tests.test_backtest_validation tests.test_backtest_vnindex_theme tests.test_backtest_diagnostics -v
  ```

  Expected: all selected tests pass.

- [x] **Step 2: Run the broader verification gate.**

  Run the explicit Backtest modules, `python -m compileall -q backtest_engine
scripts/debug_backtest_zero_signal.py`, `git diff --check`, and protected-file
diff inspection. Record exact output; report the pre-existing full-discovery
exception separately if it remains.

- [x] **Step 3: Update context from measurements only.**

  State the Step 0 metrics, confirmed repair, and remaining validated
rejection/gate results. Resume comprehensive unit-test expansion only after
this issue is resolved or explicitly deferred.
