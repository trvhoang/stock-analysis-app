# Backtest V2 Multi-Metric Certified Candidates and Sequential Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store each exact winning strategy once with every metric it wins, and collect up to five ticker Backtests through one sequential background batch job.

**Architecture:** The artifact contract moves directly from V1 metric-keyed mappings to V2 candidate lists. A single metric registry and V2 indexer gives replay, catalog, validation advice, and position references a metric view without duplicating a candidate. The page sends one immutable batch request to one worker; the worker computes shared VN-Index confirmation once, processes tickers sequentially, records retry outcomes atomically, and exposes a single polled status sidecar.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, SQLAlchemy, PostgreSQL, Docker, unittest, Streamlit AppTest.

## Global Constraints

- Artifact schema is V2 only. `load_certified_signals()` rejects V1; it must not convert, fallback, or read V1 artifact content.
- Delete V1 artifacts only after every V2 verification gate passes. Delete exact verified artifact files only; do not delete or regenerate database data, positions, status sidecars, directories, or V2 files.
- One candidate represents multiple metrics only when independent metric ranking selects the exact same `IndicatorCombo`. Comparison must use the immutable combo value, never rounded performance fields.
- Preserve all certification and trading rules: independent metric ranking, `n >= 30`, qualification gates, Deflated Sharpe, permutation, audit, long-only BUY entry, ATR exits, and current horizon timing.
- Use one public ordered metric registry: `("win_rate", "profit", "sharpe")`. A future metric is added once to this registry together with its selector; all V2 grouping and readers consume that registry.
- No theme batch: process input tickers one at a time. Theme batch: preflight VN-Index confirmation once, then process every ticker one at a time and write its no-theme artifact followed by its VN-Index AND artifact.
- Ticker input is comma/space separated, auto-capitalized, order-preserving, unique, and limited to one through five ticker symbols.
- A first-pass ticker error never stops sibling tickers. Retry each failed ticker once, in original order, after first pass; retain terminal failure information if retry fails.
- A shared VN-Index preflight error waits exactly five seconds, retries once, and then fails the entire batch before ticker work if still unsuccessful.
- Overall batch status is `done` when ticker retries finish, including terminal ticker failures. Overall `failed` is only malformed request/worker failure or terminal shared VN-Index preflight failure.
- Keep current position-history files readable and unchanged. Their legacy frozen scalar snapshots may remain valid only inside the position-history reader; this is not V1 artifact compatibility.
- Keep all prices raw BIGINT in persistence and divide by 1000 only through the established UI output boundary. Do not change SQL, `common_queries.py`, `data_preparation.py`, credentials, Docker files, dependencies, or commit history.
- Use `get_engine_with_retry()` and `engine.raw_connection()` for any new database work. This plan adds no SQL query.
- No commit. The user manages commit history separately.

## File Map

- `app/backtest_engine/persistence.py` — single metric registry; strict V2 artifact validator, save/load, and metric-to-candidate index.
- `app/backtest_engine/certify.py` — independent metric ranking and exact-combo candidate grouping.
- `app/backtest_engine/early_warning.py`, `signal_catalog.py`, `validation_advice.py` — read/replay a grouped V2 candidate once and present all of its metrics.
- `app/backtest_engine/position_store.py`, `position_identity.py`, `position_overview.py` — create multi-metric frozen references from one V2 candidate while retaining already-saved position snapshots.
- `app/backtest_engine/config.py`, `models.py`, `job_runner.py`, `worker.py` — immutable batch request, atomic per-ticker status, and worker request dispatch.
- `app/backtest_engine/pipeline.py` — shared theme preflight and deterministic sequential/retry batch execution.
- `app/pages/backtest_lab.py` — batch input, one job lifecycle, per-ticker status, and one result section/row per grouped candidate.
- `tests/test_backtest_*.py` — focused RED/GREEN coverage for each boundary above.
- `FOCUS.md`, `ai-context/current-status.md`, and a dated verification report — progress and final evidence.

---

### Task 1: Define V2 certification groups and strict artifact persistence

**Files:**
- Modify: `app/backtest_engine/certify.py:1-82`
- Modify: `app/backtest_engine/persistence.py:1-150`
- Modify: `tests/test_backtest_certification.py`
- Modify: `tests/test_backtest_persistence.py`

