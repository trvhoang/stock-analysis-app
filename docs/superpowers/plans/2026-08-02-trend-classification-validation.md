# Complete Trend Classification Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empirically compare the legacy and current statistical trend classifiers using real database-derived probability records, then document divergences without changing production behavior.

**Architecture:** Keep production advice thresholds and output contracts unchanged while adding pure validation helpers and a read-only probe. The probe reuses `analyze_ticker()` to obtain current delta, Up/Down probabilities, signal count, and dates from the existing parameterized delta query; pure comparison code annotates each record with legacy/current classifications and divergence metadata. Results are written to a dated validation report for human review.

**Tech Stack:** Python 3.12, unittest, pandas, Streamlit application container, PostgreSQL, SQLAlchemy, existing `analyze_ticker()` and validation helpers.

## Global Constraints

- Do not modify `app/commons/common_queries.py`, `BASE_DELTA_CALC_CTE`, or `COMMON_DELTA_FILTER_WHERE_CLAUSE`.
- Do not modify production classifier thresholds until the validation report is reviewed and a separate change is approved.
- Use `sqlalchemy.text()` and bound parameters for every validation-only SQL query.
- Use `get_engine_with_retry()` and `engine.raw_connection()` for database access.
- Keep database prices as raw BIGINT values; this task has no display or export work.
- Use deterministic ticker selection, deterministic validation windows, and explicit sample-size/exclusion reporting.
- Treat `possibility_up`, `possibility_down`, `total_signals`, `current_delta`, `start_date`, and `end_date` returned by `analyze_ticker()` as database-derived observations; do not recompute them with a second delta formula.
- No recalibration, market-performance claim, schema change, dependency, Docker, credential, or `IMPLEMENTED.md` change.

---

## Classifier Definitions

The validation must compare these exact rules:

```python
def legacy_statistical_trend(possibility_up):
    if possibility_up > 70:
        return "Strong Up"
    if possibility_up >= 53:
        return "Up"
    if possibility_up >= 48:
        return "Sideways"
    if possibility_up >= 30:
        return "Down"
    return "Strong Down"


def current_statistical_trend(possibility_up, possibility_down):
    if possibility_up > 70:
        return "Strong Up"
    if possibility_up >= 53:
        return "Up"
    if possibility_down > 70:
        return "Strong Down"
    if possibility_down >= 53:
        return "Down"
    return "Sideways"
```

The legacy rule is represented by the existing `common_functions.provide_advice()` behavior; the current rule is represented by `pages.analyze_visualization._classify_statistical_trend()`. Validation helpers must be tested against those contracts, not silently redefine them.

### Task 1: Add Pure Comparison Helpers and Tests

**Files:**
- Modify: `app/commons/validation.py`
- Test: `tests/test_validation.py`
- Test: `tests/test_analyze_trend_classification.py` only if an existing contract assertion needs to be made explicit

**Interfaces:**
- Consumes: DataFrame records with `ticker`, `validation_days`, `result_days`, `signal_date`, `possibility_up`, `possibility_down`, and `total_signals`.
- Produces: pure classifier functions and `compare_trend_classifications(records)` returning a copy with `legacy_trend`, `current_trend`, `dominant_outcome`, and `changed` columns.

- [x] **Step 1: Write failing tests for exact threshold behavior.** Add tests for Up boundaries (`52.99`, `53`, `70`, `70.01`), legacy Down/Strong Down boundaries (`47.99`, `30`, `29.99`), current Down/Strong Down boundaries (`possibility_down` `53`, `70`, `70.01` while Up stays below `53`), no-change mass, equal probabilities, zero probabilities, and missing signals.

  ```python
  def test_no_change_mass_is_not_current_bearish_signal(self):
      self.assertEqual(legacy_statistical_trend(40), "Down")
      self.assertEqual(current_statistical_trend(40, 10), "Sideways")
  ```

