# Backtest V4 Schema-5 Evidence Integrity and Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace schema-4 Backtest evidence with causally correct schema-5
artifacts, prove one bounded Swing and one conditional Mid-term entry
experiment, and reduce runtime only under exact semantic parity.

**Architecture:** Repair formulas, clocks, partitions, fills, and source
eligibility before cutting persistence and downstream readers to schema 5.
Regenerate a corrected baseline control, then run research-only staged entry
definitions selected entirely on training evidence. Keep reference execution
available while vectorized components prove trace parity.

**Tech Stack:** Python 3.12, pandas, NumPy, Streamlit, PostgreSQL, SQLAlchemy,
`unittest`, Docker.

## Global Constraints

- Approved design:
  `docs/superpowers/specs/2026-09-01-backtest-v4-schema-5-enhancement-design.md`.
- Long-only simulation; actual BUY and SELL remain manual.
- Every visible result says **Exploratory — gross**.
- Existing five-year evidence says **historical test — previously observed**.
- No fee, tax, slippage, market-impact, or partial-fill model.
- No new dependency.
- Do not modify `app/common_queries.py`, BIGINT-times-1000 storage/scaling,
  credentials, Docker files, or database schema.
- Use `sqlalchemy.text()`, bound parameters, `get_engine_with_retry()`, and
  `engine.raw_connection()` for database access.
- Schema-4 artifacts are never parsed or migrated; overwrite them with
  schema-5 `requires_regeneration` markers.
- Existing position records remain frozen history.
- No Git action or commit unless the user separately requests it. Each task
  ends at a test/reviewer checkpoint.
- Stop after research evidence; promotion of a research rulebook requires a
  separate approved design.

---

## File map

| Path | Responsibility |
|---|---|
| `app/backtest_engine/indicators.py` | Exact Wilder formulas and canonical indicator columns |
| `app/backtest_engine/timeframes.py` | Shared causal daily/W-FRI clock |
| `app/backtest_engine/vnindex_theme.py` | Theme construction from shared native dates |
| `app/backtest_engine/rolling_window.py` | Partition-complete and gap-safe reference execution |
| `app/backtest_engine/exploratory.py` | Honest split and baseline metrics/ranking |
| `app/backtest_engine/evidence.py` | New source fingerprints, density, and common-as-of contracts |
| `app/backtest_engine/config.py` | V5 rulebook/request identities |
| `app/backtest_engine/models.py` | Schema-5 execution and evidence identities |
| `app/backtest_engine/persistence.py` | Strict schema-5 artifacts and markers |
| `app/backtest_engine/pipeline.py` | Batch source freeze and schema-5 orchestration |
| `app/backtest_engine/early_warning.py` | Fresh fingerprint validation and current replay |
| `app/backtest_engine/validation_advice.py` | BUY safety and entry/SELL separation |
| `app/backtest_engine/research.py` | New staged definitions, pairing, stability, and selection |
| `app/backtest_engine/research_runner.py` | New read-only controlled experiment runner |
| `app/pages/backtest_lab.py` | Schema-5 labels/status projection only |

---

### Task 1: Exact SMA-Seeded Wilder Indicators

**Files:**
- Modify: `app/backtest_engine/indicators.py`
- Modify: `tests/test_backtest_indicators.py`
- Modify: `tests/test_backtest_rulebook_config.py`

**Interfaces:**
- Produces: `_wilder_average(values: pd.Series, period: int, seed_start: int) -> pd.Series`
- Produces: `_adx_components(frame: pd.DataFrame, period: int) -> tuple[pd.Series, pd.Series, pd.Series]`
- Preserves: `build_rulebook_frame(ohlcv, rulebook, *, common_as_of)` output
  column names.

- [x] **Step 1: Add independent golden RSI, ATR, DMI, and ADX tests.**

Use hard-coded expected numbers calculated from the SMA seed and recursive
formula; do not calculate expected values with pandas `ewm` or the production
helper.

```python
def _manual_wilder(values, period, seed_start):
    result = [None] * len(values)
    seed_end = seed_start + period
    result[seed_end - 1] = sum(values[seed_start:seed_end]) / period
    for index in range(seed_end, len(values)):
        result[index] = (
            result[index - 1] * (period - 1) + values[index]
        ) / period
    return result

def test_atr_uses_sma_seed_then_wilder_recursion(self):
    frame = make_ohlcv(rows=40)
    actual = backtest_indicators._atr(frame, 14)
    prior_close = frame["close"].shift(1)
    expected_tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prior_close).abs(),
            (frame["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1).tolist()
    expected = _manual_wilder(expected_tr, 14, 0)
    self.assertTrue(np.allclose(actual.iloc[13:].to_numpy(), expected[13:]))
```

Add a separate RSI fixture whose first valid value is bar `period`, and an ADX
fixture whose first valid ADX is bar `2 * period - 2`.