**Interfaces:**
- Produces `CERTIFICATION_METRICS: tuple[str, ...]` from `persistence.py`, the sole ordered registry.
- Produces `certify_top_sets(candidates: Sequence[ValidatedCandidate], min_n: int = 30) -> list[dict[str, object]]`.
- Produces `index_signal_sets(signal_sets: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]`.
- Produces V2 `save_certified_signals(ticker, signal_sets, theme_variant, output_dir, *, audit_eligibility=None) -> str` and strict V2 `load_certified_signals(path) -> dict[str, object]`.
- V2 candidate shape is `{"metrics": list[str], "combo": dict, "horizon": str, "theme_variant": str, "theme_mode": str | None, "vnindex_condition": dict | None, "direction": "long", "n": int, "win_rate": float, "profit": float, "sharpe": float, "deflated_sharpe": float, "p_value": float | None, "date_range": list[str]}`.

- [x] **Step 1: Write RED certification tests for unique candidate groups**

Create `tests/test_backtest_certify.py` with three qualified fixtures whose
`combo` values are distinct, plus one ineligible fixture. Assert exact winner
grouping and registry order:

```python
signal_sets = certify_top_sets(candidates, min_n=30)
self.assertEqual(
    [candidate["metrics"] for candidate in signal_sets],
    [["win_rate", "profit"], ["sharpe"]],
)
self.assertEqual(signal_sets[0]["combo"], combo_a.to_dict())
self.assertNotIn("metric", signal_sets[0])
```

Add a three-metric tie-to-one-combo case, a three-distinct-winner case, an
empty-qualified case returning `[]`, and a deterministic ordering case where
the first metric represented by each group controls list order. Assert metric
rankings still choose the same winners that the old independent loops choose.

- [x] **Step 2: Run certification RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_certification -v
```

Expected: FAIL because the current function returns a dictionary with scalar
`metric` values and does not emit groups.

- [x] **Step 3: Implement exact-combo grouping without changing ranking gates**

Move the ordered metric constant to `persistence.py` as public
`CERTIFICATION_METRICS`, and import it in `certify.py`. Keep one selector per
metric. First select each metric independently from the existing eligible
population, then group selected candidates by `ValidatedCandidate.combo`:

```python
winners = {
    metric: max(eligible, key=metric_selectors[metric])
    for metric in CERTIFICATION_METRICS
} if eligible else {}

groups: dict[IndicatorCombo, list[str]] = {}
for metric in CERTIFICATION_METRICS:
    candidate = winners.get(metric)
    if candidate is not None:
        groups.setdefault(candidate.combo, []).append(metric)
return [_serialize_candidate(combo, metrics) for combo, metrics in groups.items()]
```

Make `_serialize_candidate()` receive the candidate and its complete metrics
list, emit `metrics`, and remove scalar `metric`. Keep every existing
performance, combo, date-range, theme, and long-only field unchanged.

- [x] **Step 4: Write RED V2 persistence tests**

Replace V1 fixtures in `tests/test_backtest_persistence.py` with V2 candidate
lists. Test a two-metric candidate and a single-metric candidate; assert saved
JSON has `schema_version == 2`, `empty is False`, and a list-valued
`signal_sets`. Add rejection tests for every contract boundary:

```python
with self.assertRaisesRegex(ValueError, "non-empty"):
    save_certified_signals("FPT", [{"metrics": []}], "no-background-theme", root)
with self.assertRaisesRegex(ValueError, "duplicate metric"):
    save_certified_signals("FPT", [candidate(["win_rate"]), candidate(["win_rate"])], variant, root)
with self.assertRaisesRegex(ValueError, "unsupported certified signal schema version"):
    load_certified_signals(str(v1_path))
```

Also assert registry ordering is required, absent metrics are allowed,
cross-candidate duplicate metrics fail, theme metadata remains validated,
atomic overwrite leaves no temporary files, and `index_signal_sets()` maps
both `win_rate` and `profit` to the same candidate object.

- [x] **Step 5: Run persistence RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_persistence -v
```

Expected: FAIL because the current writer requires three scalar metric slots
and the loader accepts only schema version 1.

- [x] **Step 6: Implement strict V2 validation, indexing, and atomic write**

