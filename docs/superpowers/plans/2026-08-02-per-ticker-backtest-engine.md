# Per-Ticker Signal-Set Backtest Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, long-only, per-ticker backtest engine that searches the approved technical-signal space, validates candidates, persists exactly two current certified files per ticker, and exposes a standalone Backtest page that submits jobs and reads results.

**Architecture:** The logical `backtest_engine/` package from `BACKTEST_ENGINE.md` will live at `app/backtest_engine/` so the existing Docker image and mounted application can import it without Dockerfile changes. Pure engine modules reuse the existing indicator registry and scoring contracts; the rolling evaluator produces deterministic trade events; validation, certification, persistence, job status, and the standalone page consume those contracts without duplicating indicator or SQL logic.

**Tech Stack:** Python 3.12, pandas, NumPy, existing indicator functions, SQLAlchemy, PostgreSQL, `ProcessPoolExecutor`, Streamlit, Plotly, `unittest`, JSON persistence.

## Global Constraints

- Implementation is active; completed phases are marked only after their
  focused RED-to-GREEN tests and phase-level checks pass.
- Every implementation task follows TDD: write one focused failing test, verify RED, implement the smallest change, verify GREEN, self-review, then advance.
- Each phase is blocked until its task tests and phase-level checks pass; FOCUS.md is the phase/task ledger.
- Long-only Phase 1: one BUY entry on an upward score crossing; exits are ATR stop-loss, ATR take-profit, or timeout; no short entries and no technical early exits.
- Use existing `app/commons/technical_analysis.py` indicator functions, dimensions, point mapping, equal group weights, and ADX gate semantics; do not reimplement them in the engine.
- Do not modify `app/commons/common_queries.py`, `BASE_DELTA_CALC_CTE`, `COMMON_DELTA_FILTER_WHERE_CLAUSE`, `app/pages/data_preparation.py` scaling/connection logic, `IMPLEMENTED.md`, Docker configuration, or credentials.
- Any new SQL uses `sqlalchemy.text()` with bound parameters, `get_engine_with_retry()`, and `engine.raw_connection()`; no SQL price division or storage changes.
- Database prices remain raw BIGINT values. Backtest ratios and ATR calculations may operate on a copied numeric frame, but no UI/export path may receive altered storage values.
- The engine never runs synchronously in a Streamlit request. Long work is submitted to a background job and parallel combo/window work uses configurable `ProcessPoolExecutor` workers, default six.
- Search space is limited to indicator subsets by existing dimensions, `THRESHOLD_SCORE_BUY_GRID = (60, 65, 70, 75, 80)`, `adx_gate_mode in ("soft", "hard")`, horizon, and theme variant; group weights remain equal and are not searched.
- Defaults are named and overridable: `MIN_N=30`, six-month rolling window, one-month sliding stride, ATR(14) SL 1.5, ATR(14) TP 2.5, swing max hold 15 daily bars, mid-term max hold 16 weekly bars, permutation count 1000, seed 42, moving block size 20, PSR/Deflated-Sharpe cutoff 0.95.
- Data quality runs before indicators. Invalid structure/non-positive prices block a run; unexplained moves over 7% and date gaps are retained as explicit quality findings rather than silently dropped. The gap policy must be encoded in Phase 1 tests before production code is written; holiday gaps must not be treated as missing trading data by an unverified calendar heuristic.
- Certified persistence uses JSON as the source of truth and exactly two current files per ticker: `{TICKER}_signals_no-background-theme.json` and `{TICKER}_signals_background-theme.json`; re-certification atomically overwrites only the selected current file.
- VN-Index theme evaluation is optional, date-aligned without look-ahead, uses existing MA logic with daily SMA(50) for Swing and weekly SMA(20) for Mid-term, and tests no-theme/AND/OR empirically without assuming benefit.
- The standalone page is `app/pages/backtest_lab.py`; navigation integration is deferred until the engine/job contracts are proven.

---

## Phase 0: Freeze Contracts and Test Fixtures

**Purpose:** Establish exact schemas and reusable deterministic fixtures before any engine behavior is implemented. This phase prevents later modules from inventing incompatible shapes.