- [x] **Step 2: Run the RED indicator gate.**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_indicators tests.test_backtest_rulebook_config -v
```

Expected: the new RSI/ATR/ADX assertions fail against EWM seeding; existing
Alligator assertions remain green.

- [x] **Step 3: Implement one exact recursive primitive and use it consistently.**

```python
def _wilder_average(
    values: pd.Series,
    period: int,
    *,
    seed_start: int,
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = pd.Series(float("nan"), index=numeric.index, dtype=float)
    seed_end = seed_start + period
    if period < 1 or len(numeric) < seed_end:
        return result
    seed = numeric.iloc[seed_start:seed_end]
    if not np.isfinite(seed.to_numpy(dtype=float)).all():
        return result
    result.iloc[seed_end - 1] = float(seed.mean())
    for position in range(seed_end, len(numeric)):
        prior = result.iloc[position - 1]
        current = numeric.iloc[position]
        if not np.isfinite(prior) or not np.isfinite(current):
            continue
        result.iloc[position] = (prior * (period - 1) + current) / period
    return result
```

Use `seed_start=1` for RSI gains/losses, `seed_start=0` for ATR and DM/TR,
and seed ADX from the first `period` valid DX values. Return `+DI` and `-DI`
from `_adx_components`; keep `rulebook_adx_14` and `ATR_14` public columns.

- [x] **Step 4: Prove GREEN and causal-prefix invariance.**

Add a test that perturbs bars strictly after an as-of index and asserts every
earlier RSI/ATR/ADX/DMI value is unchanged. Run the Task 1 command and expect
all tests to pass.

- [x] **Step 5: Reviewer checkpoint.**

Inspect that no `ewm(alpha=1/period)` remains in Backtest RSI/ATR/ADX, EMA is
unchanged, and the common Technical Analyze module was not modified.

**Task 1 gate:** PASS — intended RED failures were observed for RSI, ATR, ADX,
and DMI exposure; focused Docker tests pass 16/16, the Backtest regression gate
passes 186/186, and both modified modules compile.

---

### Task 2: Shared Common-As-Of and Completed W-FRI Clock

**Files:**
- Modify: `app/backtest_engine/timeframes.py`
- Modify: `app/backtest_engine/indicators.py`
- Modify: `app/backtest_engine/vnindex_theme.py`
- Modify: `app/backtest_engine/pipeline.py`
- Modify: `tests/test_backtest_vnindex_theme.py`
- Modify: `tests/test_backtest_pipeline.py`
- Modify: `tests/test_backtest_indicators.py`

**Interfaces:**
- Produces: `latest_common_completed_bar(sources: Mapping[str, pd.DataFrame], requested_end: date) -> date`
- Produces: `to_weekly_ohlcv(frame: pd.DataFrame, *, common_as_of: date) -> pd.DataFrame`
- Changes: `build_rulebook_frame(ohlcv, rulebook, *, common_as_of: date)`
  requires an explicit date.

- [x] **Step 1: Write independent date-label tests.**

```python
def test_midterm_ticker_and_theme_share_completed_friday_labels(self):
    ticker = make_ohlcv(start="2024-01-01", rows=105)
    vnindex = ticker.copy(deep=True)
    for column in ("open", "high", "low", "close"):
        vnindex[column] += 1000
    as_of = date(2024, 5, 24)
    ticker_weekly = to_weekly_ohlcv(ticker, common_as_of=as_of)
    theme_weekly = to_weekly_ohlcv(vnindex, common_as_of=as_of)
    self.assertEqual(
        ticker_weekly["date"].tolist(),
        theme_weekly["date"].tolist(),
    )
    self.assertEqual(pd.Timestamp(as_of), ticker_weekly["date"].iloc[-1])

def test_historical_wednesday_does_not_emit_following_friday(self):
    source = make_ohlcv(start="2024-01-01", rows=105)
    source = source.loc[source["date"].le(pd.Timestamp("2024-05-15"))]
    weekly = to_weekly_ohlcv(
        source,
        common_as_of=date(2024, 5, 15),
    )
    self.assertLessEqual(weekly["date"].max().date(), date(2024, 5, 15))
```

Cover Friday, weekend, historical Wednesday, missing-Friday conservative
behavior, and no future change after appending later bars.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_vnindex_theme tests.test_backtest_pipeline tests.test_backtest_indicators -v
```

Expected: the default-W-SUN and implicit-wall-clock cases fail.

- [x] **Step 3: Implement the shared adapters.**

```python
def latest_common_completed_bar(sources, requested_end):
    latest = []
    cutoff = pd.Timestamp(requested_end)
    for name, frame in sources.items():
        dates = pd.to_datetime(frame["date"], errors="coerce")
        eligible = dates.loc[dates.le(cutoff)]
        if eligible.empty:
            raise ValueError(f"{name} has no completed bar within request")
        latest.append(eligible.max())
    return min(latest).date()

def to_weekly_ohlcv(frame, *, common_as_of):
    working = frame.copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.loc[working["date"].le(pd.Timestamp(common_as_of))]
    weekly = (
        working.set_index("date")
        .resample("W-FRI", label="right", closed="right")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return weekly.loc[weekly["date"].le(pd.Timestamp(common_as_of))].reset_index(drop=True)
```

Load all batch sources before evaluation, calculate one common-as-of across the
full ticker union and VN-Index, and pass it explicitly to ticker and theme
builders. Do not consult `datetime.now()` in historical frame construction.

- [x] **Step 4: Run GREEN and a batch common-date assertion.**

Assert every batch artifact receives the same `common_as_of`. Re-run the Task
2 command and expect all tests to pass.

- [x] **Step 5: Reviewer checkpoint.**

Confirm no Mid-term path calls a second weekly adapter and no test computes its
expected labels with the production helper under test.

**Task 2 gate (2026-09-01): PASS.** Independent RED evidence recorded the
missing explicit-cutoff APIs plus six legacy clock failures. One shared
`W-FRI` adapter now owns ticker/theme construction, daily and weekly frames
require an explicit common cutoff, single and batch pipelines use the latest
bar shared by every successfully loaded ticker source and VN-Index, and
persisted effective ranges stop at that same boundary. Focused Task 2 tests
pass 34/34, affected reader tests pass 29/29, the full Backtest suite passes
191/191, and affected modules compile. The only other Backtest `W-FRI`
resample is the pre-existing history-span audit, not a frame builder.

---

### Task 3: Honest Split, Completed Partition Exits, and Gap-Safe Stops

**Files:**
- Modify: `app/backtest_engine/exploratory.py`
- Modify: `app/backtest_engine/rolling_window.py`
- Modify: `tests/test_backtest_exploratory.py`
- Modify: `tests/test_backtest_rolling_window.py`
- Modify: `tests/test_backtest_trade_execution.py`

**Interfaces:**
- Preserves: `split_native_frame(frame, *, requested_start, requested_end) -> EvaluationSplit`.
- Preserves: `run_rulebook_trade_sequence(frame, execution, entry_signal) -> list[TradeEvent]` while changing its boundary behavior to retain completed exits but never incomplete positions.

- [x] **Step 1: Add RED split and trade fixtures.**

```python
def test_calendar_split_requires_terminal_coverage(self):
    frame = pd.DataFrame(
        {"date": pd.date_range("2011-09-01", "2022-01-03", freq="B")}
    )
    split = split_native_frame(
        frame,
        requested_start=date(2011, 9, 1),
        requested_end=date(2026, 9, 1),
    )
    self.assertEqual("chronological_65_35", split.method)

def test_completed_stop_survives_when_timeout_is_outside_partition(self):
    frame = make_frame(rows=10)
    frame.loc[5, "low"] = 80
    entries = pd.Series(False, index=frame.index)
    entries.loc[1] = True
    execution = RulebookExecution(rulebook_for("swing"), ENTRY_GATE_NAMES)
    events = run_rulebook_trade_sequence(frame, execution, entries)
    self.assertEqual(1, len(events))
    self.assertEqual("stop_loss", events[0].exit_reason)

def test_gap_below_stop_fills_at_open(self):
    frame = make_frame(rows=30)
    frame.loc[5, ["open", "high", "low", "close"]] = [70, 75, 60, 65]
    entries = pd.Series(False, index=frame.index)
    entries.loc[1] = True
    execution = RulebookExecution(rulebook_for("swing"), ENTRY_GATE_NAMES)
    event = run_rulebook_trade_sequence(frame, execution, entries)[0]
    self.assertEqual(70, event.exit_price)
```

Also cover no exit before partition end, timeout inside/outside, crossing
signal/entry/exit, target gap, and stop/target collision.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_exploratory tests.test_backtest_rolling_window tests.test_backtest_trade_execution -v
```

- [x] **Step 3: Implement the exact boundary and fill rules.**

Require `last >= requested_end - 7 days` for calendar 10y/5y. In the executor,
scan available eligible rows through `min(timeout_position, last_position)`.
Emit timeout only when `timeout_position <= last_position`; otherwise return no
event if neither stop nor target completed.

Use this exit price function:

```python
def _price_exit(row, reason, stop_loss, take_profit):
    if reason == "stop_loss":
        opened = float(row["open"])
        return opened if opened < stop_loss else stop_loss
    if reason == "take_profit":
        return take_profit
    raise ValueError("price exit reason is invalid")
```

Retain stop-first ordering and the existing minimum exit offsets.

- [x] **Step 4: Prove GREEN and old-rule negative evidence.**

Run the Task 3 command. Add an assertion that an open trade with no completed
in-partition exit remains absent.

- [x] **Step 5: Reviewer checkpoint.**

Verify no executor reads a row outside its supplied partition and every
retained event's signal, entry, and exit dates are within `source_window`.

**Task 3 gate (2026-09-01): PASS.** RED evidence proved missing terminal
coverage, premature timeout-fit rejection, and optimistic stop-gap pricing.
Calendar 10y/5y now requires both endpoints within seven days; execution scans
only through the earlier of timeout or partition end, retains completed
in-partition stop/target exits, drops still-open positions, and emits timeout
only when its inclusive bar exists. Long stops gap below at raw open, targets
remain frozen-target fills, and collisions remain stop-first. Focused tests
pass 21/21, all Backtest tests pass 199/199, and affected modules compile.

---

### Task 4: Source Fingerprint, Density, and Evidence Eligibility

**Files:**
- Create: `app/backtest_engine/evidence.py`
- Create: `tests/test_backtest_evidence.py`
- Modify: `app/backtest_engine/pipeline.py`
- Modify: `tests/test_backtest_pipeline.py`

**Interfaces:**
- Produces: `EvidenceEligibility` immutable dataclass.
- Produces: `source_fingerprint(ticker: str, frame: pd.DataFrame, common_as_of: date) -> str`
- Produces: `assess_evidence(ticker_frame, vnindex_frame, common_as_of) -> EvidenceEligibility`

- [x] **Step 1: Write RED canonical-identity and density tests.**

```python
def _session_frame(rows=100):
    dates = pd.bdate_range("2020-01-01", periods=rows)
    close = pd.Series(range(50_000, 50_000 + rows), dtype="int64")
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 100,
            "low": close - 100,
            "close": close,
            "volume": [1_000] * rows,
        }
    )

