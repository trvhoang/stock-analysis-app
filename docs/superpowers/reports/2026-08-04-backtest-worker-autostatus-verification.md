# Backtest Worker Isolation and Automatic Status Verification

## Scope

Repaired the Streamlit-time `PicklingError`, removed user-driven status
refreshing, and preserved the existing Backtest engine, data, SQL, BIGINT, and
artifact contracts.

## RED Evidence

- Worker-contract RED: three focused tests failed because no module worker or
  serialized request existed, and non-importable factories were accepted.
- Automatic-status RED: three focused page tests failed because no scheduler
  existed and the page rejected the injected scheduler contract.
- Independent review RED: an `OSError` during status reads crashed the page;
  the new regression test reproduced that failure.

## Shipped Behavior

- `submit_backtest()` validates a module-level engine factory, atomically
  writes a JSON request, and launches `python -m backtest_engine.worker`.
- The worker reconstructs `BacktestConfig`, resolves the factory inside its
  own interpreter, and persists terminal errors as JSON status sidecars.
- A daemon reaper removes the child process handle and converts unexpected
  non-terminal child exits to failed status.
- The Backtest page has no `Refresh status` button. Queued, running, and
  unreadable statuses keep request controls disabled, render the current
  state, and rerun automatically after one second. Done/failed states stop
  scheduling and unlock controls.

## Verification Evidence

| Check | Result |
|---|---|
| Job-runner suite | 7/7 passed; includes real `-m backtest_engine.worker` completion and worker-side factory-resolution failure. |
| Page/pipeline/runner gate | 21/21 passed after the unreadable-status review fix. |
| Broad Backtest gate | 52/52 passed. |
| Full focused Backtest/Technical gate | 132/132 passed in 1.437 seconds. |
| Live isolated-worker smoke | FPT, 2024-01-01 to 2025-01-01, completed at 100% in 18.2 seconds with one artifact under `/tmp`; no `PicklingError`. |
| Streamlit health | `/_stcore/health` returned `ok`; app logs showed no worker-triggered FastAPI startup. |

The live pipeline emitted the existing pandas DBAPI compatibility warning from
`backtest_engine/data_quality.py`; it did not affect completion and is outside
this worker/UI repair.

## Review

Independent review identified that `OSError` and `TypeError` from status reads
were not treated as temporarily unreadable jobs. `_read_job_entries()` now
catches them, and the focused regression plus the final 132-test gate pass.

## Boundary Check

No SQL, `common_queries.py`, data-preparation scaling/connection behavior,
Docker files, dependencies, credentials, persisted signal schema, or commit
history changed.
