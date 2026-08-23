# Price Display and Export Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale database prices to k VND for UI and Plotly display while preserving original BIGINT price values in every export CSV.

**Architecture:** Add one pure helper in `app/commons/price_utils.py` with explicit `ui` and `export` output contexts. Technical data calls the UI context after database retrieval; export formatting calls the export context and never changes values. SQL and database storage remain untouched.

**Tech Stack:** Python 3.12, pandas, Streamlit, Plotly, unittest, Docker Compose.

## Global Constraints

- Keep database prices stored as BIGINT values multiplied by 1000.
- Divide prices by 1000 only for UI/Plotly-facing technical data.
- Export functions always preserve original BIGINT price values, independent of optional columns or percentage-change settings.
- Do not divide prices in SQL.
- Do not modify `common_queries.py`, database schema, Docker files, credentials, or `IMPLEMENTED.md`.
- Keep volume unchanged.
- Use existing raw database connections and parameter binding.

### Task 1: Add Failing Price-Context Tests

**Files:**
- Create: `tests/test_price_utils.py`
- Modify: `tests/test_analyze_export.py`

**Interfaces:**
- Test target: `prepare_price_for_output(values, output)`.
- Test contexts: `PRICE_OUTPUT_UI` and `PRICE_OUTPUT_EXPORT`.

- [x] **Step 1: Write the failing shared-helper tests**

```python
def test_ui_context_scales_price_to_k_vnd():
    result = prepare_price_for_output(pd.Series([50300, 121350]), PRICE_OUTPUT_UI)
    self.assertEqual(result.tolist(), [50.3, 121.35])

def test_export_context_preserves_original_price():
    source = pd.Series([50300, 121350])
    result = prepare_price_for_output(source, PRICE_OUTPUT_EXPORT)
    pd.testing.assert_series_equal(result, source)
```

Add export assertions proving both close-only and full-OHLC export retain `[50300, 121350]`, regardless of `include_percentage_change` and `include_ohlc_volume`.

- [x] **Step 2: Run tests and verify the expected RED state**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_price_utils tests.test_analyze_export
```

Expected: failure because `commons.price_utils` and the new output-context behavior do not exist yet; no production code is changed before this failure.

### Task 2: Implement the Shared Output-Context Helper

**Files:**
- Create: `app/commons/price_utils.py`

**Interfaces:**
- Consumes: scalar or pandas Series price values and an explicit output context.
- Produces: UI values divided by 1000; export values unchanged.

- [x] **Step 1: Implement the minimal helper**

```python
PRICE_OUTPUT_UI = "ui"
PRICE_OUTPUT_EXPORT = "export"


def prepare_price_for_output(values, output):
    if output == PRICE_OUTPUT_EXPORT:
        return values
    if output != PRICE_OUTPUT_UI:
        raise ValueError(f"Unsupported price output: {output}")
    return pd.to_numeric(values, errors="coerce") / 1000
```

- [x] **Step 2: Run shared-helper and export tests**

Run the command from Task 1. Expected: all targeted tests pass.

### Task 3: Normalize Technical UI Data

**Files:**
- Modify: `app/commons/technical_analysis.py:191-253`
- Modify: `app/pages/technical_visualization.py:286-306`

**Interfaces:**
- `fetch_data()` continues returning a DataFrame with the same OHLCV columns, but price columns are UI-scaled numeric values.
- Volume remains unchanged.

- [x] **Step 1: Add a regression test for `fetch_data()`**

Mock `pd.read_sql` with BIGINT OHLCV values, call `fetch_data()` using a mocked engine, and assert:

```python
self.assertEqual(result.loc[0, ["open", "high", "low", "close"]].tolist(), [49.9, 50.3, 49.5, 50.0])
self.assertEqual(result.loc[0, "volume"], 2500000)
```

- [x] **Step 2: Run the regression test and verify RED**

Run the focused technical scaling test in Docker. Expected: price assertions fail because current `fetch_data()` returns raw BIGINT values.

- [x] **Step 3: Apply UI context after fetch/resampling**

Import `PRICE_OUTPUT_UI` and `prepare_price_for_output`. After `tail(limit).reset_index()`, apply the helper to `open`, `high`, `low`, and `close`; leave `volume` untouched. Do not alter SQL or database values.

- [x] **Step 4: Label Plotly values as k VND**

Set the price-axis title to `Price (k VND)` and use k VND in price hover labels. Keep numeric values numeric for indicators and Plotly.

- [x] **Step 5: Run the regression and Task 2 focused suite**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec -T app python -m unittest discover -s /app/tests -p 'test_technical_*.py'
docker compose -f docker/docker-compose.yml exec -T app python -m unittest discover -s /app/tests -p 'test_adx_gating.py'
```

Expected: all technical/UI tests pass, including the new scaling regression.

### Task 4: Preserve Raw Export Values

**Files:**
- Modify: `app/pages/analyze_visualization.py:99-150`
- Modify: `tests/test_analyze_export.py`

**Interfaces:**
- `fetch_export_history()` continues retrieving original BIGINT values.
- `format_export_dataframe()` always applies `PRICE_OUTPUT_EXPORT` to price columns; options only control which columns appear.

- [x] **Step 1: Change export assertions to raw-value expectations**

Expected close-only CSV values: `[100000, 110000]`, not `[100.0, 110.0]`.

Expected full-OHLC CSV values remain original raw values for open, high, low, and close; volume remains unchanged.

- [x] **Step 2: Run export tests and verify RED**

Run the export test module. Expected: close-only scaling assertion fails before production change.

- [x] **Step 3: Use the shared helper with export context**

Replace conditional `/1000` conversion with `prepare_price_for_output(price_values, PRICE_OUTPUT_EXPORT)`. Keep percentage-change calculation unchanged; ratios are identical on raw versus scaled prices.

- [x] **Step 4: Run export tests and verify GREEN**

Run the export test module in Docker. Expected: all export tests pass and both option paths preserve raw prices.

### Task 5: Final Verification and Review

**Files:**
- Inspect only: `FOCUS.md`, `ai-context/current-status.md`, `IMPLEMENTED.md`

- [x] **Step 1: Run all relevant focused tests**

Run technical scaling/UI, snapshot, ADX, export, and shared-flow tests in Docker. Record exact pass counts.

- [x] **Step 2: Run static checks**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec -T app python -c "import ast, pathlib; ast.parse(pathlib.Path('/app/commons/price_utils.py').read_text()); ast.parse(pathlib.Path('/app/commons/technical_analysis.py').read_text()); ast.parse(pathlib.Path('/app/pages/analyze_visualization.py').read_text()); print('AST: OK')"
docker compose -f docker/docker-compose.yml exec -T app curl -fsS http://localhost:3501/_stcore/health
git diff --check
```

- [x] **Step 3: Review boundaries**

Confirm no SQL division, no storage/schema changes, no export raw-value regression, no `common_queries.py` changes, and no `IMPLEMENTED.md` changes.

- [x] **Step 4: Apply implementation self-review**

Check logic, performance, SQL safety, and UI display units. Report any remaining full-suite or browser-smoke limitation before moving to the next task.