def test_fingerprint_changes_for_append_and_historical_correction(self):
    original = _session_frame(100)
    first = source_fingerprint("VCB", original, original["date"].iloc[-1].date())
    corrected = original.copy(deep=True)
    corrected.loc[10, "close"] += 1000
    self.assertNotEqual(
        first,
        source_fingerprint("VCB", corrected, corrected["date"].iloc[-1].date()),
    )
    appended = pd.concat([original, _session_frame(101).iloc[[-1]]], ignore_index=True)
    self.assertNotEqual(
        first,
        source_fingerprint("VCB", appended, appended["date"].iloc[-1].date()),
    )

def test_recent_listing_uses_only_effective_session_denominator(self):
    vnindex = _session_frame(rows=500)
    ticker = vnindex.iloc[-490:].copy()
    evidence = assess_evidence(ticker, vnindex, ticker["date"].iloc[-1].date())
    self.assertTrue(evidence.eligible)
    self.assertEqual(490, evidence.expected_sessions)

def test_more_than_twenty_missing_sessions_is_ineligible(self):
    vnindex = _session_frame(rows=100)
    ticker = vnindex.drop(index=range(30, 51)).reset_index(drop=True)
    evidence = assess_evidence(ticker, vnindex, vnindex["date"].iloc[-1].date())
    self.assertFalse(evidence.eligible)
    self.assertIn("max_gap_sessions_exceeds_20", evidence.reasons)