**Files:**
- Create: `app/backtest_engine/__init__.py`
- Create: `app/backtest_engine/config.py`
- Create: `app/backtest_engine/models.py`
- Test: `tests/test_backtest_contracts.py`
- Modify: `FOCUS.md` only to record phase progress after tests pass

**Interfaces:**
- `BacktestConfig`: ticker, start/end dates, horizon, theme variant/mode, worker count, output directory, and named defaults.
- `IndicatorCombo`: immutable dimension subsets, threshold, ADX gate mode, horizon, and theme metadata.
- `TradeEvent`: signal date, entry date/price, ATR, SL/TP, exit date/price, exit reason, return, and source window.
- `JobStatus`: job id, state (`queued/running/done/failed`), progress, output paths, and error text.

- [x] **Task 0.1 — Write contract tests first.** Assert defaults, enum validation, long-only direction, JSON-safe serialization, exact two theme variants, and rejection of invalid horizon/theme/mode/threshold values.

  ```python
  def test_default_config_is_long_only_and_uses_approved_risk_values():
      config = BacktestConfig.for_ticker("FPT")
      self.assertEqual(config.direction, "long")
      self.assertEqual(config.max_hold_bars, 15)
      self.assertEqual(config.atr_sl_multiplier, 1.5)
      self.assertEqual(config.atr_tp_multiplier, 2.5)
  ```

- [x] **Task 0.2 — Run RED.**

  `docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_contracts -v`

  Expected: import/attribute failure because the new contracts do not exist.

  The initial local run also confirmed the expected missing-module RED before
  Docker became available for the GREEN gate.

- [x] **Task 0.3 — Implement the smallest contracts and named constants.** Use dataclasses/enums and explicit validation; do not add persistence or engine behavior yet.

- [x] **Task 0.4 — Run GREEN and contract review.** The focused file passes; FOCUS records Phase 0 complete only after no placeholder, serialization, or naming mismatch remains.

**Phase gate:** PASS — Docker `tests.test_backtest_contracts` is 8/8 green,
the package compiles, and the FOCUS contract checklist is checked.

---

## Phase 1: Data Quality, Raw History, and Indicator Adapter

**Purpose:** Build the mandatory pre-indicator quality gate from scratch and connect the engine to existing raw OHLCV data and indicator functions.

**Files:**
- Create: `app/backtest_engine/data_quality.py`
- Create: `app/backtest_engine/indicators.py`
- Test: `tests/test_backtest_data_quality.py`
- Test: `tests/test_backtest_indicators.py`

**Interfaces:**
- `validate_ohlcv(frame) -> DataQualityReport(valid_frame, errors, warnings)`.
- `load_ticker_history(ticker, start_date, end_date, engine) -> pandas.DataFrame` using one parameterized raw-price query.
- `build_indicator_frame(ohlcv, horizon) -> pandas.DataFrame` calling existing MA/MA-cross/RSI/Stochastic/ADX/OBV/ATR/Bollinger functions.
- `score_indicator_value(label) -> int` and `build_dimension_scores(...)` reuse the existing 4/3/2/1/0 mapping and equal group weights without copying business constants.

- [x] **Task 1.1 — Write quality-gate RED tests.** Cover required columns, ordering, duplicate dates, missing/invalid prices, zero volume handling, >7% unexplained move findings, gap findings without holiday assumptions, and preservation of the original raw BIGINT values.
- [x] **Task 1.2 — Run `tests.test_backtest_data_quality` and verify RED.** Expected: missing module/function failure.
- [x] **Task 1.3 — Implement quality gate and raw history loader.** Reject structural/non-positive-price errors; retain explicit warning records for unexplained moves/date gaps; use `text()` plus bound `ticker/start_date/end_date`; close raw connections in `finally`.
- [x] **Task 1.4 — Run quality tests GREEN.** Confirm malformed frames fail before any indicator function is called and raw prices remain unchanged.
- [x] **Task 1.5 — Write indicator adapter RED tests.** Patch existing indicator functions only at the boundary and assert every required indicator is called, the selected horizon uses the existing daily/weekly convention, and output labels map to the existing point scale.
- [x] **Task 1.6 — Implement the adapter by reuse.** Expose a narrow engine-facing adapter over `commons.technical_analysis`; do not duplicate calculations, mappings, or ADX behavior.
- [x] **Task 1.7 — Run indicator tests GREEN and perform SQL/data-integrity review.** Verify no SQL in protected files changed and no UI scaling helper is imported into raw engine calculations.