- [x] **Step 2: Run the focused test file and verify RED.** Host fallback failed first with the expected missing-helper import; Docker was unavailable.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_validation -v
  ```

  Expected: FAIL because the new comparison helpers do not yet exist.

- [x] **Step 3: Implement the smallest pure helpers.** Add the exact two classifier adapters and `compare_trend_classifications()`. Normalize numeric probability columns with `pd.to_numeric(errors="coerce")`; preserve original fields; calculate `dominant_outcome` from Up, Down, and `100 - Up - Down` with deterministic tie order `Up`, `Down`, `No Change`; calculate `changed` and `eligible` (`total_signals >= 30` and both probabilities numeric). Invalid probability rows keep their source fields, receive `None` classifications and dominant outcome, `changed=False`, and `eligible=False`. Reject missing required columns with a precise `ValueError`; do not silently drop malformed records.

  ```python
  def calculate_dominant_outcome(row):
      values = {
          "Up": row["possibility_up"],
          "Down": row["possibility_down"],
          "No Change": 100 - row["possibility_up"] - row["possibility_down"],
      }
      if any(pd.isna(value) for value in values.values()):
          return None
      return max(("Up", "Down", "No Change"), key=lambda key: values[key])


  def compare_trend_classifications(records):
      required = {"ticker", "possibility_up", "possibility_down", "total_signals"}
      missing = required.difference(records.columns)
      if missing:
          raise ValueError(f"Missing validation columns: {sorted(missing)}")
      result = records.copy()
      result["possibility_up"] = pd.to_numeric(result["possibility_up"], errors="coerce")
      result["possibility_down"] = pd.to_numeric(result["possibility_down"], errors="coerce")
      valid = result["possibility_up"].notna() & result["possibility_down"].notna()
      result["legacy_trend"] = None
      result["current_trend"] = None
      result.loc[valid, "legacy_trend"] = result.loc[valid, "possibility_up"].map(legacy_statistical_trend)
      result.loc[valid, "current_trend"] = result.loc[valid].apply(
          lambda row: current_statistical_trend(row["possibility_up"], row["possibility_down"]),
          axis=1,
      )
      result["dominant_outcome"] = result.apply(calculate_dominant_outcome, axis=1)
      result["changed"] = valid & (result["legacy_trend"] != result["current_trend"])
      result["eligible"] = valid & (pd.to_numeric(result["total_signals"], errors="coerce") >= 30)
      return result
  ```

- [x] **Step 4: Run focused tests and verify GREEN.** Host fallback: 11 validation tests passed; page test remained blocked by missing Streamlit.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_validation tests.test_analyze_trend_classification -v
  ```

  Expected: all focused tests pass, including the existing page-local advice contract.

- [x] **Step 5: Review helper against production contracts.** Validation helper is unused by normal UI/API paths; production thresholds and protected SQL/storage files were unchanged.

### Task 2: Build a Read-Only Database Probe

**Files:**
- Create: `scripts/validate_trend_classification.py`
- Test: `tests/test_trend_classification_probe.py`

**Interfaces:**
- Consumes: `get_engine_with_retry()`, a deterministic ticker sample, fixed `(validation_days, result_days)` windows, and `analyze_ticker()`.
- Produces: a CSV/Markdown-ready observation DataFrame containing database-derived probabilities plus legacy/current classifications; no application runtime side effect.

- [x] **Step 1: Write failing probe tests with mocks.** Test that the collector calls `analyze_ticker()` once per ticker/window pair; keeps `None` and zero-signal results in an exclusion summary; preserves ticker, windows, dates, current delta, signal count, and probabilities; and produces deterministic row ordering.

  ```python
  def test_collects_database_probability_fields_without_recomputing_them(self):
      fake = {
          "ticker": "AAA", "start_date": "2025-01-01", "end_date": "2025-01-07",
          "current_delta": 2.0, "total_signals": 40,
          "possibility_up": 40.0, "possibility_down": 10.0,
      }
      records, excluded = collect_probability_records(
          ["AAA"], [(5, 5)], fake_analyzer=lambda *args: fake
      )
      self.assertEqual(records.iloc[0]["possibility_up"], 40.0)
      self.assertEqual(excluded, [])
  ```