```

Cover row order, duplicate dates, numeric canonicalization, 94.99% versus 95%,
missing latest bar, and VN-Index fingerprint independence.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_evidence tests.test_backtest_pipeline -v
```

- [x] **Step 3: Implement immutable evidence.**

```python
@dataclass(frozen=True)
class EvidenceEligibility:
    status: str
    eligible: bool
    reasons: tuple[str, ...]
    common_as_of: date
    first_available_bar: date
    last_available_bar: date
    ticker_fingerprint: str
    vnindex_fingerprint: str
    observed_sessions: int
    expected_sessions: int
    coverage_ratio: float
    max_gap_sessions: int

    def to_dict(self):
        return {
            "status": self.status,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "common_as_of": self.common_as_of.isoformat(),
            "first_available_bar": self.first_available_bar.isoformat(),
            "last_available_bar": self.last_available_bar.isoformat(),
            "ticker_fingerprint": self.ticker_fingerprint,
            "vnindex_fingerprint": self.vnindex_fingerprint,
            "observed_sessions": self.observed_sessions,
            "expected_sessions": self.expected_sessions,
            "coverage_ratio": self.coverage_ratio,
            "max_gap_sessions": self.max_gap_sessions,
        }
```

Hash uppercase ticker and ordered raw integer tuples with SHA-256. Calculate
missing runs as consecutive absent VN-Index session positions. Use
`coverage_ratio >= 0.95`, `max_gap_sessions <= 20`, and exact latest-bar
equality.

- [x] **Step 4: Wire evidence into pipeline results without changing schema yet.**

Pass `EvidenceEligibility` as an internal value to `_persist_evaluation` and
`_persist_failure`. Do not serialize until Task 5 cuts over atomically.

- [x] **Step 5: Prove GREEN and inspect real sparse cases read-only.**

Run the Task 4 command, then a non-writing Docker diagnostic for VPL, HHC, TPP,
and one recent listing. Record counts only; do not write artifacts.

**Task 4 gate (2026-09-01): PASS.** Canonical SHA-256 identity includes the
uppercase ticker plus ordered raw integer OHLCV tuples through common-as-of;
row order is normalized, duplicate dates and fractional raw values are
rejected, and ticker/VN-Index fingerprints remain independent. Eligibility
uses VN-Index sessions only from the ticker's first available bar, requires
95% density, no missing run above 20 sessions, exact latest-bar equality, and
a clean raw audit. Internal evidence reaches success and failure persistence
without schema-4 serialization. Focused tests pass 15/15, all Backtest tests
pass 209/209, and affected modules compile. The non-writing database probe
measured VPL 408/3743 (10.90%, max gap 3331), HHC 1920/3742 (51.31%, 73), TPP
2299/3742 (61.44%, 59), all ineligible; recent listing LPS was 9/9 (100%, 0)
and eligible. No artifact or database write occurred.

---

### Task 5: Atomic Schema-5 Cutover and Regeneration

**Files:**
- Modify: `app/backtest_engine/config.py`
- Modify: `app/backtest_engine/models.py`
- Modify: `app/backtest_engine/persistence.py`
- Modify: `app/backtest_engine/pipeline.py`
- Modify: `app/backtest_engine/job_runner.py`
- Modify: `app/backtest_engine/worker.py`
- Modify: `app/backtest_engine/result_store.py`
- Modify: `tests/test_backtest_rulebook_config.py`
- Modify: `tests/test_backtest_persistence.py`
- Modify: `tests/test_backtest_regeneration.py`
- Modify: `tests/test_backtest_worker.py`
- Modify: `tests/test_backtest_job_runner.py`

**Interfaces:**
- Produces: schema version `5`, contract `backtest_schema5_v1`.
- Produces: `swing_rulebook_v5`, `midterm_rulebook_v5`.
- Preserves canonical filenames and atomic replacement.

- [x] **Step 1: Add strict schema-5 RED fixtures.**

Build one complete success, empty, failed, and `requires_regeneration` fixture.
Assert schema 4 is rejected, every schema-5 field is exact, an ineligible
success remains displayable, and malformed evidence never persists.