**Phase gate:** PASS — `tests.test_backtest_data_quality` and
`tests.test_backtest_indicators` pass 11/11 in Docker; existing Technical
Analyze regression tests pass 9/9; the quality report and indicator frame
contracts are frozen in FOCUS. Full discovery still has one pre-existing
`scripts` import error outside this feature.

---

## Phase 2: Combo Generation and Exact Signal Score

**Purpose:** Generate the bounded search space and reproduce the live Analyze technical score with subset selection, threshold crossing, and ADX gate modes.

**Files:**
- Create: `app/backtest_engine/signal_combos.py`
- Test: `tests/test_backtest_signal_combos.py`

**Interfaces:**
- `generate_signal_combos(horizon, include_theme) -> tuple[IndicatorCombo, ...]`.
- `score_combo(indicator_frame, combo) -> pandas.Series`.
- `detect_buy_crossings(score, threshold) -> pandas.Series[bool]`.
- Combo dimensions: Trend direction `(MA, MA cross)`, Momentum `(RSI, Stochastic)`, Volume `(OBV)`, Volatility `(ATR, Bollinger)`; ADX is a gate, never a fifth vote.

- [x] **Task 2.1 — Write RED tests.** Assert subset combinations are bounded/deterministic, equal group weights are fixed, soft ADX scales only trend direction, hard ADX excludes/renormalizes, threshold grid is respected, and a sustained score above threshold produces exactly one upward crossing.
- [x] **Task 2.2 — Run RED.** Expected: missing combo generator/score functions.
- [x] **Task 2.3 — Implement minimal combo generator and score.** Reuse Phase 1 adapters and existing technical metadata; reject empty dimension definitions and invalid thresholds.
- [x] **Task 2.4 — Run GREEN.** Verify deterministic combo ordering and exact crossing semantics.
- [x] **Task 2.5 — Self-review.** Confirm no flat indicator cross-product, no short signal, no weight search, and no duplicated live scoring formula.

**Phase gate:** PASS — Docker combo tests pass 4/4; cumulative backtest and
Technical regression tests pass 32/32; FOCUS records 270 no-theme and 810
theme-inclusive combos with deterministic ordering.

---

## Phase 3: Rolling Windows and Vectorized Long Trade Engine

**Purpose:** Walk every six-month window on a one-month stride and evaluate long BUY crossings with entry-at-next-open, ATR exits, SL-first same-bar tie-break, and max-hold timeout.

**Files:**
- Create: `app/backtest_engine/rolling_window.py`
- Test: `tests/test_backtest_rolling_window.py`
- Test: `tests/test_backtest_trade_execution.py`

**Interfaces:**
- `iter_rolling_windows(index, start_date, end_date, length_months=6, stride_months=1) -> iterator[Window]`.
- `run_combo_window(frame, combo, window) -> list[TradeEvent]`.
- `run_rolling_backtest(frame, combos, config) -> list[TradeEvent]`.
- Entry is next trading bar open after the crossing; SL/TP are based on signal-bar ATR and approved multipliers; if both are touched in one bar, SL wins; timeout exits at the max-hold-th bar close.

- [x] **Task 3.1 — Write window-coverage RED tests.** For a fixed synthetic date range, assert every generated window is deterministic, covers the configured range, advances by one month, and cannot be hand-selected/skipped.
- [x] **Task 3.2 — Write trade-execution RED fixtures.** Cover no-look-ahead future spike, next-open entry, SL hit, TP hit, same-bar SL priority, timeout resolution, insufficient next bar, and one crossing for a sustained score.
- [x] **Task 3.3 — Run both RED files.** Expected: missing rolling/trade functions.
- [x] **Task 3.4 — Implement pure vectorized execution.** Use NumPy/pandas arrays for future high/low/close scans; keep the per-event logic deterministic and avoid nested combo×window×permutation loops in the hot path.
- [x] **Task 3.5 — Run GREEN.** All rolling/trade fixtures pass, including the no-look-ahead regression and timeout status.
- [x] **Task 3.6 — Self-critique.** Review entry timing, ATR source date, same-bar priority, overlap behavior, and raw-price arithmetic before allowing validation work.