Replace `_normalize_signal_sets()` with a list-only validator. Require every
candidate field above, validate its `metrics` against
`CERTIFICATION_METRICS`, require registry ordering, and use one `seen_metrics`
set to reject a metric in two candidates. Validate candidate/artifact theme
consistency and current VN-Index metadata rules. Compute `empty` as
`not normalized_sets`; save `schema_version: 2`; keep the existing temporary
file, `fsync`, and `os.replace` atomic sequence.

Implement `index_signal_sets()` by validating the V2 list then assigning each
candidate to every listed metric. `load_certified_signals()` must parse JSON,
require version `2`, require a list, invoke the same validator, and return the
unchanged payload. It must never inspect, transform, or load V1 content.

- [x] **Step 7: Prove Task 1 GREEN**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_certification tests.test_backtest_persistence -v
```

Expected: PASS. Exact-combo multi-metric grouping, deterministic order, V2
strictness, indexing, atomic overwrite, and audit metadata all pass.

### Task 2: Convert replay, catalog, advice, and frozen references to one grouped candidate

**Files:**
- Modify: `app/backtest_engine/early_warning.py:1-305`
- Modify: `app/backtest_engine/signal_catalog.py:1-294`
- Modify: `app/backtest_engine/validation_advice.py:1-270`
- Modify: `app/backtest_engine/position_store.py:25-180`
- Modify: `app/backtest_engine/position_identity.py:1-95`
- Modify: `app/backtest_engine/position_overview.py:1-95`
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `tests/test_backtest_signal_catalog.py`
- Modify: `tests/test_backtest_position_store.py`
- Modify: `tests/test_backtest_position_overview.py`

**Interfaces:**
- Consumes only `load_certified_signals()` and `index_signal_sets()` for artifact reads.
- Keeps `check_current_situation(ticker: str, metric: str = "all", theme_variant: str = "no-background-theme", engine: object | None = None, output_dir: str | None = None) -> dict[str, object]` public.
- Produces `list_saved_signal_options(ticker: str, signal_dir: str = "ticker-signals") -> list[dict[str, object]]` with one option per V2 candidate and a complete `metrics` list.
- Changes `prepare_signal_reference(ticker: str, theme_variant: str, metrics: Sequence[str], engine: object, signal_dir: str = "ticker-signals") -> dict[str, object]`, where `metrics` is the complete candidate metric list.

- [x] **Step 1: Write RED replay tests for no duplicate candidate evaluation**

Convert replay fixtures to V2 documents. For one `metrics=["win_rate",
"profit"]` candidate, patch the internal signal evaluator and assert that an
`metric="all"` replay invokes it once while `results["win_rate"]` and
`results["profit"]` expose the same certified strategy. Assert a requested
single listed metric works, an absent metric returns the existing
no-certified-result response, and `metric="sharpe"` never evaluates the
unlisted candidate.

```python
result = check_current_situation("FPT", metric="all", engine=engine, output_dir=root)
self.assertEqual(evaluate.call_count, 1)
self.assertEqual(result["results"]["win_rate"]["certified"]["metrics"], ["win_rate", "profit"])
self.assertEqual(result["results"]["profit"]["certified"]["metrics"], ["win_rate", "profit"])
```

- [x] **Step 2: Run replay RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_early_warning -v
```

Expected: FAIL because current replay assumes a dictionary keyed by each
scalar metric and prepares the same candidate twice.

- [x] **Step 3: Implement one replay per V2 candidate**

Use `index_signal_sets()` only to resolve requested metric names. Build an
ordered unique candidate collection by candidate list position, construct one
replay context per candidate, evaluate once, then assign its result to every
listed requested metric. Preserve the old public `results` mapping so
`validation_advice.py` can continue to compose one advisory view per metric.
For single-metric calls, return the selected result unchanged except the
certified payload now has `metrics` rather than `metric`.

- [x] **Step 4: Write RED catalog and reference tests**

Create one V2 artifact with `["win_rate", "profit"]` and one Sharpe-only
candidate. Assert catalog output creates two rows, not three, and labels the
first row `Win Rate / % Profit`. Assert saved-signal options produce two
options with `metrics == ["win_rate", "profit"]` and no scalar `metric`.
Patch replay in `prepare_signal_reference()` and assert it creates one frozen
`signal_reference` whose `metrics` and `certified_signals` both contain the
complete list.