```python
def _eligible_evidence():
    return {
        "status": "eligible",
        "eligible": True,
        "reasons": [],
        "common_as_of": "2026-01-02",
        "first_available_bar": "2011-01-03",
        "last_available_bar": "2026-01-02",
        "ticker_fingerprint": "a" * 64,
        "vnindex_fingerprint": "b" * 64,
        "observed_sessions": 3700,
        "expected_sessions": 3700,
        "coverage_ratio": 1.0,
        "max_gap_sessions": 0,
    }

def test_schema_four_is_rejected_without_migration(self):
    payload = _success_document()
    payload.update({
        "schema_version": 5,
        "contract_version": "backtest_schema5_v1",
        "partition_labels": {
            "training": "in-sample",
            "test": "historical test — previously observed",
        },
        "evidence_eligibility": _eligible_evidence(),
    })
    payload["schema_version"] = 4
    with self.assertRaisesRegex(ValueError, "unsupported rulebook result schema"):
        validate_rulebook_document(payload)

def test_schema5_requires_partition_and_evidence_labels(self):
    payload = _success_document()
    payload.update({
        "schema_version": 5,
        "contract_version": "backtest_schema5_v1",
        "partition_labels": {
            "training": "in-sample",
            "test": "historical test — previously observed",
        },
        "evidence_eligibility": _eligible_evidence(),
    })
    self.assertTrue(validate_rulebook_document(payload))
    self.assertEqual(
        "historical test — previously observed",
        payload["partition_labels"]["test"],
    )
```

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_rulebook_config tests.test_backtest_persistence tests.test_backtest_regeneration tests.test_backtest_worker tests.test_backtest_job_runner -v
```

- [x] **Step 3: Change identities and strict document validation together.**

Set `_SCHEMA_VERSION = 5`; add `contract_version`, `partition_labels`,
`evidence_eligibility`, and `candidate_role`. Baseline candidates require
`candidate_role == "baseline_control"`. Rename request types to V5. Replace
V3 audit-source names with `fresh_schema5_raw_history` in the modified path.

```python
_SCHEMA_VERSION = 5
_CONTRACT_VERSION = "backtest_schema5_v1"
_PARTITION_LABELS = {
    "training": "in-sample",
    "test": "historical test — previously observed",
}
```

- [x] **Step 4: Implement filename-only invalidation.**

`write_regeneration_marker` must create a schema-5 marker from ticker and
horizon arguments without reading the existing file. Regeneration must cover
canonical artifacts and visible job sidecars, use atomic replacement, and
carry the exact reason `Regenerate under Backtest schema 5.` for the contract
cutover.

- [x] **Step 5: Run GREEN and round-trip tests.**

Run the Task 5 command. Verify success/empty/failed/marker round trips and a
temporary-file failure leaves the previous valid artifact intact.

- [x] **Step 6: Reviewer checkpoint.**

Search readers for `schema_version == 4`, `schema-4`, `rulebook_v4`, and V3
audit-source names. Every active reader must either use schema 5 or explicitly
classify old data as frozen history.

**Task 5 gate (2026-09-01): PASS.** Strict schema-5 success, empty, failed,
and regeneration contracts now round-trip atomically; schema 4 is rejected
without parsing or migration. The focused suite passes 33/33, the affected
reader/pipeline suite passes 76/76, and compilation passes. Content-blind
cutover wrote 74 canonical and 18 horizon-qualified legacy artifact markers
plus 95 job pairs; verification confirmed all 92 schema-4/current artifact
targets and all 190 job sidecars are schema-5 `requires_regeneration`
documents. Twenty-seven older theme-only schema-2 files remain intentionally
ignored frozen history under the design's unrelated-history boundary.

---

### Task 6: Fresh Replay, BUY Blocking, and Separate SELL Semantics

**Files:**
- Modify: `app/backtest_engine/early_warning.py`
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `app/backtest_engine/manual_position_store.py`
- Modify: `app/backtest_engine/position_store.py`
- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `tests/test_backtest_manual_position_store.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- Produces: `validate_current_evidence(document, ticker_raw, vnindex_raw) -> EvidenceEligibility`
- Changes: `_position_action` no longer maps consumed BUY trigger to `can SELL`.

- [x] **Step 1: Write RED stale-evidence and position-action tests.**

```python
def test_consumed_entry_trigger_does_not_sell_open_position(self):
    current = {"literal_entry": False, "latest_close": 100.0}
    position = {
        "status": "open",
        "risk_snapshot": {"stop_loss": 90.0, "take_profit": 120.0},
    }
    self.assertEqual(
        "HOLD",
        _position_action(current, position, buy_eligible=False),
    )
```

For the stale-source test, mock `load_ticker_history` with the exact raw rows
used by a valid schema-5 fixture plus one appended completed session. Mock
`write_regeneration_marker`, call `check_current_situation`, and assert one
marker call, `candidate is None`, and reason `source_history_changed`.

Add explicit technical-exit, stop, target, malformed risk, manual position,
schema-4 historical position, and evidence-ineligible cases.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_manual_position_store tests.test_backtest_page -v
```

- [x] **Step 3: Recompute evidence before signal replay.**

Load ticker and VN-Index once, calculate the current common-as-of, compare both
frozen fingerprints and latest date, and atomically write a regeneration marker
on mismatch. Return a structured stale reason; do not replay the candidate.

- [x] **Step 4: Separate entry, deterioration, and price exits.**

```python
def _position_action(current, open_position, buy_eligible):
    if open_position is None:
        return "can BUY" if buy_eligible else "expired BUY"
    if bool(current.get("technical_exit")) or bool(current.get("deteriorated")):
        return "can SELL"
    try:
        close = float(current["latest_close"])
        snapshot = open_position["risk_snapshot"]
        stop_loss = float(snapshot["stop_loss"])
        take_profit = float(snapshot["take_profit"])
    except (KeyError, TypeError, ValueError):
        return "HOLD"
    return "can SELL" if close <= stop_loss or close >= take_profit else "HOLD"