- [x] **Step 2: Run probe tests and verify RED.** Host fallback failed first because the new `scripts` module did not exist; Docker was unavailable.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_trend_classification_probe -v
  ```

  Expected: FAIL because the collector module does not exist.

- [x] **Step 3: Implement deterministic collection.** In `scripts/validate_trend_classification.py`, select at most 64 tickers with one parameterized `sqlalchemy.text()` query, exclude `VNINDEX`, require at least 260 trading rows, and order by ticker. Use fixed windows `(5, 5)`, `(10, 5)`, and `(20, 10)`. Call existing `analyze_ticker()` for each pair so probability aggregates come from the established `BASE_DELTA_CALC_CTE` path. Record `None`, insufficient signals, and exceptions separately with ticker/window/reason; do not fabricate zero probabilities. Apply `compare_trend_classifications()` only to valid rows. Write no database rows and do not mutate application state.

  ```python
  TICKER_QUERY = text("""
      SELECT ticker
      FROM trading_data
      WHERE ticker <> :excluded_ticker
      GROUP BY ticker
      HAVING COUNT(*) >= :minimum_rows
      ORDER BY ticker
      LIMIT :ticker_limit
  """)

  WINDOWS = ((5, 5), (10, 5), (20, 10))

  def collect_probability_records(tickers, windows, engine, analyzer=analyze_ticker):
      records, excluded = [], []
      for ticker in tickers:
          for validation_days, result_days in windows:
              try:
                  result = analyzer(ticker, validation_days, result_days, engine)
              except Exception as error:
                  excluded.append({"ticker": ticker, "validation_days": validation_days,
                                   "result_days": result_days, "reason": str(error)})
                  continue
              if not result or not result.get("total_signals"):
                  excluded.append({"ticker": ticker, "validation_days": validation_days,
                                   "result_days": result_days, "reason": "no valid signals"})
                  continue
              records.append({"ticker": ticker, "validation_days": validation_days,
                              "result_days": result_days, "signal_date": result["end_date"],
                              "current_delta": result["current_delta"],
                              "total_signals": result["total_signals"],
                              "possibility_up": result["possibility_up"],
                              "possibility_down": result["possibility_down"]})
      return pd.DataFrame(records), excluded
  ```

- [x] **Step 4: Run probe tests and verify GREEN.** Host fallback: 3 mocked probe tests passed.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_trend_classification_probe -v
  ```

  Expected: all mocked collection tests pass.

### Task 3: Run Empirical Validation and Produce Divergence Report

**Files:**
- Create: `docs/superpowers/reports/2026-08-02-trend-classification-validation.md`
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

**Interfaces:**
- Consumes: probe output from Task 2.
- Produces: reproducible sample metadata, divergence breakdown, and an explicit decision on whether a separate production-change proposal is justified.

- [x] **Step 1: Run the read-only probe in Docker.** Healthy PostgreSQL run completed: 64 tickers, 190 valid rows, 2 excluded, 151 eligible.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python scripts/validate_trend_classification.py --limit 64
  ```

  Record command date, ticker count, windows, valid rows, excluded rows, and database/container status.

- [x] **Step 2: Validate report calculations.** Report includes valid/excluded/eligible counts, legacy/current counts, changed rates, transition matrix, dominant outcomes, probability context, signal-count context, and direct-Down versus low-Up interpretation.

- [x] **Step 3: Review against acceptance rules.** No threshold change was made; Down-dominant Sideways cases are documented for separate product review.

- [x] **Step 4: Update project status.** Report, `FOCUS.md`, and `ai-context/current-status.md` record results; the item moved out of WIP; the full-history SQL warning remains separate.

### Task 4: Final Verification and Handoff

**Files:**
- Verify: all files changed by Tasks 1–3
- Do not modify: `IMPLEMENTED.md`, `app/commons/common_queries.py`, `app/data_preparation.py`, `docker/`

- [x] **Step 1: Run focused validation tests.** Docker focused validation/page/probe suite passed 22/22.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_validation tests.test_analyze_trend_classification tests.test_trend_classification_probe -v
  ```

- [x] **Step 2: Run the full suite.** Docker discovery passed 137/137.

  ```powershell
  docker compose -f docker/docker-compose.yml exec -T app python -B -m unittest discover -s tests -p "test_*.py"
  ```

  Expected: zero failures; record exact count.

- [x] **Step 3: Check boundaries and whitespace.** `git diff --check` exits cleanly apart from normal CRLF warnings; protected-path diff is empty.

  ```powershell
  git diff --check
  git diff --name-only -- IMPLEMENTED.md app/commons/common_queries.py app/data_preparation.py docker Dockerfile docker-compose.yml
  ```

  Expected: first command exits 0; second command prints no paths.

- [x] **Step 4: Self-review logic, SQL, and performance.** Helpers are pure; the probe reuses `analyze_ticker()` and bounded deterministic windows; no production classifier output changed.

- [x] **Step 5: Handoff.** Report records the exact sample, divergence rates, findings, test counts, and separate-review recommendation; no recalibration plan is warranted from this descriptive sample alone.

## Self-Review of This Plan

- Scope covered: classifier contracts, pure tests, database collection, empirical report, status synchronization, and final verification.
- No placeholders remain; every task names files, interfaces, commands, and expected outcomes.
- Type consistency: collector returns `(records, excluded)`; comparison consumes records and adds classification columns; report consumes the annotated frame.
- Explicit gap: live PostgreSQL execution is required to produce findings; if Docker/PostgreSQL is unavailable, stop after mocked tests and document the blocker instead of inferring market behavior.