Add position compatibility tests: an existing saved position whose frozen
snapshot has legacy scalar `metric: "win_rate"` remains readable; a newly
created V2 snapshot requires `metrics` and membership of the requested metric.
Loading a V1 artifact is never part of either test.

- [x] **Step 5: Run catalog/reference RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_position_store tests.test_backtest_position_overview -v
```

Expected: FAIL because catalog/options iterate scalar artifact slots and
position validation requires a scalar artifact `metric` field.

- [x] **Step 6: Implement grouped readers and position snapshot boundary**

Replace local `_METRICS` duplicates with the public registry. Catalog each
candidate once; render joined metric titles in registry order. Offer one saved
set per candidate and pass its full metric list to replay/reference creation.
For a new reference, place the same immutable V2 candidate snapshot under
each listed metric key so existing link-key and open-position checks remain
per metric.

In `_validated_certified_signal()`, accept a V2 candidate only if the
requested metric is in its `metrics` list. Retain the existing scalar
`metric == requested_metric` branch solely for an already-persisted position
snapshot. Do not add that branch to persistence, replay, catalog, or artifact
loading. Update validation advice and overview iterations to consume indexed
V2 candidates and preserve existing no-position/open-position behavior.

- [x] **Step 7: Prove Task 2 GREEN**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_early_warning tests.test_backtest_signal_catalog tests.test_backtest_position_store tests.test_backtest_position_overview tests.test_backtest_position_monitor -v
```

Expected: PASS. One candidate replays once, catalog/options do not duplicate
it, current positions still read, and advice remains available per listed
metric.

### Task 3: Add the immutable batch request and atomic per-ticker job status

**Files:**
- Modify: `app/backtest_engine/config.py:1-150`
- Modify: `app/backtest_engine/models.py:148-180`
- Modify: `app/backtest_engine/job_runner.py:70-265`
- Modify: `app/backtest_engine/worker.py:1-80`
- Modify: `tests/test_backtest_job_runner.py`
- Create: `tests/test_backtest_worker.py`

**Interfaces:**
- Produces `BacktestBatchConfig(tickers: tuple[str, ...], start_date: date | None = None, end_date: date | None = None, horizon: str = "swing", include_theme: bool = False, threshold_score_buy: int = COMPACT_ENTRY_SCORE, rolling_window_months: int = 6, rolling_stride_months: int = 1, atr_period: int = 14, atr_sl_multiplier: float = 1.5, atr_tp_multiplier: float = 2.5, max_hold_bars: int | None = None, min_n: int = 30, permutation_count: int = 1000, permutation_seed: int = 42, permutation_block_size: int = 20, deflated_sharpe_cutoff: float = 0.95, permutation_alpha: float = 0.05, worker_count: int = 6, output_dir: str = "ticker-signals")` with `to_dict()` containing `request_type: "backtest_batch_v2"`.
- Produces `BatchTickerStatus(ticker: str, attempts: int, state: str, output_paths: tuple[str, ...] = (), error_texts: tuple[str, ...] = ())`.
- Extends `JobStatus(job_id: str, state: str, progress: float = 0.0, output_paths: tuple[str, ...] = (), error_text: str | None = None, ticker_results: tuple[BatchTickerStatus, ...] = ())`.
- Extends progress callback shape to `report_progress(value: float, ticker_results: tuple[BatchTickerStatus, ...] | None = None) -> None`; omitted results retain the last atomic ticker snapshot, so current one-argument pipeline reporters stay valid.
- Worker dispatch returns either `BacktestConfig` for an existing single request or `BacktestBatchConfig` only when `request_type == "backtest_batch_v2"`.

- [x] **Step 1: Write RED batch configuration and status tests**

Test config normalization/rejection directly:

```python
config = BacktestBatchConfig(tickers=("fpt", "vcb"), horizon="swing")
self.assertEqual(config.tickers, ("FPT", "VCB"))
with self.assertRaisesRegex(ValueError, "duplicate"):
    BacktestBatchConfig(tickers=("FPT", "fpt"))
with self.assertRaisesRegex(ValueError, "between 1 and 5"):
    BacktestBatchConfig(tickers=())
```

Test invalid symbols, six unique tickers, unsupported horizon, and JSON date
round-trip. Add `JobStatus("job-1", "running", ticker_results=(BatchTickerStatus("FPT", 1, "running"),))`
round-trip tests. Verify a reporter update persists ticker progress and errors
without losing output paths, and the terminal `done` sidecar retains the full
ordered ticker result list.