```

Baseline schema-5 replay sets `technical_exit=False` and
`deteriorated=False`; future promoted staged definitions must supply explicit
predicates.

- [x] **Step 5: Update UI labels and GREEN tests.**

View/Validate display `Exploratory — gross`, `in-sample`,
`historical test — previously observed`, evidence status, and regeneration
reason. Research-only documents are ignored. Run the Task 6 command.

- [x] **Step 6: Reviewer checkpoint.**

Verify Validate Signals remains sequential and read-only except for the
explicit atomic invalidation marker. No SELL is executed.

**Task 6 gate (2026-09-01): PASS.** Validate Signals now loads ticker and
VN-Index exactly once, recomputes the complete common-as-of evidence identity,
and atomically replaces stale artifacts before candidate replay. New saved
positions use strict schema-5 baseline-control references with frozen evidence;
schema-4 and older records remain readable historical data and cannot consume
a current identity. A consumed BUY event no longer implies SELL: only explicit
technical exit/deterioration or frozen stop/target conditions do. Evidence and
partition labels are visible in View/Validate, regeneration reasons are shown,
and V5 positions preserve their native horizon for risk monitoring. Focused
Task 6 tests pass 74/74, the complete Backtest suite passes 223/223, and all
affected modules compile. Reviewer search finds schema 4 only in the explicit
frozen-history normalization path; validation remains sequential and executes
no trade or SELL write.

---

### Task 7: Corrected Baseline Regeneration and Practical Evidence Gate

**Files:**
- Modify: `tests/test_backtest_signal_combos.py`
- Modify: `tests/test_backtest_exploratory.py`
- Modify: `tests/test_backtest_pipeline.py`
- Create: `docs/superpowers/reports/2026-09-01-backtest-schema-5-baseline-verification.md`

**Interfaces:**
- Preserves: 15 baseline subsets × two treatments.
- Produces: frozen pre-experiment baseline hashes and funnel evidence.

- [x] **Step 1: Reassert the baseline contract after the schema cutover.**

Tests must prove 15 lexical non-empty subsets, paired treatments, no-theme
training `n >= 5`, DSR treatment-only selection, informational p-value, and
exact Top-3 rank order. All candidates serialize as `baseline_control`.

- [x] **Step 2: Run the focused schema-5 Backtest gate.**

```powershell
docker exec stock_app python -m unittest discover -s tests -p "test_backtest*.py" -v
```

Expected: all Backtest tests pass before any database artifact is regenerated.

- [x] **Step 3: Run a non-writing eight-ticker baseline diagnostic.**

Use the frozen sample `VCB,DHC,DSN,ELC,BVH,HAP,DRC,CSM`, exact 1,000
permutations, both horizons, and the latest common completed bar. Record source
fingerprints, density, split, funnel, candidates, Top 3, exits, gap changes,
runtime, and peak memory. Do not persist canonical artifacts during this step.

- [x] **Step 4: Compare schema 4 versus corrected schema 5 without treating the difference as improvement.**

The report lists signal-date, `n`, return, treatment, and rank changes caused by
correctness repairs. It explicitly invalidates Mid-term schema-4 theme metrics
as a quality comparator.

- [x] **Step 5: Regenerate canonical artifacts only after review approval.**

Run the ordinary Collect Signals worker path. Assert every canonical result is
schema 5 and shares the approved common-as-of; no schema-4 success remains
readable.

**Task 7 gate (2026-09-02): PASS.** The full Backtest gate passes 224/224.
The non-writing frozen-sample diagnostic completed 16 evaluations at exact
1,000 permutations with one `2026-08-28` common-as-of, 330.7544649820047
measured seconds, and 24,326,881 maximum traced bytes. It records fingerprints,
partitions, primitive density, funnel, Top 3, reconstructed legacy-behavior
changes, exits, and gap fills without claiming improvement. Ordinary isolated
Collect workers then regenerated 16 canonical schema-5 artifacts; all validate
through the production reader as `backtest_schema5_v1` success documents with
baseline-control candidates and the same common-as-of. HAP is explicitly
evidence-ineligible/display-only because its 58-session gap exceeds 20. Report:
`docs/superpowers/reports/2026-09-01-backtest-schema-5-baseline-verification.md`.

---

### Task 8: Staged Research Definitions and Training Diagnostics

**Files:**
- Create: `app/backtest_engine/research.py`
- Create: `tests/test_backtest_research.py`
- Modify: `app/backtest_engine/models.py`
- Modify: `app/backtest_engine/indicators.py`

**Interfaces:**
- Produces: `ResearchDefinition`, `MatchedTradePair`, `ResearchEvaluation`.
- Produces: `pair_first_overlaps(control, variant, native_dates) -> tuple[MatchedTradePair, ...]`, where both trade inputs are ordered `Sequence[TradeEvent]` values and `native_dates` is an ordered `Sequence[date]`.
- Produces: `leave_one_year_out(events) -> tuple[YearOmissionMetrics, ...]`, where `events` is an ordered `Sequence[TradeEvent]`.

- [x] **Step 1: Write RED identity, stage, pairing, and metric tests.**

```python
def _trade(signal_date, exit_date):
    signal = pd.Timestamp(signal_date)
    entry = signal + pd.offsets.BDay(1)
    exit_at = pd.Timestamp(exit_date)
    return TradeEvent(
        signal_date=signal,
        entry_date=entry,
        entry_price=100,
        atr=10,
        stop_loss=85,
        take_profit=125,
        exit_date=exit_at,
        exit_price=110,
        exit_reason="timeout",
        return_pct=10.0,
        source_window=(signal, exit_at),
    )

def test_first_overlap_pairing_is_deterministic(self):
    native_dates = tuple(pd.bdate_range("2020-01-01", "2020-02-14").date)
    control = (_trade("2020-01-06", "2020-01-20"), _trade("2020-02-03", "2020-02-10"))
    variant = (_trade("2020-01-03", "2020-01-08"), _trade("2020-02-05", "2020-02-12"))
    pairs = pair_first_overlaps(control, variant, native_dates)
    self.assertEqual(2, len(pairs))
    self.assertEqual(1, pairs[0].variant_signal_lead_bars)

def test_theme_volume_and_adx_cannot_be_standalone_research_entries(self):
    with self.assertRaisesRegex(ValueError, "setup and trigger are required"):
        ResearchDefinition(
            definition_id="bad",
            horizon="swing",
            setup=None,
            trigger=None,
            confirmations=("adx",),
        )
