# Backtest Runtime Guard and Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the opaque Backtest worker `ValueError: int('')` with a configuration error that identifies an invalid database URL port, retain a traceback in worker logs, and separate signal collection from future validation work in the Backtest Lab.

**Architecture:** The isolated worker continues to receive only its atomic JSON request. Before creating the SQLAlchemy engine, `pipeline.py` validates the already-selected database URL and converts an invalid URL-port parse into a credential-safe runtime error. The job runner records the original traceback in process logs while preserving the existing concise terminal-status contract. The Streamlit page uses native tabs; Collect Signals owns all current page elements and Validate Signals remains intentionally static.

**Tech Stack:** Python 3.12, Streamlit AppTest, SQLAlchemy URL parsing, Docker, unittest.

## Global Constraints

- Work on `feature/revamp-indicator-add-backtest-engine`; do not create, amend, or alter commits.
- Do not modify `app/common_queries.py`, BIGINT scaling, credentials, Docker files, or SQL queries.
- Do not log database URLs or credential values; only the exception traceback and job identifier may be logged.
- No dependencies; use installed SQLAlchemy and Streamlit APIs.
- Do not submit a live job that can overwrite `ticker-signals` solely for this repair.

---

### Task 1: Guard invalid database URLs before the engine is created

**Files:**
- Modify: `app/backtest_engine/pipeline.py`
- Modify: `tests/test_backtest_pipeline.py`

**Interfaces:**
- Consumes: `DATABASE_URL` when present, otherwise the existing `POSTGRES_*` fallback components.
- Produces: `_database_url() -> str`, which returns a parseable PostgreSQL URL or raises `RuntimeError` with a safe invalid-port message.

- [x] **Step 1: Write the failing URL-guard test**

```python
import os
from unittest.mock import patch

from backtest_engine.pipeline import _database_url

def test_database_url_rejects_an_empty_explicit_port(self):
    with patch.dict(
        os.environ,
        {"DATABASE_URL": "postgresql://user:password@db:/stocks"},
        clear=True,
    ):
        with self.assertRaisesRegex(RuntimeError, "invalid port"):
            _database_url()
```

Add a companion assertion using `postgresql://user:password@db:5432/stocks` that confirms valid URLs are returned unchanged.

- [x] **Step 2: Run the focused test and verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_pipeline.BacktestPipelineTests.test_database_url_rejects_an_empty_explicit_port -v`

Expected: FAIL because the existing `_database_url()` returns the malformed string without validating its port.

- [x] **Step 3: Add the smallest safe URL validator**

```python
from sqlalchemy.engine import make_url

def _validate_database_url(database_url: str) -> str:
    try:
        make_url(database_url).port
    except (TypeError, ValueError) as error:
        raise RuntimeError("DATABASE_URL has an invalid port") from error
    return database_url
```

Apply this validator to both the existing `DATABASE_URL` path and the constructed fallback path in `_database_url()`. Do not add fallback/default ports and do not expose the URL in the message.

- [x] **Step 4: Run the focused pipeline tests and verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_pipeline -v`

Expected: PASS; the invalid explicit port returns the safe error and existing pipeline composition remains unchanged.

### Task 2: Preserve full worker diagnostics in process logs

**Files:**
- Modify: `app/backtest_engine/job_runner.py`
- Modify: `tests/test_backtest_job_runner.py`

**Interfaces:**
- Consumes: an exception raised by the worker factory.
- Produces: the unchanged failed `JobStatus` sidecar plus one error log record with `exc_info` and the job identifier.

- [x] **Step 1: Write the failing traceback-log test**

```python
def test_failure_records_an_exception_trace_in_worker_logs(self):
    with self._temporary_status_dir() as directory:
        with self.assertLogs("backtest_engine.job_runner", "ERROR") as logs:
            final = run_backtest_job(
                BacktestConfig.for_ticker("FPT"),
                _failing_engine,
                directory,
            )

    self.assertEqual(final.state, "failed")
    self.assertEqual(len(logs.records), 1)
    self.assertIn(final.job_id, logs.records[0].getMessage())
    self.assertIsNotNone(logs.records[0].exc_info)
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_job_runner.BacktestJobRunnerTests.test_failure_records_an_exception_trace_in_worker_logs -v`

Expected: FAIL because the runner currently persists the terminal status without emitting an exception log record.

- [x] **Step 3: Log the caught factory exception without changing the status payload**

```python
import logging

LOGGER = logging.getLogger(__name__)

# The status remains safe for UI display; stderr retains the traceback needed
# to identify the exact worker callsite in Docker logs.
LOGGER.exception("Backtest job %s failed", job_id)
```

Place `LOGGER.exception(...)` inside `_run_job_with_id()`'s existing `except Exception as error` block before building the failed `JobStatus`. Do not include `config`, `DATABASE_URL`, or other environment values in the log message.

