# Backtest Worker Isolation and Automatic Status Design

## Goal

Make Backtest execution safe under Streamlit development reloads and update
queued/running job status without any manual user action.

## Problem

`ProcessPoolExecutor` serializes its submitted callable asynchronously. A
Streamlit source-module invalidation can replace
`backtest_engine.job_runner._worker_entry` before serialization completes,
leaving the queued function detached from the module identity required by
`pickle`. Spawned processes also risk executing the Streamlit application's
top-level bootstrap.

## Chosen Design

### Isolated worker process

`submit_backtest()` will launch a dedicated `python -m
backtest_engine.worker` subprocess rather than pass an in-memory callable to a
Streamlit-owned process pool. The parent writes an atomic request payload that
contains only the job id, validated configuration, status directory, and an
importable engine-factory reference. The worker resolves that reference in its
own interpreter, then uses the existing atomic status lifecycle.

The worker module has no Streamlit or application-bootstrap import. It must
persist a terminal failed status for invalid requests, factory-resolution
errors, and unexpected worker errors, so the UI never remains indefinitely
locked.

### Automatic status synchronisation

While any submitted job is queued, running, or unreadable, the page renders
the current status, waits one second, and calls Streamlit 1.32's built-in
`st.experimental_rerun()`. This is automatic polling, not a second background
job: the backtest itself remains isolated in its subprocess. Once all jobs are
terminal, the scheduled rerun stops and the request controls unlock.

All manual `Refresh status` controls are removed. No dependency upgrade or
custom browser component is introduced.

## Invariants

- Job inputs, worker request, and persisted status use atomic files.
- No callable crosses a process boundary.
- Backtest worker startup cannot execute `app/main.py` or start FastAPI.
- UI controls stay disabled until every requested variant has a known terminal
  status; failed sibling jobs do not hide successful artifacts.
- The existing JSON status/result contracts, engine behavior, SQL, BIGINT
  scaling, Docker configuration, and commit history remain unchanged.

## Validation

Tests will prove subprocess command construction, importable-factory
validation, terminal status persistence for worker-side failure, no
`Refresh status` widget, automatic repoll only while busy, progress display,
and terminal unlock. A Docker integration check will exercise the worker
entrypoint without importing Streamlit's application bootstrap.
