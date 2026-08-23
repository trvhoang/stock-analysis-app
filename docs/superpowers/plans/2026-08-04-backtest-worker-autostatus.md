# Backtest Worker Isolation and Automatic Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Streamlit-process callable pickling from Backtest execution and automatically keep the Backtest UI current while jobs are non-terminal.

**Architecture:** `job_runner.submit_backtest()` persists a JSON request and launches `python -m backtest_engine.worker <request-path>`. The dedicated worker resolves a validated importable factory reference, reconstructs `BacktestConfig`, and writes the existing atomic lifecycle statuses. The Backtest page removes manual refresh controls and schedules a one-second `st.experimental_rerun()` only while stored jobs are busy.

**Tech Stack:** Python 3.12 stdlib (`subprocess`, `threading`, `importlib`, `json`), Streamlit 1.32, `unittest`, Docker Compose.

## Global Constraints

- Work on the current feature branch; do not create, amend, or alter commits.
- Do not add dependencies, modify Docker files, SQL, data-preparation code, `common_queries.py`, credentials, persistence schemas, or BIGINT output behavior.
- Job request and status files are atomically written; a failed worker startup must not leave an indefinitely queued status.
- Backtest work must never execute in a Streamlit request or import `app/main.py` in its worker interpreter.
- UI status polling is automatic while queued/running/unreadable and stops at terminal state; no `Refresh status` widget remains.
- Follow Do / Check / Act: record a focused RED failure before every production change, then run focused Docker GREEN tests before the next task.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/backtest_engine/job_runner.py` | Persist serializable requests, validate factory references, launch/reap isolated workers, and retain atomic status helpers. |
| `app/backtest_engine/worker.py` | Reconstruct and execute one trusted request without importing Streamlit or the application bootstrap. |
| `app/pages/backtest_lab.py` | Schedule automatic busy-only status reruns and remove manual refresh controls. |
| `tests/test_backtest_job_runner.py` | Prove request/worker lifecycle, failure persistence, and no callable pickling contract. |
| `tests/test_backtest_page.py` | Prove no manual refresh widget and busy-only automatic repoll scheduling. |
| `FOCUS.md` / `ai-context/current-status.md` | Record RED/GREEN evidence, completion, and the precise stopping point. |

### Task 1: Isolated, Serializable Backtest Worker

**Files:**
- Create: `app/backtest_engine/worker.py`
- Modify: `app/backtest_engine/job_runner.py`
- Modify: `tests/test_backtest_job_runner.py`

**Interfaces:**
- `_factory_reference(factory: Callable) -> str` returns `<module>:<qualname>` only when importing and resolving the reference returns the same callable.
- `submit_backtest(config, engine_factory, status_dir) -> str` writes `{job_id}.request.json`, returns promptly, and launches `sys.executable -m backtest_engine.worker <request-path>`.
- `run_worker_request(request_path: str) -> JobStatus` reconstructs a validated `BacktestConfig`, resolves the trusted factory reference, and always writes a terminal failure for request/factory errors.

- [x] **Step 1: Write failing lifecycle and worker-entry tests.**

  Add `import json`, `import sys`, and `from backtest_engine.worker import
  run_worker_request`, then add these tests to `tests/test_backtest_job_runner.py`:

  ```python
  def test_submit_writes_serializable_request_and_launches_module_worker(self):
      config = BacktestConfig.for_ticker("FPT")
      with self._temporary_status_dir() as directory, patch(
          "backtest_engine.job_runner.subprocess.Popen"
      ) as popen, patch("backtest_engine.job_runner.threading.Thread") as thread:
          process = popen.return_value
          process.wait.return_value = 0
          job_id = submit_backtest(config, _slow_engine, directory)

          request = json.loads(
              (Path(directory) / f"{job_id}.request.json").read_text("utf-8")
          )
      self.assertEqual(request["config"], config.to_dict())
      self.assertEqual(
          request["factory_ref"], "tests.test_backtest_job_runner:_slow_engine"
      )
      popen.assert_called_once_with(
          [sys.executable, "-m", "backtest_engine.worker", str(Path(directory) / f"{job_id}.request.json")],
          close_fds=True,
      )
      thread.return_value.start.assert_called_once_with()

  def test_worker_persists_factory_resolution_failure(self):
      with self._temporary_status_dir() as directory:
          request_path = Path(directory) / "bad.request.json"
          request_path.write_text(json.dumps({
              "job_id": "bad", "status_dir": directory,
              "config": BacktestConfig.for_ticker("FPT").to_dict(),
              "factory_ref": "not_a_module:missing",
          }), encoding="utf-8")
          final = run_worker_request(str(request_path))
      self.assertEqual(final.state, "failed")
      self.assertIn("ModuleNotFoundError", final.error_text)

  def test_submit_rejects_non_importable_factory_before_worker_launch(self):
      with self.assertRaisesRegex(ValueError, "importable"):
          submit_backtest(BacktestConfig.for_ticker("FPT"), lambda *_: [], "status")
  ```

- [x] **Step 2: Run the selected tests and record RED.**

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_job_runner.BacktestJobRunnerTests.test_submit_writes_serializable_request_and_launches_module_worker tests.test_backtest_job_runner.BacktestJobRunnerTests.test_worker_persists_factory_resolution_failure tests.test_backtest_job_runner.BacktestJobRunnerTests.test_submit_rejects_non_importable_factory_before_worker_launch
  ```

  Expected: FAIL because the module worker, request payload, and importable-factory contract do not exist.

