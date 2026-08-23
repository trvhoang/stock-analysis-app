# Validate Signals Advice and Position Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development`
> or `executing-plans` to execute one checked task at a time. Do not advance a
> task until its validation gate passes.

**Goal:** Implement Backtest Lab's `Validate Signals` tab as a manual decision
aid that compares current ticker conditions to saved signal sets and retains
confirmed position history per ticker/theme/metric.

**Architecture:** Reuse current certified-signal replay; do not create a second
backtest path. Extend replay with current raw score/quote/ATR context, calculate
matching/advice in a small pure service, and store user-confirmed positions in
separate atomic JSON history files. A native-horizon monitor evaluates pinned
risk levels. The Streamlit page reads, displays, and requires explicit BUY or
SELL confirmations only.

**Tech Stack:** Python 3.12, Streamlit, pandas, SQLAlchemy, PostgreSQL,
standard-library `Decimal`/`json`/`uuid`, Docker `unittest`, Streamlit AppTest.

## Global Constraints

- Reuse existing `load_ticker_history()`, `get_engine_with_retry()`,
  `build_indicator_frame()`, `score_combo()`, `evaluate_current_combo()`,
  `to_weekly_ohlcv()`, certified artifact persistence, and price utilities.
- Do not modify `app/common_queries.py`, data ingestion/BIGINT scaling,
  credentials, Docker, `IMPLEMENTED.md`, or commit history. Add no dependency
  and no database table.
- Database/engine values remain raw BIGINT. UI display/input uses `k VND` and
  converts in Python only; export retains raw original values.
- Long-only is immutable. This feature has no short entry, technical SELL
  signal, automatic order, or automatic close.
- Manual BUY date is locked to each selected validation as-of date. The page
  uses that as-of raw ATR with the user-confirmed raw BUY price to freeze its
  engine-standard ATR exit snapshot; mixed-as-of selections are rejected.
- Signal files are immutable inputs: validation must never call job submission,
  backtest pipeline, certification, or `save_certified_signals()`.
- Exactly one open position may exist per `(ticker, theme_variant, metric)`;
  a position freezes its signal snapshot and risk values against later artifact
  overwrites.
- Match formula: `min(100, current_score / threshold_score_buy * 100)`.
  A required unconfirmed VN-Index theme is ineligible. Classify `<70` Observe,
  `70–<85` Nearly match, `>=85` Closely match.
- SELL is merely permitted when native holding bars exceed 60% of pinned
  max-hold, or current raw close is at/beyond `SL * 1.05` or `TP * 0.95`.
  It remains manual.
- Swing is daily only. Mid-term is weekly only, uses 16 inclusive bars, and
  first normal exit is on the next weekly bar. Task 0 proves the actual
  buy-date/weekly-bar mapping before code is written.

## File Map

| File | Role |
|---|---|
| `docs/superpowers/reports/2026-08-07-validate-signals-spike.md` | Task 0 evidence and final temporal mapping. |
| `app/backtest_engine/early_warning.py` | Replay current raw context efficiently. |
| `app/backtest_engine/validation_advice.py` | Pure matching, classification, and advice assembly. |
| `app/backtest_engine/position_store.py` | Validated atomic position history JSON. |
| `app/backtest_engine/position_monitor.py` | Native-clock holding/exit/Sell eligibility. |
| `app/commons/price_utils.py` | `k VND` input to raw price conversion. |
| `app/pages/backtest_lab.py` | Validate tab and manual forms; Collect unchanged. |
| `tests/test_backtest_early_warning.py` | Current-context/replay reuse coverage. |
| `tests/test_backtest_validation_advice.py` | Match/advice/theme/missing-artifact coverage. |
| `tests/test_backtest_position_store.py` | Position schema/atomic/duplicate coverage. |
| `tests/test_backtest_position_monitor.py` | Daily/weekly holding and Sell-rule coverage. |
| `tests/test_backtest_page.py`, `tests/test_price_utils.py` | AppTest and price boundary coverage. |

---

### Task 0: Spike actual artifact, price, and timeframe contracts

**Files:**
- Create: `docs/superpowers/reports/2026-08-07-validate-signals-spike.md`
- Modify: `FOCUS.md`
- Test: `tests/test_backtest_early_warning.py`, `tests/test_backtest_trade_execution.py`, `tests/test_backtest_vnindex_theme.py`, `tests/test_price_utils.py`

**Produces:** A read-only report that captures artifact availability, current
replay fields/query count, price representations, and a no-look-ahead
Mid-term date/bar contract.