- [x] **Step 2: Run job-contract RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_job_runner tests.test_backtest_worker -v
```

Expected: FAIL because batch configuration/status types, request
discrimination, and ticker-status serialization do not exist.

- [x] **Step 3: Implement batch config, status serialization, and worker dispatch**

Add `BacktestBatchConfig` beside `BacktestConfig`. Add a shared private ticker
normalizer in `config.py` using the existing `[A-Z0-9._-]+` contract, then make
`persistence.py` import it instead of retaining a second implementation.
Normalize every batch ticker, reject a duplicate rather than silently dropping
it at this lower boundary, and let the UI parser remove duplicate input before
construction. Validate horizon and every shared setting listed in the interface
with the same constraints as `BacktestConfig`.

Add `BatchTickerStatus` validation: uppercased nonblank ticker, attempts `0`
only while queued and `1..2` otherwise, state in `queued/running/done/failed`, tuple output paths, and
JSON-safe error text. Add `ticker_results` to `JobStatus.to_dict()` and
`read_job_status()`; defaults keep existing single-job tests valid.

Allow the runner reporter to receive optional ticker results and atomically
write them with monotonic progress. Extract result paths and ticker results
from a batch factory result shaped as:

```python
{"output_paths": ["ticker-signals/FPT/FPT_signals_no-background-theme.json"], "ticker_results": [status.to_dict()]}
```

Update worker parsing to dispatch explicit `request_type` to
`BacktestBatchConfig`; reject any other explicit request type. Retain normal
`BacktestConfig` parsing for existing unit-level single-job paths.

- [x] **Step 4: Prove Task 3 GREEN**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_job_runner tests.test_backtest_worker -v
```

Expected: PASS. Requests and status sidecars are atomic, typed, spawn-safe,
and preserve per-ticker retries/errors without changing single-job behavior.

### Task 4: Run V2 artifacts through one shared-theme sequential pipeline

**Files:**
- Modify: `app/backtest_engine/pipeline.py:1-155`
- Modify: `tests/test_backtest_pipeline.py`

**Interfaces:**
- Keeps `run_backtest_pipeline(config: BacktestConfig, report_progress, engine) -> list[str]` for single-ticker test compatibility, but it writes V2 artifacts from Task 1.
- Produces `run_backtest_batch_pipeline(config: BacktestBatchConfig, report_progress, engine) -> dict[str, object]`.
- Produces `run_backtest_batch_from_env(config: BacktestBatchConfig, report_progress) -> dict[str, object]` as the module-level spawn-safe worker factory.
- Batch factory result contains `output_paths` and JSON-safe `ticker_results` in input ticker order.

- [x] **Step 1: Write RED V2 pipeline tests**

Update existing one-ticker pipeline assertions to expect a V2 list. Add a
no-theme batch test with `("FPT", "VCB", "MBB")`: patch history loading,
indicator construction, certification, and save; assert call order completes
all FPT work before VCB begins and VCB before MBB, with exactly one no-theme
artifact per ticker.

Add themed batch tests that assert:

```python
self.assertEqual(vnindex_history_calls, ["VNINDEX"])
self.assertEqual(build_confirmation.call_count, 1)
self.assertEqual(alignment.call_count, 3)
self.assertEqual(saved_variants["FPT"], ["no-background-theme", "background-theme"])
```

Use a first-pass FPT exception, VCB success, and FPT retry success to prove
retry occurs after all first-pass tickers. Add a final-failure test asserting
the factory returns normally with overall `done` semantics and a failed FPT
record containing both error texts. Add a preflight failure test that patches
`time.sleep`: assert `sleep(5)`, two VN-Index attempts, no ticker load, and a
clear raised `RuntimeError` after the second failure.