```

Cover immutable hash identity, candidate role `research_only`, setup/trigger
requirements, inclusive first-overlap, unpaired trades, MAE, drawdown, stop
rate, distinct years, absolute-P&L concentration, and year omission.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_research -v
```

- [x] **Step 3: Implement only the two approved experiment pairs.**

```python
SWING_CONTROL = ResearchDefinition(
    definition_id="swing_joint_rsi52_control_v1",
    horizon="swing",
    setup="ema5_13_and_alligator_up",
    trigger="rsi9_upcross_52",
    confirmations=(),
)
SWING_VARIANT = ResearchDefinition(
    definition_id="swing_ema_rsi52_variant_v1",
    horizon="swing",
    setup="ema5_above_ema13",
    trigger="rsi9_upcross_52",
    confirmations=(),
)
MIDTERM_CONTROL = ResearchDefinition(
    definition_id="midterm_joint_rsi65_control_v1",
    horizon="midterm",
    setup="sma8_21_and_alligator_up",
    trigger="rsi14_upcross_65",
    confirmations=(),
)
MIDTERM_VARIANT = ResearchDefinition(
    definition_id="midterm_joint_close_sma8_variant_v1",
    horizon="midterm",
    setup="sma8_21_and_alligator_up",
    trigger="close_upcross_sma8",
    confirmations=(),
)
```

Do not add periods, thresholds, exit variants, voting, or a generic indicator
catalog.

- [x] **Step 4: Implement training-only acceptance predicates.**

Swing requires at least five pairs, median lead at least one bar, lexicographic
metric superiority, no worse MAE/stop rate/drawdown, and no fewer positive
year-omission runs. Mid-term requires lexicographic superiority, no fewer
distinct years, no greater absolute-P&L concentration/drawdown, and no fewer
positive year-omission runs.

- [x] **Step 5: Run GREEN and assert test blindness.**

Perturb only test trades and assert selected definition and training acceptance
are byte-for-byte unchanged.

- [x] **Step 6: Reviewer checkpoint.**

Confirm research definitions are not imported by canonical signal readers,
validation, saved-position dropdowns, or Top-3 product projection.

**Task 8 gate (2026-09-02): PASS.** Four immutable definitions encode only
the two approved control/variant pairs. Entry masks require a directional setup
and causal one-bar trigger; optional confirmations cannot stand alone.
First-overlap pairing, signal lead, MAE, compounded drawdown, stop rate,
exit-year dispersion/concentration, leave-one-year-out evidence, and both
training-only acceptance predicates are deterministic. Historical-test changes
cannot alter the byte-for-byte selection snapshot. Focused tests pass 14/14;
the full Backtest suite passes 238/238; affected modules compile. A source
search confirms zero research imports in canonical pages, readers, validation,
saved-position, or Top-3 paths.

---

### Task 9: Controlled Experiment Runner and Evidence Report

**Files:**
- Create: `app/backtest_engine/research_runner.py`
- Create: `tests/test_backtest_research_runner.py`
- Create: `docs/superpowers/reports/2026-09-01-backtest-schema-5-controlled-experiments.md`

**Interfaces:**
- Produces: `run_controlled_experiment(request, engine) -> ResearchEvaluation`.
- Produces immutable research JSON outside canonical ticker-signal paths.

- [x] **Step 1: Write RED runner-isolation and ordering tests.**

Assert the runner freezes sources/common-as-of, evaluates training before
opening historical test, writes only its configured research directory, and
cannot overwrite canonical artifacts.

- [x] **Step 2: Run RED.**

```powershell
docker exec stock_app python -m unittest tests.test_backtest_research_runner -v
```

- [x] **Step 3: Implement a read-only-by-default runner.**

The request contains ticker, horizon, requested dates, permutation settings,
and explicit output directory. The output stores source hashes, definitions,
training selection, acceptance components, previously-observed test metrics,
and `promotion_status: research_only`. It never returns a product rulebook ID.

- [x] **Step 4: Run Swing experiment 1 on the frozen sample.**

Record matched/unmatched counts, median lead, MAE, stop rate, drawdown, year
omission, training rank, and observed-test evidence. A failed acceptance is a
valid result.

- [x] **Step 5: Run Mid-term only after the corrected baseline gate.**

Before evaluating Mid-term, assert ticker/theme date identity and cite the
schema-5 baseline verification hash. Otherwise write `not_run` with the failed
prerequisite; do not substitute old Mid-term evidence.

- [x] **Step 6: Stop at the promotion gate.**

The report states whether each variant passed its predeclared training gates.
It cannot promote a result, modify canonical Top 3, or use the observed test to
reverse the selection. Wait for a separate user decision.

**Task 9 gate (2026-09-02): PASS; promotion remains closed.** The runner is
read-only by default, freezes all four training treatment executions before
historical test, and writes only content-addressed immutable
`backtest_research_schema5_v1` documents outside the canonical result tree.
The frozen sample produced 14 complete evaluations and two explicit HAP
`not_run` records for its 58-session gap. No variant passed all predeclared
training gates, so all controls remain selected and no promotion decision is
available. The exact Mid-term baseline report hash, W-FRI/source identity, and
current canonical artifact are mandatory prerequisites. Combined research
tests pass 21/21; the full Backtest suite passes 245/245; compilation and
canonical-product import isolation pass. Report:
`docs/superpowers/reports/2026-09-01-backtest-schema-5-controlled-experiments.md`.

---

### Task 10: Exact-Parity Runtime Optimization

**Files:**
- Modify: `app/backtest_engine/validation.py`
- Modify: `app/backtest_engine/rolling_window.py`
- Modify: `app/backtest_engine/indicators.py`
- Create: `tests/test_backtest_runtime_parity.py`
- Create: `scripts/profile_backtest_schema5.py`

