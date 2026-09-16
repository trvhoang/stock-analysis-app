# Project-wide VN-Index Trading Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by
> task. No Git action or commit is authorized for this project.

**Goal:** Make every production technical-indicator frame use the VN-Index
weekday session calendar before indicator calculation, with fail-closed source
errors and transparent missing-session diagnostics.

**Architecture:** A small shared calendar adapter creates and fingerprints the
usable VN-Index session set, then returns a filtered ticker frame and exact
diagnostics. Backtest, Flexible, and legacy technical adapters consume it before
their existing indicator logic. Existing delta CTE/statistical analysis remains
untouched.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy, PostgreSQL, Streamlit,
unittest, Docker Compose.

## Global Constraints

- Use `sqlalchemy.text()`, `engine.raw_connection()`, and `%(param)s` bindings
  for every new SQL query.
- Preserve raw BIGINT inputs; scale only at existing display boundaries.
- Use `Asia/Ho_Chi_Minh` for current-time bounds.
- Do not modify `common_queries.py`, credentials, Docker, or add a dependency.
  The approved Task 0 is the only ingestion change.
- Every production indicator path filters before RSI, MA, ADX, ATR,
  Stochastic, OBV, Bollinger, Alligator, execution, or resampling.
- A missing weekday VN-Index print is named `assumed_non_session`; no raw
  ticker fallback is allowed.
- Preserve schema-5; stale Backtest evidence becomes the existing atomic
  `requires_regeneration` marker. Flexible starts fresh after the reset.

### Task 0: Acknowledged invalid-session cleanup and validity scan

**Files:**

- Modify: `app/pages/data_preparation.py`
- Modify: `tests/test_data_preparation.py`

**Produces:** Every user-triggered Get data transaction removes only the five
acknowledged invalid session dates (`2023-08-26`, `2025-05-04`, `2025-05-11`,
`2026-02-07`, `2026-03-08`), then verifies that no persisted Saturday/Sunday
row remains before its single commit.

- [x] Write red tests for exact-date cleanup, all-table invalid-session scan,
  and rollback when the post-cleanup scan finds a remaining invalid date.
- [x] Implement fixed `sqlalchemy.text()` statements and raw-connection
  bindings. Keep the cleanup after source finalization and before commit so it
  is atomic with the input refresh.
- [x] Add progress phases for cleanup and scan; fail the refresh with complete
  date/row-count/ticker diagnostics if any invalid session remains.
- [x] Run the Docker data-preparation gate; it passes 13/13 after the five-date
  calendar update.
- [ ] On the next user-triggered Get data transaction, confirm the five
  acknowledged dates are absent and the post-cleanup all-table scan is empty.

---

### Task 1: Shared canonical calendar, filtering, and safe diagnostics

**Files:**

- Create: `app/commons/trading_calendar.py`
- Create: `tests/test_trading_calendar.py`
- Modify: `app/backtest_engine/evidence.py`
- Modify: `tests/test_backtest_evidence.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class VNIndexCalendar:
    sessions: tuple[date, ...]
    assumed_non_sessions: tuple[date, ...]
    first_date: date
    last_date: date
    fingerprint: str

class VNIndexCalendarUnavailable(ValueError):
    reason: str
    missing_sessions: tuple[date, ...]

def build_vnindex_calendar(vnindex_raw: pd.DataFrame, *, start: date,
                           end: date) -> VNIndexCalendar: ...
def restrict_to_vnindex_sessions(ticker_raw: pd.DataFrame,
                                 calendar: VNIndexCalendar) -> tuple[pd.DataFrame, tuple[date, ...]]: ...
def load_calendar_aligned_history(engine: object, ticker: str, *, start: date,
                                  end: date) -> tuple[pd.DataFrame, VNIndexCalendar, tuple[date, ...]]: ...
```

- [ ] Write red tests for a missing weekday VN-Index row excluding a same-date
  ticker row, immutable/sorted sessions, deterministic fingerprint, weekend
  VN-Index rejection, duplicate/invalid VNI rejection, and zero overlap.