- [x] **Step 1: Inspect without mutation.**

  Read current FPT artifacts and a non-empty temporary fixture separately.
  Record artifact `empty` state, stored metric/horizon/theme metadata, and
  `check_current_situation()` response fields. Do not submit a Backtest job or
  overwrite `ticker-signals`.

- [x] **Step 2: Verify existing contract baseline.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_early_warning tests.test_backtest_trade_execution tests.test_backtest_vnindex_theme tests.test_price_utils -v
  ```

  Expected: all named modules pass. Record exact test count and any existing
  Docker limitation in the spike report.

- [x] **Step 3: Prove the Mid-term as-of boundary.**

  Build a temporary daily fixture ending mid-week with a BUY date inside that
  week. Record `buy_date`, `as_of_date`, source rows used, and weekly bars
  counted. If any row later than `as_of_date` contributes to the result, stop
  and ask the user before production implementation.

- [x] **Step 4: Freeze the rule and phase gate.**

  Record the chosen rule: actual BUY date must be a ticker trading date; Swing
  counts actual daily rows on/after it; Mid-term maps the date to its weekly
  period and counts only periods containing source rows through as-of. Never
  use a daily bar to calculate a Mid-term exit. Update `FOCUS.md` only after
  passing evidence exists.

### Task 1: Extend replay and implement matching-level primitives

**Files:**
- Modify: `app/backtest_engine/early_warning.py`
- Create: `app/backtest_engine/validation_advice.py`
- Modify: `tests/test_backtest_early_warning.py`
- Create: `tests/test_backtest_validation_advice.py`

**Interfaces produced:**

```python
def match_level(current_score: float, threshold_score_buy: int,
                theme_eligible: bool) -> float: ...
def classify_match(level: float) -> str: ...
def validate_saved_signals(ticker: str, include_theme: bool, engine,
                           signal_dir: str = "ticker-signals") -> dict[str, object]: ...
```

Each replay result exposes raw `current_score`, `latest_close`, `latest_atr`,
and actual `as_of_date`, alongside existing replay state/entry/SL/TP fields.

- [x] **Step 1: Write RED tests.**

  Assert a canonical synthetic frame exposes latest score, close, ATR, and
  source as-of date even without a crossing. Assert an all-metrics artifact
  loads/builds one ticker frame per horizon, not one per metric; reject a
  malformed mixed-horizon artifact. Add exact threshold assertions:

  ```python
  assert match_level(49, 70, True) == 70.0
  assert classify_match(69.99) == "observe"
  assert classify_match(70.0) == "nearly_match"
  assert classify_match(84.99) == "nearly_match"
  assert classify_match(85.0) == "closely_match"
  assert match_level(80, 70, False) == 0.0
  ```

- [x] **Step 2: Verify RED.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_early_warning tests.test_backtest_validation_advice -v
  ```

  Expected: FAIL because raw context and validation-advice implementation do
  not exist.

- [x] **Step 3: Implement shared replay only once.**

  Keep `score_combo()` as the score authority. Return latest raw context from
  `evaluate_current_combo()` (or one adjacent shared helper); do not re-score
  in the page. Refactor `check_current_situation()` so all non-null metric sets
  in an artifact reuse one loaded/validated ticker frame, and themed artifacts
  reuse one VN-Index confirmation frame. Reject inconsistent ticker/theme/
  horizon metadata. Implement the capped, two-decimal matching formula and
  exact classification. Missing, unreadable, empty, or null-metric files return
  explicit unavailable data, never invented scores.

- [x] **Step 4: Verify GREEN and read-only boundary.**

  Re-run Step 2. Mock and assert no call to pipeline, job submission,
  certification, or signal persistence. Run:

  ```powershell
  docker exec stock_app python -m compileall -q app/backtest_engine
  ```

  Update `FOCUS.md` after all checks pass.

### Task 2: Convert UI prices safely and persist manual positions atomically

**Files:**
- Modify: `app/commons/price_utils.py`
- Create: `app/backtest_engine/position_store.py`
- Modify: `tests/test_price_utils.py`
- Create: `tests/test_backtest_position_store.py`

**Interfaces produced:**

```python
def price_from_ui_k_vnd(value: object) -> int: ...
def load_position_history(ticker: str, theme_variant: str, metric: str,
                          positions_dir: str = "backtest-positions") -> dict[str, object]: ...
def open_position(..., positions_dir: str = "backtest-positions") -> dict[str, object]: ...
def close_position(..., positions_dir: str = "backtest-positions") -> dict[str, object]: ...
```