- [x] **Step 2: Run pipeline RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_pipeline -v
```

Expected: FAIL because the pipeline accepts one variant, reloads VN-Index per
themed run, has no batch status, and does not retry tickers.

- [x] **Step 3: Factor single-ticker preparation from variant evaluation**

Keep date-window behavior unchanged: if configured start predates available
history, `load_ticker_history()` supplies all available rows and existing
indicator calculations use those rows. Extract these exact helpers:
`_prepare_ticker(ticker: str, config: BacktestConfig, engine) -> tuple[pd.DataFrame, HistoryAudit]`,
`_run_variant(frame: pd.DataFrame, audit: HistoryAudit, config: BacktestConfig,
theme_variant: str, confirmation_frame: pd.DataFrame | None) -> str`, and
`_build_confirmation_frame(vnindex: pd.DataFrame, horizon: str) -> pd.DataFrame`.

`_prepare_ticker()` loads, validates OHLCV, audits, and builds indicators once.
`_run_variant()` selects only that variant's combos, aligns an already-built
confirmation frame as-of ticker dates only for the themed variant, validates,
certifies, and atomically saves V2. Do not alter OHLCV validation or convert
raw prices.

- [x] **Step 4: Implement batch sequence, retry, and truthful progress**

In `run_backtest_batch_pipeline()`, create ordered queued
`BatchTickerStatus` records. If `include_theme` is true, preflight VN-Index
once. On the first preflight error, call `time.sleep(5)` then repeat the same
load/validate/build operation once. On the second error, raise:

```python
raise RuntimeError(f"VN-Index preflight failed after retry: {error}") from error
```

For each first-pass ticker, mark running, prepare it once, save no-theme, then
save VN-Index AND only when requested. Catch a ticker exception, append its
typed error string, mark it failed, report status, and continue. After that
pass, retry only failed tickers in original order. A retry success replaces
the failure state with `done` and keeps attempts at two; retry failure remains
`failed` with both error strings. Return paths in ticker/variant order and
records in original input order. Progress must never decrease; report status
after preflight, each transition, and final completion.

`run_backtest_batch_from_env()` obtains one engine through
`get_engine_with_retry(_database_url())`, calls the batch pipeline, and
disposes it in `finally`. It must not make database, credential, or Docker
configuration changes.

- [x] **Step 5: Prove Task 4 GREEN**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_pipeline tests.test_backtest_certification tests.test_backtest_persistence -v
```

Expected: PASS. V2 saving, strict sequence, one shared themed preflight,
five-second fatal retry, ticker retry, terminal failure recording, and
unchanged date/quality behavior all pass.

### Task 5: Replace Collect Signals with one batch lifecycle and grouped V2 results

**Files:**
- Modify: `app/pages/backtest_lab.py:150-380, 2124-2215`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- Produces `parse_batch_tickers(value: str) -> tuple[str, ...]` for comma/space splitting, uppercasing, first-occurrence order, and one-to-five validation.
- Replaces `build_backtest_configs(ticker, horizon, time_range, start_date, end_date, include_theme)` with `build_backtest_batch_config(tickers: tuple[str, ...], horizon: str, time_range: str, start_date: date | None, end_date: date | None, include_theme: bool) -> BacktestBatchConfig`.
- Replaces `submit_run_requests(run_clicked: bool, config: BacktestBatchConfig, submit_fn: Callable, engine_factory: Callable, status_dir: str)` with a function that submits exactly one `BacktestBatchConfig` and returns `(config, job_id) | None`.
- `render_result_artifact(path)` accepts only valid V2 artifact lists and renders one candidate section per list item.

- [x] **Step 1: Write RED page/AppTest coverage**

Add tests that enter `fpt, VCB FPT\nmbb`, select Swing, and click Run. Assert
the submitted batch config contains `("FPT", "VCB", "MBB")`, only one submit
call occurs, and an input with six tickers displays a validation error without
submission. Assert controls lock for queued/running/unreadable status and
unlock only after a terminal status.

Inject a terminal batch status with one successful and one failed ticker.
Assert it displays input order, attempt count, terminal error for the failed
ticker, and renders every successful output path. Inject a V2 multi-metric
artifact and assert one candidate section shows `Win Rate / % Profit`, no
duplicate combo section appears, and missing metrics retain an explicit
no-certified-result message. Assert Markdown download has the same grouping.