**Phase gate:** PASS — Docker rolling/trade tests pass 7/7; cumulative
backtest and Technical regression tests pass 39/39; vectorized future-bar
scan and synthetic event rows are deterministic with no future score access.

---

## Phase 4: VN-Index Theme Alignment

**Purpose:** Add optional no-theme, AND-theme, and OR-theme variants without future-date leakage.

**Files:**
- Create: `app/backtest_engine/vnindex_theme.py`
- Test: `tests/test_backtest_vnindex_theme.py`

**Interfaces:**
- `align_vnindex_asof(ticker_frame, vnindex_frame) -> pandas.DataFrame` uses only VN-Index dates on or before ticker signal dates.
- `build_vnindex_confirmation(vnindex_frame, horizon) -> pandas.Series[bool]` reuses the existing MA function with daily SMA(50)/weekly SMA(20).
- `combine_theme_signal(ticker_signal, theme_signal, mode) -> pandas.Series[bool]` implements exact AND/OR.

- [x] **Task 4.1 — Write RED tests.** Cover no-theme identity, backward/as-of date alignment, no future VN-Index value, daily/weekly SMA periods, AND, OR, and accepted OR-only theme triggers.
- [x] **Task 4.2 — Run RED.** Expected: missing theme module/functions.
- [x] **Task 4.3 — Implement as-of join and theme combiner.** Reuse existing MA logic; never inner-join a future VN-Index row into a past ticker row.
- [x] **Task 4.4 — Run GREEN and review.** Confirm theme variants are evaluated independently and no theme benefit is assumed.

**Phase gate:** PASS — Docker theme tests pass 5/5; cumulative focused suite
passes 44/44; FOCUS records no-look-ahead evidence and the theme experiment
does not assume benefit.

---

## Phase 5: Statistical Validation and Certification

**Purpose:** Control multiple testing, apply the min-n gate, select exactly one current certified set for each metric, and persist the two theme files safely.

**Files:**
- Create: `app/backtest_engine/validation.py`
- Create: `app/backtest_engine/certify.py`
- Create: `app/backtest_engine/persistence.py`
- Test: `tests/test_backtest_validation.py`
- Test: `tests/test_backtest_certification.py`
- Test: `tests/test_backtest_persistence.py`

**Interfaces:**
- `calculate_deflated_sharpe(returns, trials, ...) -> float` / PSR-compatible score.
- `moving_block_permutation_test(returns, count=1000, seed=42, block_size=20) -> PermutationResult`.
- `validate_candidates(trade_events, combos, config) -> list[ValidatedCandidate]` runs the cheap Deflated-Sharpe pre-filter for every combo and permutations only for survivors.
- `certify_top_sets(candidates, min_n=30) -> dict[str, dict]` returns `win_rate`, `profit`, and `sharpe` sets or an explicit empty result when no candidate qualifies.
- `save_certified_signals(ticker, signal_sets, theme_variant, output_dir) -> str` atomically overwrites one JSON file for the selected ticker/theme.
- JSON schema includes combo parameters, horizon/theme/VN-Index condition, n, hit rate, profit, Sharpe/Deflated Sharpe, p-value, date range, and `certified_at`.

- [x] **Task 5.1 — Write RED math tests.** Use a hand-computed/reference fixture for Sharpe/PSR, min-n, p-value bounds, block preservation, and fixed-seed determinism.
- [x] **Task 5.2 — Run RED.** Expected: missing validation functions.
- [x] **Task 5.3 — Implement validation minimally.** Never select on raw Sharpe/win rate before the Deflated-Sharpe filter; use the fixed seed and block size; keep all trial metadata for audit output.
- [x] **Task 5.4 — Run validation GREEN.** Confirm no permutation runs for rejected candidates and identical seed/input yields identical output.
- [x] **Task 5.5 — Write certification/persistence RED tests.** Cover pooled n gate, top-one-per-metric selection, empty state, exact two filenames, overwrite behavior, atomic write, schema completeness, and JSON round-trip byte-equivalent normalized content.
- [x] **Task 5.6 — Implement certification and persistence.** Use a temporary file plus atomic replace; never create timestamped historical copies; keep JSON as source of truth.
- [x] **Task 5.7 — Run GREEN and self-review.** Verify the min-n gate is before certification, theme variants cannot overwrite each other, and no DB schema is introduced.