Each tuple has a file at
`backtest-positions/<TICKER>/<TICKER>_positions_<theme_variant>_<metric>.json`.
Schema version 1 holds an append-only `history` with one active record maximum.
A record stores id, tuple, status, frozen certified signal snapshot,
certification timestamp, entry-context matching/current price, actual raw BUY
price/date/timestamp, raw ATR/SL/TP/max-hold, and later actual raw SELL
price/date/timestamp/reason. Holding numbers are always derived, never stored.

- [x] **Step 1: Write RED tests.**

  Assert `"50.3" -> 50300`, `"121.35" -> 121350`; reject invalid,
  non-positive, and greater-than-three-decimal prices. Assert opening deep
  copies a raw-integer snapshot, prevents a second open record for the same
  tuple, and allows a new open after manual close. Assert malformed schema,
  bad date, non-long direction, close before BUY, and non-positive raw prices
  fail. Assert atomic writes leave no temporary file.

- [x] **Step 2: Verify RED.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_price_utils tests.test_backtest_position_store -v
  ```

  Expected: FAIL because conversion and position storage do not exist.

- [x] **Step 3: Implement minimal validated storage.**

  Convert with `Decimal(str(value)) * 1000` and require a positive integral raw
  result. Reuse current ticker validation and the atomic temp-file/`fsync`/
  `os.replace` pattern under the separate position root. Use `uuid4().hex` for
  identity. `close_position()` updates only the named open record from an
  explicit user fill; it never derives a sell price.

- [x] **Step 4: Verify GREEN and snapshot immutability.**

  Re-run Step 2; confirm a later signal-artifact replacement cannot mutate an
  open position snapshot. Run `git diff --check` and inspect protected paths.
  Update `FOCUS.md` after passing.

### Task 3: Monitor pinned positions without mixing horizons

**Files:**
- Create: `app/backtest_engine/position_monitor.py`
- Create: `tests/test_backtest_position_monitor.py`
- Modify: `app/backtest_engine/timeframes.py` only if Task 0 proves a single
  as-of weekly-period helper is necessary; otherwise do not modify it.

**Interface produced:**

```python
def monitor_position(position: dict[str, object], raw_history: pd.DataFrame,
                     as_of_date: object) -> dict[str, object]: ...
```

It returns raw latest close, holding bars, suggested holding bars, holding
ratio, SL/TP proximity, timeout state, `sell_allowed`, and explicit reasons.

- [x] **Step 1: Write RED lifecycle tests.**

  With a 15-row Swing fixture, assert inclusive holding first exceeds 60% at
  bar 10—not bar 9. With 16 weekly bars, assert Mid-term first exceeds 60% at
  week 10, never creates a same-week exit, and remains weekly-only. Assert SELL
  permission at/beyond `close <= SL * 1.05` and `close >= TP * 0.95`; assert
  no permission at/below 60% with neither proximity condition. Assert timeout
  is reported but does not close storage.

- [x] **Step 2: Verify RED.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_position_monitor -v
  ```

  Expected: FAIL because no monitor exists.

- [x] **Step 3: Implement the native-clock monitor.**

  Validate OHLCV first. Swing counts actual daily trading bars from verified
  BUY date through as-of. Mid-term uses Task 0's tested weekly-period rule and
  never inspects a daily row after as-of or calculates daily SL/TP behavior.
  Compare latest raw close only to stored raw risk levels. Keep timeout
  informational; only `close_position()` changes state.

- [x] **Step 4: Verify GREEN and no look-ahead.**

  Re-run Step 2, mutate rows after as-of, and assert unchanged monitor output.
  Re-run existing Swing/Mid-term trade lifecycle tests. Update `FOCUS.md` only
  after all pass.

### Task 4: Compose variant/metric advice with position state

**Files:**
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `tests/test_backtest_position_monitor.py` only for service-boundary fixtures

**Produces:** Page-ready, separately labelled no-theme/themed results per
metric. Each result is unavailable, Observe, BUY eligible, or has frozen
open-position/monitor state.

- [x] **Step 1: Write RED composition tests.**

  Use three metric artifacts to assert `<70` Observe and `>=70` BUY eligibility
  without an open position. Assert a theme-ineligible high-score set cannot
  advise BUY. Assert an open `win_rate` tuple neither blocks `profit` nor a
  different theme. Assert open records show current match plus monitor SELL
  status without write calls. Assert checkbox off requests no-theme only; on
  requests both variants independently.