- [x] **Step 2: Run page RED**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_page -v
```

Expected: FAIL because the page has a scalar `Ticker`, submits one job per
variant, and iterates V1 metric mappings.

- [x] **Step 3: Implement input parsing and one batch job control**

Replace the Collect Signals text label with `Tickers`; use the existing
uppercasing session-state callback. Implement the parser with
`re.split(r"[\s,]+", value.strip())`, discard empty tokens, retain each first
uppercased occurrence, then construct `BacktestBatchConfig` to enforce format
and count. Keep 15y default, horizon `-` requirement, Custom dates, checkbox
label, and `View Signals` popover behavior.

Store one job entry in session state, submit the batch factory
`run_backtest_batch_from_env`, and reuse automatic polling. During any
queued/running/unreadable batch, disable Tickers, range, horizon, theme, and
Run; do not provide a manual status refresh. Show overall progress and one
ordered ticker line with `ticker`, `attempts`, state, output availability, and
terminal error text.

- [x] **Step 4: Implement V2 result and catalog presentation**

Require list-valued `signal_sets` in page rendering. Render one section per
candidate, titled by its joined human metric labels in registry order. Keep
the current `n`, hit-rate, profit, Sharpe, Deflated Sharpe, p-value, combo,
long-only/ATR caption, downloads, and audit-eligibility warning. For each
registry metric absent from all groups, render one no-certified-result
message. Update Markdown equivalently.

Use Task 2 catalog output unchanged: its Metric cell is one joined label per
candidate. Do not change Validate Signals or Current Positions layout in this
task beyond consuming their Task 2 V2 reader results.

- [x] **Step 5: Prove Task 5 GREEN**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
```

Expected: PASS. One batch job accepts/normalizes 1–5 tickers, locks safely,
polls automatically, presents partial failures, and renders one grouped V2
candidate everywhere on the Collect Signals path.

### Task 6: Complete verification, delete verified V1 artifacts, and synchronize documentation

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-14-backtest-v2-multi-metric-batch-verification.md`
- Delete: exact V1 files resolved under `ticker-signals/<ticker>/<ticker>_signals_<theme>.json`

**Interfaces:**
- Consumes the V2 artifact loader and all focused test suites from Tasks 1–5.
- Produces a dated evidence report with exact command outcomes, V1 deletion list, and no live Backtest execution.

- [x] **Step 1: Run the complete feature gate before any cleanup**

Run:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_certify tests.test_backtest_persistence tests.test_backtest_early_warning tests.test_backtest_signal_catalog tests.test_backtest_position_store tests.test_backtest_position_overview tests.test_backtest_position_monitor tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_pipeline tests.test_backtest_page -v
python -m compileall app/backtest_engine app/pages/backtest_lab.py
git diff --check
git diff -- app/common_queries.py app/data_preparation.py .env app/main.py docker-compose.yml Dockerfile
```

Expected: every focused test passes; compilation and whitespace pass; the
protected-file diff command has no output. Do not delete artifacts if any
command fails.

- [x] **Step 2: Run a non-writing live health check**

Run the existing Docker health endpoint/check used by this project. Confirm
the application and database are healthy without clicking Run backtest or
writing a V2 artifact. Record the exact command, status, and timestamp in the
verification report.

- [x] **Step 3: Inventory exact V1 artifact targets and verify scope**

Run this read-only PowerShell inspection from the repository root:

```powershell
$root = (Resolve-Path -LiteralPath .\ticker-signals).Path
$targets = Get-ChildItem -LiteralPath $root -Recurse -File -Filter "*_signals_*.json" |
  Where-Object {
    try { (Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json).schema_version -eq 1 }
    catch { $false }
  }
$targets | ForEach-Object { $_.FullName }
```

Before deletion, verify every printed path is under the resolved `$root`, has
the expected filename suffix, and is a JSON artifact. Record the exact list in
the verification report. Malformed files, V2 files, position directories,
status directories, database content, and parent directories are never
targets.

- [x] **Step 4: Delete only the inspected V1 file list**

After the scope verification in Step 3, delete each resolved path without a
glob or recursive delete:

```powershell
foreach ($target in $targets) {
  Remove-Item -LiteralPath $target.FullName
}
```

Then re-run the same inventory command and assert it prints no V1 paths.
Report each deleted path and state explicitly that the user will regenerate
signals later; do not launch any Backtest during cleanup.

- [x] **Step 5: Self-critique, document, and mark the feature complete**

Load and execute `ai-skills/skill-implementation-review.md`. Resolve every
finding before completion. Write the verification report with focused test
count, compilation, whitespace/protected-boundary output, health evidence,
V1 inventory/deletion evidence, and known full-discovery limitation if it
still applies. Update `FOCUS.md` to completed with this plan/report and update
`ai-context/current-status.md` to move the WIP item into completed history.
Record no commit.