- [x] **Step 3: Implement the smallest isolated-worker contract.**

  In `job_runner.py`, replace `ProcessPoolExecutor` ownership with these responsibilities:

  ```python
  def _factory_reference(factory: Callable) -> str:
      module_name = getattr(factory, "__module__", "")
      qualname = getattr(factory, "__qualname__", "")
      if not module_name or not qualname or "<locals>" in qualname:
          raise ValueError("engine_factory must be importable")
      module = importlib.import_module(module_name)
      resolved = module
      for attribute in qualname.split("."):
          resolved = getattr(resolved, attribute)
      if resolved is not factory:
          raise ValueError("engine_factory must be importable")
      return f"{module_name}:{qualname}"

  def submit_backtest(config, engine_factory: Callable, status_dir: str) -> str:
      factory_ref = _factory_reference(engine_factory)
      job_id = uuid.uuid4().hex
      _write_status(JobStatus(job_id, "queued"), status_dir)
      try:
          request_path = _write_request(job_id, config, factory_ref, status_dir)
          process = subprocess.Popen(
              [sys.executable, "-m", "backtest_engine.worker", str(request_path)],
              close_fds=True,
          )
      except Exception as error:
          _write_status(JobStatus(job_id, "failed", error_text=f"{type(error).__name__}: {error}"), status_dir)
          return job_id
      _ACTIVE_PROCESSES[job_id] = process
      threading.Thread(target=_reap_worker, args=(job_id, status_dir, process), daemon=True).start()
      return job_id
  ```

  `_write_request()` must use the same temporary-file plus `os.replace()`
  durability pattern as `_write_status()`. The `try` block must cover both
  request persistence and `Popen`, converting either failure from the already
  queued state to terminal `failed`. `_reap_worker()` must call
  `process.wait()`, remove the active process entry, and write a terminal
  failure only when the process exits non-zero and status remains unreadable or
  non-terminal. Keep `run_backtest_job()` as the synchronous test/worker
  primitive.

  In new `worker.py`, parse one request path from `sys.argv`, rebuild dates
  with `date.fromisoformat`, resolve `<module>:<qualname>` via
  `importlib.import_module`, and call the existing synchronous runner. Wrap
  request parsing and factory resolution so every error writes a `failed`
  `JobStatus`; place `main()` behind `if __name__ == "__main__"`.