**Phase gate:** PASS — Phase 5 tests pass 9/9; cumulative backtest and Technical regression tests pass 53/53 in Docker; a synthetic run produces three metric outputs or a safe explicit empty state; compile and protected-boundary checks pass.

---

## Phase 6: Early Warning Replay and Diff

**Purpose:** Reuse the exact certified combo against fresh 3–6 month data and report current state plus certified-vs-current differences.

**Files:**
- Create: `app/backtest_engine/early_warning.py`
- Test: `tests/test_backtest_early_warning.py`

**Interfaces:**
- `check_current_situation(ticker, metric="all", theme_variant="no-background-theme", engine=None, output_dir=None) -> dict`.
- States: `no_signal`, `active`, `fired_open`, `fired_timeout_resolved`; background-theme output also includes `confirmed`/`not_confirmed`.

- [x] **Task 6.1 — Write RED replay tests.** Cover loading each theme file, same scoring/evaluator path as rolling backtest, data-quality rejection, no signal, active signal, still-open signal, timeout resolution, theme suppression, and certification age.
- [x] **Task 6.2 — Run RED.** Expected: missing early-warning function.
- [x] **Task 6.3 — Implement replay by composition.** Call the same indicator, score, theme, and trade-exit functions; do not copy their formulas. Build the explicit `certified`, `current`, and `diff` sections.
- [x] **Task 6.4 — Run GREEN and drift review.** The historical replay fixture must reproduce the rolling engine's state exactly; any mismatch blocks Phase 7.

**Phase gate:** PASS — Phase 6 replay tests pass 7/7; cumulative backtest and Technical regression tests pass 60/60 in Docker; fresh-data quality rejection, all four ticker states, timeout parity, both theme modes, persisted-rule validation, certification age, compile, and protected-boundary checks pass.

---

## Phase 7: Offline Job Runner and Status Polling Contract

**Purpose:** Make full runs safe for background execution and observable by the UI without blocking Streamlit.

**Files:**
- Create: `app/backtest_engine/job_runner.py`
- Test: `tests/test_backtest_job_runner.py`

**Interfaces:**
- `submit_backtest(config, engine_factory, status_dir) -> str` returns immediately with a job id.
- `run_backtest_job(config, engine_factory, status_dir) -> JobStatus` runs the offline pipeline and writes atomic JSON status updates.
- `read_job_status(job_id, status_dir) -> JobStatus`.

- [x] **Task 7.1 — Write RED lifecycle tests.** Assert submit returns before work completion, status transitions queued→running→done/failed, progress is monotonic, errors are persisted, worker count is configurable with default six, and no Streamlit import occurs.
- [x] **Task 7.2 — Run RED.** Expected: missing runner/status functions.
- [x] **Task 7.3 — Implement background orchestration.** Use a spawned `ProcessPoolExecutor` with configurable workers and JSON sidecar status because no schema/Docker change is approved; write status atomically and never run the full pipeline inline in a page callback.
- [x] **Task 7.4 — Run GREEN and inspect process cleanup.** Confirm failed jobs do not leave misleading `running` status and status files are readable after process exit.

**Phase gate:** PASS — Phase 7 tests pass 3/3; cumulative backtest and Technical regression tests pass 63/63 in Docker; lifecycle, monotonic progress, atomic status, spawned worker pool, worker-default, compile, and protected-boundary checks pass.

---

## Phase 8: Standalone Backtest Page

**Purpose:** Add the approved standalone page after engine contracts are proven; the page only submits jobs, polls status, renders persisted results, and downloads artifacts.

**Files:**
- Create: `app/pages/backtest_lab.py`
- Modify: `app/main.py` navigation only
- Test: `tests/test_backtest_page.py`

**Interfaces:**
- UI controls: ticker, time range/custom dates, six-month window/one-month stride display, horizon, theme toggle/mode, run button.
- Output: queued/running/done/failed status, three metric result sections, combo breakdown, entry/SL/TP, n, hit rate, Deflated Sharpe, p-value, equity curve, explicit empty state, JSON/MD download.