- [x] **Step 2: Verify RED.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_position_monitor -v
  ```

- [x] **Step 3: Implement deterministic composition.**

  Evaluate variants independently; they need not have equal horizons. Reuse
  one history/frame per artifact horizon, loading older history only when an
  open BUY date requires it. Display unavailable artifact states clearly. When
  current artifact differs from a frozen position, render both identities but
  monitor only the frozen position. Never choose a best metric automatically;
  expose all BUY-eligible sets for user multi-selection.

- [x] **Step 4: Verify GREEN and no writes.**

  Re-run Step 2 with mocks proving evaluation calls neither signal persistence
  nor position open/close. Re-run Task 1 replay tests and update `FOCUS.md`.

### Task 5: Populate the Streamlit Validate Signals tab

**Files:**
- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Consumes:** Task 1–4 services and the existing injected page `engine`.

- [x] **Step 1: Write RED AppTests.**

  Inject validation/store callbacks as existing job functions are injected.
  Assert a Ticker field, unchecked theme checkbox, and `Validate saved signals`
  button—without job submission. Assert no-theme vs both-variant rendering;
  clear unavailable-artifact messaging; metric multi-selection plus one `k
  VND` BUY price/date confirmation; and an open-position view with holding,
  SL/TP, match, reasons, and explicit SELL price/date confirmation.

- [x] **Step 2: Verify RED.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page -v
  ```

  Expected: FAIL because the tab is currently static information only.

- [x] **Step 3: Implement minimum UI orchestration.**

  Stop discarding injected `engine`; query only after user clicks Validate.
  Keep request identity/result in `st.session_state` so confirmation reruns
  cannot apply stale ticker/theme data. Display all raw prices with
  `prepare_price_for_output(..., PRICE_OUTPUT_UI)` and labels `Actual BUY
  price (k VND)`/`Actual SELL price (k VND)`. Use tuple-derived widget keys.
  Apply one submitted ticker price/date to every checked eligible tuple; sell
  only the selected open record. Rerun after feedback. Do not add refresh,
  auto-trading, or synchronous backtest execution.

- [x] **Step 4: Verify GREEN and Collect regression.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_job_runner tests.test_backtest_early_warning tests.test_backtest_validation_advice -v
  ```

  Expected: pass. Assert Collect still has its exact job controls, automatic
  polling, and no manual refresh button. Update `FOCUS.md` after passing.

### Task 6: Complete evidence, review, and documentation

**Files:**
- Modify: `FOCUS.md`, `ai-context/current-status.md`, and spike report
- Create: `docs/superpowers/reports/2026-08-07-validate-signals-verification.md`

- [x] **Step 1: Run explicit Backtest regression gate.**

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_contracts tests.test_backtest_indicators tests.test_backtest_signal_combos tests.test_backtest_trade_execution tests.test_backtest_rolling_window tests.test_backtest_pipeline tests.test_backtest_early_warning tests.test_backtest_validation tests.test_backtest_vnindex_theme tests.test_backtest_diagnostics tests.test_backtest_validation_advice tests.test_backtest_position_store tests.test_backtest_position_monitor tests.test_backtest_page tests.test_price_utils -v
  ```

  Expected: every named module passes. Do not treat generic discovery as the
  gate until its pre-existing topology limitation is separately repaired.

- [x] **Step 2: Compile and inspect boundaries.**

  ```powershell
  docker exec stock_app python -m compileall -q app/backtest_engine app/pages
  git diff --check
  git diff -- app/common_queries.py app/data_preparation.py app/main.py docker Dockerfile docker-compose.yml
  ```

  Expected: compile/whitespace pass and no new protected-boundary diff. Do not
  commit.

- [x] **Step 3: Run live-safe manual validation.**

  Use a known non-empty artifact or a temporary output directory—never replace
  a current production signal file. Verify no-theme and themed results,
  multi-set BUY storage, manual SELL closure, raw/UI price conversion, and
  retained closed history. Record exact results and cleanup.

- [x] **Step 4: Self-critique before completion.**

  Load `ai-skills/skill-implementation-review.md`, review all global
  constraints plus session-state and user-input branches, correct any finding,
  and rerun the affected gate. Only then mark WIP complete.

## Self-Review

- Tasks 1/4 cover score/theme/match/Observe/BUY; Tasks 2/5 cover multi-selected
  separate positions and raw UI-price conversion; Task 3 covers native holding,
  60%, and ±5% SELL behavior; Task 5 covers explicit BUY/SELL UI; Task 6
  records proof.
- Task 0 blocks the only unresolved Mid-term date-mapping ambiguity, and Tasks
  1/3 include future-row mutation tests. No task mixes daily exits into
  Mid-term.
- Scope intentionally excludes order execution, P/L analytics, sizing,
  multi-ticker scans, database migrations, and re-certification.