- [x] **Step 4: Run the selected tests for GREEN, then real worker integration.**

  Run Step 2's command, then:

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_job_runner
  ```

  Expected: PASS. The existing immediate-return lifecycle test must reach
  `done` through the new `-m backtest_engine.worker` entrypoint. Confirm the
  serialized request contains only JSON data and the factory reference string.

- [x] **Step 5: Self-review Task 1.**

  Confirm `job_runner.py` and `worker.py` contain no Streamlit or `main`
  import, no `ProcessPoolExecutor`, no callable serialization, and no status
  path writes outside the provided status directory.

### Task 2: Automatic Status Synchronisation Without a User Control

**Files:**
- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**
- `schedule_status_refresh(is_busy: bool, sleep_fn: Callable = time.sleep, rerun_fn: Callable = st.experimental_rerun) -> None` waits exactly one second and reruns only when `is_busy` is true.
- `render_backtest_page(..., schedule_refresh_fn: Callable = schedule_status_refresh)` renders status first, then delegates scheduling for testability.

- [x] **Step 1: Write failing automatic-polling tests.**

  Add these tests to `tests/test_backtest_page.py`:

  ```python
  def test_busy_status_schedules_one_second_automatic_refresh(self):
      calls = []
      schedule_status_refresh(True, lambda seconds: calls.append(seconds), lambda: calls.append("rerun"))
      self.assertEqual(calls, [1, "rerun"])

  def test_terminal_status_does_not_schedule_refresh(self):
      calls = []
      schedule_status_refresh(False, lambda seconds: calls.append(seconds), lambda: calls.append("rerun"))
      self.assertEqual(calls, [])

  def test_running_page_has_no_manual_refresh_button(self):
      script = """
  import streamlit as st
  from backtest_engine.config import BacktestConfig
  from backtest_engine.models import JobStatus
  from pages.backtest_lab import render_backtest_page
  st.session_state["backtest_jobs"] = ((BacktestConfig.for_ticker("FPT"), "job-1"),)
  render_backtest_page(
      status_dir="status",
      read_status_fn=lambda *_: JobStatus("job-1", "running", progress=0.5),
      schedule_refresh_fn=lambda busy: None,
  )
  """
      app = AppTest.from_string(script).run()
      self.assertEqual([item.label for item in app.button], ["Run backtest"])
      self.assertTrue(app.button[0].disabled)
  ```

- [x] **Step 2: Run the selected tests and record RED.**

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page.BacktestPageTests.test_busy_status_schedules_one_second_automatic_refresh tests.test_backtest_page.BacktestPageTests.test_terminal_status_does_not_schedule_refresh tests.test_backtest_page.BacktestPageTests.test_running_page_has_no_manual_refresh_button
  ```

  Expected: FAIL because automatic scheduling is absent and a manual refresh
  button still renders for a running job.

- [x] **Step 3: Implement the page-only automatic poll.**

  Add `import time`, `STATUS_REFRESH_SECONDS = 1`, and this helper:

  ```python
  def schedule_status_refresh(
      is_busy: bool,
      sleep_fn: Callable = time.sleep,
      rerun_fn: Callable = st.experimental_rerun,
  ) -> None:
      if is_busy:
          sleep_fn(STATUS_REFRESH_SECONDS)
          rerun_fn()
  ```

  Extend `render_backtest_page()` with injected `schedule_refresh_fn` for
  deterministic tests. Compute `is_busy` once from the status snapshots,
  render all labels/progress/results/errors, show a short automatic-update
  caption when busy, then call `schedule_refresh_fn(is_busy)`. Delete the
  `Refresh status` button branch entirely. Existing busy-control disabling and
  terminal rendering remain unchanged.

- [x] **Step 4: Run the selected tests for GREEN and the focused page gate.**

  Run Step 2's command, then:

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page tests.test_backtest_pipeline tests.test_backtest_job_runner
  ```

  Expected: PASS. Confirm running jobs show progress with disabled controls,
  expose no manual refresh button, schedule exactly one one-second rerun, and
  terminal jobs unlock controls without scheduling another rerun.

- [x] **Step 5: Self-review Task 2.**

  Verify the polling code never submits a job, reads only existing JSON
  sidecars, and stops at done/failed statuses. Confirm no UI or Plotly price
  behavior changed.

### Task 3: Docker Validation and Documentation Handoff

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-04-backtest-worker-autostatus-verification.md`

- [x] **Step 1: Run source and focused Docker validation.**

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_signal_combos tests.test_backtest_rolling_window tests.test_backtest_trade_execution tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence tests.test_backtest_early_warning tests.test_backtest_vnindex_theme
  ```

  Also run `git diff --check` and confirm protected files have no new diff.

- [x] **Step 2: Live smoke on the running app.**

  Submit one short no-theme request. Confirm it begins queued/running without
  `PicklingError`, the UI updates without a Refresh button, controls remain
  disabled until terminal, and the status reaches a terminal state. Record
  only observed result and duration; do not alter persisted data manually.

- [x] **Step 3: Run implementation review and revise every finding.**

  Review worker request validation, atomic files, child process cleanup,
  Streamlit thread safety, terminal unlock, source-import boundaries, and
  protected BIGINT/SQL/Docker areas. Apply only necessary corrections, then
  repeat Step 1.

- [x] **Step 4: Document evidence.**

  Create the verification report with exact commands/results, worker/UI smoke
  evidence, source-boundary check, and any environment-only limitation. Mark
  this plan and `FOCUS.md` complete only after every required validation
  passes; update `ai-context/current-status.md` with the repaired lifecycle.