- [x] **Task 8.1 — Write RED page helper/AppTest tests.** Assert controls, validation messages, submit-only behavior, polling states, empty state, three result sections, artifact download, and no direct long-running engine call in the page callback.
- [x] **Task 8.2 — Run RED.** Expected: missing page module/helpers/navigation.
- [x] **Task 8.3 — Implement minimal standalone page.** Reuse existing Plotly chart conventions; keep UI prices labeled k VND while persisted/backtest prices remain raw; do not modify existing Analyze/Technical pages.
- [x] **Task 8.4 — Run GREEN.** Use Streamlit AppTest/headless smoke in Docker; verify no page errors, warnings, or blocking behavior.

**Phase gate:** PASS — Phase 8 page/AppTest tests pass 5/5; pipeline composition and cumulative backtest/Technical regression tests pass 69/69 in Docker; navigation, submit-only behavior, status polling, result/empty states, downloads, compile, and protected-boundary checks pass.

---

## Phase 9: Profiling, Full Verification, and Documentation Handoff

**Purpose:** Prove correctness/performance on the target Docker environment and close all documentation loops.

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `ai-context/architecture.md` only if implementation paths differ from this plan
- Create: `docs/superpowers/reports/2026-08-02-backtest-engine-verification.md`

- [x] **Task 9.1 — Baseline profile before optimization.** Run one full 15-year ticker sweep, record wall-clock time, peak RSS, worker count, combo count, window count, and excluded quality rows; do not claim a target before measuring.
- [x] **Task 9.2 — Run full Docker suite.**

  `docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest discover -s /app/tests -p "test_*.py"`

  Expected: zero feature failures; record the exact count and any pre-existing
  environment/import exception separately.

- [x] **Task 9.3 — Run boundary and whitespace checks.** `git diff --check` must exit cleanly apart from known line-ending warnings; protected boundary diff must be empty.
- [x] **Task 9.4 — Load implementation-review skill and self-critique.** Review logic, SQL, BIGINT handling, performance, process cleanup, comments, no-look-ahead, and UI blocking; fix all findings before handoff.
- [x] **Task 9.5 — Update FOCUS/current-status/report.** Mark only verified phases complete, document remaining open questions/technical debt, and keep the historical full-history SQL warning separate.

**Final acceptance:** All focused phase gates pass; profile evidence, boundary/whitespace checks, and documentation are complete. Full Docker discovery is 194/195 because the container does not mount the pre-existing top-level `scripts` helper package, so that unrelated import error remains documented.

---

## Plan Self-Review

- **Spec coverage:** Every BACKTEST_ENGINE deliverable maps to Phases 1–9: quality gate, reused indicators, combo search, rolling coverage, validation, min-n certification, VN-Index variants, background status, overwrite persistence, exact replay, staleness, standalone UI, and performance evidence.
- **TDD coverage:** Every implementation phase names failing tests, RED command, minimal implementation, GREEN command, and a phase gate before advancement.
- **Ponytail review:** The plan reuses the existing indicator/scoring registry, keeps JSON sidecars instead of introducing a database schema, and keeps the UI thin; no new dependency or Docker change is proposed.
- **Known planning gates:** Gap severity/calendar semantics remain explicit Phase 1 policy; the exact PSR/Deflated-Sharpe reference calculation is now captured by the Phase 5 reference test and implementation.
- **Boundary review:** No task modifies `common_queries.py`, data-preparation scaling/connection logic, credentials, Docker files, or `IMPLEMENTED.md`.
- **Placeholder scan:** No `TODO`, `TBD`, or vague “handle appropriately” steps remain; unresolved empirical outcomes are explicit acceptance/report outputs, not hidden assumptions.

## Current Stopping Point

All planned phases are complete. The standalone Backtest page is wired into
legacy navigation, submits the environment-backed pipeline through the spawned
configurable `ProcessPoolExecutor`, polls status, renders certified
results/empty states, and provides JSON/Markdown downloads. The 15-year SSI
profile baseline is recorded in the verification report. Focused Docker
coverage is 69/69; full discovery is 194/195 because Docker does not mount the
pre-existing top-level `scripts` helper package. No commit was created.