- [ ] Run the targeted tests and observe expected missing-import failure:

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_evidence tests.test_trading_calendar
  ```

- [ ] Implement the shared dataclasses, raw validation, weekday gap derivation,
  exact full missing-date formatting, and calendar-filtering copy. Use one
  bound `text()` query per ticker/VN-Index source; do not build SQL with
  concatenated values.
- [ ] Re-export `canonical_vnindex_calendar` and
  `restrict_to_canonical_sessions` from Backtest evidence as thin compatibility
  wrappers, then make `assess_evidence()` use the central calendar and filtered
  rows.
- [ ] Re-run Task 1 tests and current evidence tests; expect pass.

### Task 2: Backtest source/replay/calendar identity integration

**Files:**

- Modify: `app/backtest_engine/pipeline.py`
- Modify: `app/backtest_engine/early_warning.py`
- Modify: `app/backtest_engine/research_optimizer.py`
- Modify: `app/backtest_engine/diagnostics.py`
- Modify: `app/backtest_engine/position_risk.py`
- Modify: `tests/test_backtest_pipeline.py`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `tests/test_backtest_position_risk.py`
- Modify: `tests/test_backtest_evidence.py`

**Consumes:** Task 1 calendar adapter.

**Produces:** Every Backtest indicator/replay/risk/research path builds frames
only from calendar-filtered ticker daily rows and the same validated VN-Index
source.

- [ ] Write red tests proving one excluded ticker row changes the indicator
  input, early-warning stale evidence becomes `requires_regeneration`, theme
  calculation uses the identical calendar, and no-signal risk uses filtered
  daily/weekly bars.
- [ ] Run those tests; observe failure from raw ticker input still reaching
  `build_rulebook_frame()`.
- [ ] Implement one source-preparation boundary used by single/batch collect,
  fresh replay, research, diagnostics, and position risk. Preserve existing
  common-as-of, coverage/gap, raw audit, and atomic marker semantics. Convert a
  calendar-unavailable replay failure into a safe marker reason rather than an
  uncaught UI error.
- [ ] Test Swing and completed W-FRI Mid-term: a Friday assumed non-session
  creates no synthetic daily or weekly bar, and an insufficient filtered
  warm-up remains unknown/not-ready.
- [ ] Re-run focused Backtest suites; expect pass.

### Task 3: Legacy Analyze/API/Technical calendar adapters

**Files:**

- Modify: `app/commons/technical_analysis.py`
- Modify: `app/commons/technical_horizon.py`
- Modify: `app/commons/common_functions.py`
- Modify: `app/pages/analyze_visualization.py`
- Modify: `app/pages/technical_visualization.py`
- Modify: `tests/test_technical_analysis.py`
- Modify: `tests/test_technical_horizon.py`
- Modify: `tests/test_technical_snapshot.py`
- Modify: `tests/test_historical_technical_context.py`
- Modify: `tests/test_common_functions.py`

**Consumes:** Task 1 calendar adapter.

**Produces:** Legacy and horizon UI/API technical reports compute only on
filtered history and render an exact safe calendar error with all bounded
missing dates.

- [ ] Write red tests for daily and weekly `fetch_data()` filtering before
  resampling, horizon source filtering before Backtest frame construction,
  historical context filtering before RSI/Stochastic/MA, and UI-safe no-
  overlap error detail.
- [ ] Run targeted tests; observe existing raw-only fetch behavior fails the
  desired assertions.
- [ ] Implement calendar-aligned source loading while retaining raw BIGINT until
  each existing UI conversion. Keep pure calculators unchanged. Thread engine
  and necessary bounds to historical context without touching delta SQL.
- [ ] Make Streamlit render the typed unavailable message plus full missing
  ISO-date detail. Analyze/Suggestion return their established safe failure for
  an unavailable technical snapshot rather than compute unfiltered data.
- [ ] Re-run technical, Analyze, API-consumer, and UI tests; expect pass.

### Task 4: Flexible Rulebook fresh calendar-bound history

**Files:**

- Modify: `app/flexible_rulebook/history.py`
- Modify: `app/flexible_rulebook/features.py`
- Modify: `app/flexible_rulebook/service.py`
- Modify: `app/flexible_rulebook/discovery_activation.py`
- Modify: `app/flexible_rulebook/current_scan.py`
- Modify: `tests/test_flexible_rulebook_history.py`
- Modify: `tests/test_flexible_rulebook_features.py`
- Modify: `tests/test_flexible_rulebook_service.py`
- Modify: `tests/test_flexible_rulebook_current_scan.py`

**Consumes:** Task 1 calendar adapter and the already empty Flexible runtime
roots.

**Produces:** `HistorySnapshot` and feature receipts use a calendar-filtered
frame, calendar fingerprint, and a new quality revision; all post-reset cache
and qualification evidence is fresh.

- [ ] Write red tests for changed fingerprint when VNI calendar changes even if
  ticker OHLCV is unchanged, rejected no-overlap with full missing-session
  diagnostics, feature values built from filtered rows, and cache-safe miss
  after revised quality identity.
- [ ] Run targeted Flexible tests; observe current raw-only history identity
  cannot satisfy the new assertions.
- [ ] Implement calendar loading/filtering at `load_flexible_history()` before
  raw assessment and source fingerprinting. Thread the typed ineligible result
  through discovery/qualification/current scan without a raw fallback. Preserve
  immutable file contracts for newly created records; no legacy Flexible state
  exists to migrate.
- [ ] Re-run all Flexible Rulebook suites; expect pass.

### Task 5: Calendar-aware TCX diagnostic and validation investigation

**Files:**

- Modify: `app/backtest_engine/validation_diagnostics.py` (if present) or
  create it as the read-only diagnostic owner
- Modify: `tests/test_backtest_validation_diagnostics.py`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Consumes:** Tasks 1–2.

**Produces:** A read-only trace that states canonical sessions, assumed
non-sessions, excluded ticker dates, event edge/age, and direction-aware
gate facts for TCX and saved candidates; it does not change live classification
or position action policy.

- [ ] Write red tests for TCX-style declining RSI/ADX/price data where a stale
  level cannot be represented as a fresh upcross, and for mid-term age based on
  completed canonical weekly bars.
- [ ] Implement diagnostics from the same prepared frame as live replay; no
  direct raw DataFrame rebuild is allowed.
- [ ] Run all relevant Docker tests and the read-only TCX/all-candidate probe.
  Record only observed evidence, then self-critique calendar assumptions,
  false BUY removals, and test-period separation.
- [ ] Stop before any age/trajectory/classification policy change. A separate
  approved policy decision remains required for `No Match`, `expired BUY`,
  `HOLD`, `can SELL`, and regeneration behavior beyond source invalidation.

### Task 6: Full verification and documentation

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-09-03-project-wide-vnindex-trading-calendar-verification.md`

- [ ] Run focused Backtest, Flexible, technical, Analyze/API tests and the
  canonical Docker suite.
- [ ] Compile every changed Python module and inspect actual persisted
  error/marker output using a temporary output root only.
- [ ] Verify database remains read-only for this work, price scaling and
  protected delta CTE are untouched, Flexible roots are still empty until a
  user-run benchmark, and no Git action occurs.
- [ ] Update context files with commands and observed results only.

## Plan self-review

The plan covers central calendar construction (Task 1), all Backtest and
position/replay paths (Task 2), all legacy technical production consumers
(Task 3), Flexible source/cache/feature paths (Task 4), TCX investigation
without premature live behavior change (Task 5), and verification/context
(Task 6). It intentionally does not change protected statistical delta SQL or
introduce a holiday package. The only unresolved product decision is the later
live age/trajectory policy; Task 5 provides evidence, and no code silently
chooses it.