- [x] **Step 4: Run the focused runner tests and verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_job_runner -v`

Expected: PASS; terminal status, monotonic progress, and background lifecycle behavior remain intact.

### Task 3: Separate current signal collection from deferred validation UI

**Files:**
- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- Consumes: the existing page controls, job snapshots, auto-refresh callback, result artifacts, and session state.
- Produces: `Collect Signals` containing every current Backtest interaction and `Validate Signals` containing only an explicit deferred-work placeholder.

- [x] **Step 1: Write the failing tab-layout AppTest**

```python
def test_page_groups_current_ui_under_collect_signals_tab(self):
    app = AppTest.from_string(
        "from pages.backtest_lab import render_backtest_page\n"
        "render_backtest_page(status_dir='unused-status-dir')\n"
    ).run()

    self.assertEqual(
        [tab.label for tab in app.tabs],
        ["Collect Signals", "Validate Signals"],
    )
    self.assertEqual([widget.label for widget in app.text_input], ["Ticker"])
    self.assertTrue(any("Validate Signals" in item.value for item in app.info))
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_page_groups_current_ui_under_collect_signals_tab -v`

Expected: FAIL because the current page renders no tabs.

- [x] **Step 3: Use native Streamlit tabs with no behavior changes to collection**

```python
collect_tab, validate_tab = st.tabs(("Collect Signals", "Validate Signals"))

with collect_tab:
    # Render the existing title, controls, statuses, downloads, and auto-refresh.
    ...

with validate_tab:
    st.info("Validate Signals UI will be added in a later phase.")
```

Keep all existing controls, errors, per-variant results, downloads, and automatic one-second status refresh inside `Collect Signals`. The static tab must create no jobs, read no artifacts, and introduce no validation controls.

- [x] **Step 4: Run focused page tests and verify GREEN**

Run: `docker exec stock_app python -m unittest tests.test_backtest_page -v`

Expected: PASS; no manual refresh button returns, request controls still lock while jobs are busy, and the existing one/two-run configuration behavior is unchanged.

### Task 4: Check the complete repair and synchronize context

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/reports/2026-08-04-backtest-runtime-guard-and-tabs-verification.md`

**Interfaces:**
- Consumes: successful focused test output, compile output, and a non-writing runtime URL preflight.
- Produces: accurate active-task status and reproducible verification evidence.

- [x] **Step 1: Run the cumulative Backtest gate**

Run: `docker exec stock_app python -m unittest tests.test_backtest_certification tests.test_backtest_contracts tests.test_backtest_data_quality tests.test_backtest_early_warning tests.test_backtest_indicators tests.test_backtest_job_runner tests.test_backtest_page tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_rolling_window tests.test_backtest_signal_combos tests.test_backtest_trade_execution tests.test_backtest_validation tests.test_backtest_vnindex_theme -v`

Expected: PASS; no existing Backtest contract, data, worker, or page regression. Explicit module paths are required because the isolated-worker fixtures must remain importable as `tests.test_backtest_job_runner`.

- [x] **Step 2: Run static safety checks**

Run: `docker exec stock_app python -m compileall -q backtest_engine pages/backtest_lab.py`

Run: `git diff --check -- app/backtest_engine/pipeline.py app/backtest_engine/job_runner.py app/pages/backtest_lab.py tests/test_backtest_pipeline.py tests/test_backtest_job_runner.py tests/test_backtest_page.py`

Expected: both commands exit zero.

- [x] **Step 3: Run a non-writing live configuration preflight**

Run a Docker command that imports `_database_url()` in `stock_app` and prints only the parsed driver/host/port, never credentials. Do not submit a job and do not write to `ticker-signals`.

Expected: PostgreSQL driver, host `db`, and port `5432`.

- [x] **Step 4: Self-review and record only verified facts**

Review BIGINT, SQL, performance, logging confidentiality, Streamlit auto-refresh, tab isolation, and protected-boundary compliance. Then update FOCUS/current status and write the verification report with exact commands and results. Keep the task open if any gate fails.

### Task 5: Close the live Compose interpolation incident

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Modify: `docs/superpowers/reports/2026-08-04-backtest-runtime-guard-and-tabs-verification.md`

**Interfaces:**
- Consumes: redacted Streamlit-parent environment, Compose configuration, and
  user confirmation of the corrected live run.
- Produces: a documented operational startup command and closed Backtest
  runtime-configuration status.

- [x] **Step 1: Trace the live error to Compose interpolation**

The live PID 1 process held `POSTGRES_PORT='5432'` but a redacted
`DATABASE_URL` authority of `db:`. The worker traceback confirmed the existing
`DATABASE_URL` branch in `_database_url()` was the failure origin.

- [x] **Step 2: Verify the non-writing fallback and record recovery**

Constructed a URL only from the injected `POSTGRES_*` values and verified
`postgresql`, host `db`, port `5432`. Documented that Compose must receive the
root `.env` with `--env-file .env` before interpolating the file in `docker/`.
The user confirmed the resulting Backtest function runs without error.

## Plan Self-Review

- **Spec coverage:** Task 1 directly prevents the opaque invalid-port exception; Task 2 makes a future failure traceable; Task 3 supplies both required tabs without inventing Validate Signals UI; Task 4 records evidence and context; Task 5 closes the live Compose interpolation incident.
- **No placeholders:** Each implementation task names exact files, interfaces, test code, commands, and expected outcomes. The deferred Validate Signals feature is explicit product scope, not a missing implementation step.
- **Type consistency:** `_database_url()` remains a no-argument function returning `str`; `JobStatus` and `render_backtest_page()` signatures remain unchanged.
- **User constraint review:** The plan creates no dependency, commit, Docker, SQL, BIGINT, credential, or live-artifact change.