**Interfaces:**
- Preserves all public Backtest interfaces and serialized values.
- Keeps reference implementations callable in tests until parity is proven.

- [x] **Step 1: Write trace and numeric parity tests before optimization.**

Fixtures cover dense/sparse entries, no signals, gap stops, target gaps,
collision, deadline, incomplete timeout, daily/weekly clocks, NaNs rejected by
preflight, and moving-block seeds. Compare every `TradeEvent` field, p-value,
candidate metric, preferred treatment, and Top-3 ID.

- [x] **Step 2: Record the reference benchmark.**

```powershell
docker exec stock_app python scripts/profile_backtest_schema5.py --ticker VCB --horizon swing --permutations 1000 --mode reference
```

Record p50, p95, peak RSS, trade count, and artifact digest.

- [x] **Step 3: Vectorize moving-block permutation.**

Generate block start indexes from the same seeded generator, build the null
matrix with NumPy indexing, and retain the same comparison/tie formula. Run
the parity tests; revert this component if any value differs.

- [x] **Step 4: Add the array executor behind parity coverage.**

Use NumPy arrays for OHLC/date/ATR and integer positions. Preserve the reference
cursor rule, stop-first collision, gap fill, minimum offset, partition end, and
source window. Keep the reference executor in tests.

- [x] **Step 5: Optimize Wilder loops without changing seeds.**

Use indexed NumPy arrays for the recursive loop and reconstruct a Series with
the original index. Require `equal_nan=True` exact or explicitly bounded
floating parity before using it in production.

- [x] **Step 6: Benchmark end-to-end and decide on ticker parallelism.**

Run reference and optimized modes over the frozen eight-ticker sample. Accept
only zero semantic differences and a material p95 improvement. Do not enable
parallel ticker workers in this task; record measured memory and DB time for a
separate decision.

**Task 10 gate (2026-09-02): PASS.** Eight parity tests cover complete trade
traces, seeded permutation values, exact Wilder/SMMA frames, and byte-identical
candidate/treatment/Top-3 projections. The frozen eight-ticker, two-horizon,
1,000-permutation benchmark produced matching reference/optimized artifact
digests for all 16 pairs. Swing p95 improved by about 75–78%; Mid-term by
about 64–67%; peak RSS remained about 253–258 MB. HAP remained explicitly
evidence-ineligible. Ticker workers remain sequential. The complete Backtest
gate passes 253/253.

---

### Task 11: Full Verification, Documentation, and Handoff

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `ai-context/architecture.md` if module/data flow changed as planned
- Create: `docs/superpowers/reports/2026-09-01-backtest-schema-5-final-verification.md`

**Interfaces:**
- Produces the final evidence gate; no new runtime interface.

- [x] **Step 1: Run focused Backtest discovery.**

```powershell
docker exec stock_app python -m unittest discover -s tests -p "test_backtest*.py" -v
```

Expected: all Backtest tests pass with no unexpected traceback.

- [x] **Step 2: Run canonical project discovery.**

```powershell
docker exec stock_app python -m unittest discover -s tests -v
```

Expected: all tests pass; do not weaken discovery or skip a schema-5 test.

- [x] **Step 3: Compile affected modules.**

```powershell
docker exec stock_app python -m compileall backtest_engine pages/backtest_lab.py
```

Expected: exit code 0.

- [x] **Step 4: Run practical read-only database verification.**

Verify the frozen sample, one recent listing, VPL, and one 15-ticker batch.
Record common-as-of, fingerprints, density, split, Top 3, labels, runtime,
memory, and BUY-block reasons. Do not call a ticker eligible when its evidence
gate fails.

- [x] **Step 5: Inspect protected boundaries and workspace changes.**

Confirm no modifications to protected SQL/price/credential/Docker boundaries,
no new dependency, no legacy artifact parsing, and no accidental database or
Git action.

- [x] **Step 6: Run implementation self-review and fix every material issue.**

Use `ai-skills/skill-implementation-review.md`. Re-run every affected gate
after a correction.

- [x] **Step 7: Write the verification report and update project state.**

Record exact commands/counts, Docker version, database common-as-of, source
hashes, negative evidence, research result status, runtime comparison, known
limitations, and the promotion gate. Mark only evidenced tasks complete.

**Task 11 gate (2026-09-02): PASS.** Full Backtest discovery passes 253/253;
canonical project discovery passes 773/773; compilation passes. Read-only
LPS/VPL and actual sequential 15-ticker batch checks preserve one common-as-of,
strict source identity, honest empty/ineligible states, and BUY blocks. The
boundary review found no protected-file, dependency, database, or Git action.
Final evidence:
`docs/superpowers/reports/2026-09-01-backtest-schema-5-final-verification.md`.

---

## Ordered stop gates

1. Tasks 1–6 must all pass before any canonical schema-5 regeneration.
2. Task 7 corrected baseline evidence must pass before Task 8 or Task 9.
3. Mid-term research cannot run before its W-FRI baseline proof.
4. Research evidence cannot alter product Top 3 or positions.
5. Runtime optimization cannot start before reference semantics are frozen.
6. Any parity mismatch rejects the optimized component.
7. Product promotion requires a new explicit design approval after Task 9.

## Plan self-review result

- Every approved schema-5 design requirement maps to Tasks 1–11.
- No protected boundary or new dependency is required.
- Formula, date, split, exit, evidence, schema, UI, position, experiment, and
  runtime contracts have explicit RED/GREEN tests.
- Research selection is training-only and cannot automatically promote.
- Schema-4 data is invalidated without parsing.
- Every implementation step is concrete; no implicit threshold tuning remains.
- Task interfaces use the same names throughout this plan.
