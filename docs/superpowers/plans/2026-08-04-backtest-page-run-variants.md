# Backtest Page Run Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user choose exactly one horizon and submit either its no-theme
backtest alone or both its no-theme and VN-Index-AND variants, while locking
all request controls until every submitted job is terminal and rendered.

**Architecture:** Keep `BacktestConfig`, `submit_backtest`, the background
pipeline, and overwrite-only persistence unchanged. `backtest_lab.py` builds a
tuple of one or two existing configs, submits each as a normal background job,
stores `(config, job_id)` entries in Streamlit session state, and polls/renders
each entry independently. Busy state derives only from persisted job status.

**Tech Stack:** Python 3.12, Streamlit 1.32 AppTest, `unittest`, existing
`BacktestConfig`/spawned job runner, Docker Compose.

## Global Constraints

- Work in the current feature branch; do not create, amend, or otherwise alter
  the commit log.
- Modify only `app/pages/backtest_lab.py`, `tests/test_backtest_page.py`,
  `FOCUS.md`, `ai-context/current-status.md`, and this plan/report evidence.
- Do not modify `common_queries.py`, data-preparation scaling/connection logic,
  credentials, Docker files, dependencies, persistence schema, or engine
  contracts.
- UI price behavior remains unchanged; engine artifacts retain raw BIGINT
  values and no SQL is added or changed.
- Horizon radio values remain engine-compatible `"swing"` / `"midterm"` but
  display as `Swing` / `Mid-term`; its initial value is `None`.
- `INCLUDE_THEME_OPTION` is unchecked by default. It adds exactly one themed
  sibling config with `theme_variant="background-theme"` and
  `theme_mode="AND"`; `OR` is not exposed in the page.
- Disable all request-defining widgets and Run while any stored job is queued,
  running, or temporarily unreadable. Re-enable only after every job has a
  rendered terminal success result or failure message.
- Follow TDD strictly: every production behavior starts with a focused test
  that has been observed failing for the intended missing behavior.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/pages/backtest_lab.py` | Build the one/two config tuple, submit/poll labelled jobs, derive busy state, and render disabled controls/results. |
| `tests/test_backtest_page.py` | Unit and AppTest coverage for exact variants, radio/checkbox defaults, multi-submit, busy lock, and terminal unlock. |
| `FOCUS.md` | Record RED/GREEN evidence and the exact Phase 10 stopping point. |
| `ai-context/current-status.md` | Record completion, test evidence, and any newly observed limitation. |

---

### Task 1: Exact Selected-Horizon Variant Contract

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**
- Consumes: existing `BacktestConfig(ticker, horizon, start_date, end_date, theme_variant, theme_mode)` validation.
- Produces: `build_backtest_configs(...) -> tuple[BacktestConfig, ...]` and
  `submit_run_requests(...) -> tuple[tuple[BacktestConfig, str], ...]`.
- Invariant: every tuple starts with the no-theme config; checkbox-enabled
  tuples append exactly one `background-theme` config using `AND`.

- [x] **Step 1: Write the failing variant-contract tests.**

  Replace the singular config-helper test with these assertions in
  `BacktestPageTests`:

  ```python
  def test_config_builder_returns_only_no_theme_when_checkbox_is_unchecked(self):
      configs = build_backtest_configs(
          ticker="fpt", horizon="swing", time_range="Custom",
          start_date=date(2024, 1, 1), end_date=date(2025, 1, 1),
          include_theme=False,
      )
      self.assertEqual(configs, (
          BacktestConfig(
              ticker="FPT", horizon="swing",
              start_date=date(2024, 1, 1), end_date=date(2025, 1, 1),
              theme_variant="no-background-theme", theme_mode=None,
          ),
      ))

  def test_config_builder_appends_fixed_and_theme_variant_when_checked(self):
      configs = build_backtest_configs(
          ticker="fpt", horizon="midterm", time_range="5y",
          include_theme=True,
      )
      self.assertEqual(len(configs), 2)
      self.assertEqual(
          [(item.theme_variant, item.theme_mode) for item in configs],
          [("no-background-theme", None), ("background-theme", "AND")],
      )
      self.assertTrue(all(item.horizon == "midterm" for item in configs))

  def test_config_builder_rejects_missing_horizon(self):
      with self.assertRaisesRegex(ValueError, "Horizon is required"):
          build_backtest_configs("FPT", None, "5y")
  ```

  Add a multi-submit test that proves the helper calls the existing submit
  function once for every config and returns each `(config, job_id)` entry:

  ```python
  def test_submit_requests_submits_each_config_only_after_click(self):
      configs = (
          BacktestConfig.for_ticker("FPT"),
          BacktestConfig.for_ticker(
              "FPT", theme_variant="background-theme", theme_mode="AND"
          ),
      )
      calls = []

      def submit(config, engine_factory, status_dir):
          calls.append((config, engine_factory, status_dir))
          return f"job-{len(calls)}"

      self.assertEqual(
          submit_run_requests(False, configs, submit, object(), "status"), ()
      )
      self.assertEqual(calls, [])
      self.assertEqual(
          submit_run_requests(True, configs, submit, object(), "status"),
          ((configs[0], "job-1"), (configs[1], "job-2")),
      )
  ```

- [x] **Step 2: Run the focused test to verify RED.**

  Run:

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page.BacktestPageTests.test_config_builder_appends_fixed_and_theme_variant_when_checked tests.test_backtest_page.BacktestPageTests.test_submit_requests_submits_each_config_only_after_click
  ```

  Expected: FAIL because `build_backtest_configs` and
  `submit_run_requests` do not exist. A failure due to an assertion mismatch is
  not an acceptable RED result; correct the test until it identifies the
  missing behavior.

- [x] **Step 3: Implement the smallest config and submission helpers.**

  In `app/pages/backtest_lab.py`, replace `THEME_MODE_OPTIONS` and the singular
  builder with the following behavior. Keep `_preset_dates()` unchanged.

  ```python
  HORIZON_OPTIONS = ("swing", "midterm")
  HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}
  INCLUDE_THEME_OPTION = "VN-Index theme"
  _THEMED_RUN_MODE = "AND"


  def build_backtest_configs(
      ticker: str,
      horizon: str | None,
      time_range: str,
      start_date: date | None = None,
      end_date: date | None = None,
      include_theme: bool = False,
  ) -> tuple[BacktestConfig, ...]:
      """Build the exact one or two page-requested engine configurations."""

      if time_range not in TIME_RANGE_OPTIONS:
          raise ValueError(f"time_range must be one of {TIME_RANGE_OPTIONS}")
      if horizon is None:
          raise ValueError("Horizon is required.")
      if horizon not in HORIZON_OPTIONS:
          raise ValueError(f"horizon must be one of {HORIZON_OPTIONS}")
      preset_start, preset_end = _preset_dates(time_range)
      selected_start = start_date if time_range == "Custom" else preset_start
      selected_end = end_date if time_range == "Custom" else preset_end
      no_theme = BacktestConfig(
          ticker=ticker, horizon=horizon, start_date=selected_start,
          end_date=selected_end, theme_variant="no-background-theme",
          theme_mode=None,
      )
      if not include_theme:
          return (no_theme,)
      return (
          no_theme,
          BacktestConfig(
              ticker=ticker, horizon=horizon, start_date=selected_start,
              end_date=selected_end, theme_variant="background-theme",
              theme_mode=_THEMED_RUN_MODE,
          ),
      )


  def submit_run_requests(
      run_clicked: bool,
      configs: tuple[BacktestConfig, ...],
      submit_fn: Callable,
      engine_factory: Callable,
      status_dir: str,
  ) -> tuple[tuple[BacktestConfig, str], ...]:
      """Submit each requested variant only after an explicit page click."""

      if not run_clicked:
          return ()
      return tuple(
          (config, submit_fn(config, engine_factory, status_dir))
          for config in configs
      )
  ```

  Do not change `BacktestConfig`, the pipeline, job runner, persistence, or
  the engine's `OR` support.

- [x] **Step 4: Run the focused test to verify GREEN.**

  Run the same command from Step 2 plus the legacy submit-only test (renamed
  to use `submit_run_requests`).

  Expected: PASS. Confirm the calls preserve the original config ordering and
  that no submission occurs before a click.

- [x] **Step 5: Do not commit.**

  The user explicitly owns commit history for this feature branch. Leave the
  changed files uncommitted and confirm `git log -1 --oneline` is unchanged.

---

### Task 2: Disabled Controls and Labelled Multi-Job Rendering

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**
- Consumes: `build_backtest_configs`, `submit_run_requests`, existing
  `read_job_status(job_id, status_dir) -> JobStatus`, and each stored
  `(BacktestConfig, job_id)` pair.
- Produces: `_render_controls(disabled: bool) -> tuple[tuple[BacktestConfig, ...] | None, bool]` and page session key `backtest_jobs` containing `tuple[tuple[BacktestConfig, str], ...]`.
- Invariant: status `queued`/`running` or a status-read error means busy;
  `done`/`failed` terminal entries render before controls may be used again.

- [x] **Step 1: Write failing AppTest coverage for the new controls and lock.**

  Update the initial-render assertion to require one Time range selectbox,
  one Horizon radio, no theme-mode selectbox, and an unchecked checkbox:

  ```python
  self.assertEqual([widget.label for widget in app.selectbox], ["Time range"])
  self.assertEqual([widget.label for widget in app.radio], ["Horizon"])
  self.assertIsNone(app.radio[0].value)
  self.assertEqual(
      [widget.label for widget in app.checkbox],
      ["VN-Index theme"],
  )
  self.assertFalse(app.checkbox[0].value)
  ```

  Add an AppTest whose injected running job proves all request controls and the
  Run button are disabled:

  ```python
  def test_running_jobs_disable_request_controls(self):
      script = """
  import streamlit as st
  from backtest_engine.config import BacktestConfig
  from backtest_engine.models import JobStatus
  from pages.backtest_lab import render_backtest_page

  st.session_state["backtest_jobs"] = (
      (BacktestConfig.for_ticker("FPT"), "job-1"),
  )
  def read_status(job_id, status_dir):
      return JobStatus(job_id, "running", progress=0.5)
  render_backtest_page(status_dir="status", read_status_fn=read_status)
  """
      app = AppTest.from_string(script).run()
      self.assertEqual(app.exception, [])
      self.assertTrue(app.text_input[0].disabled)
      self.assertTrue(app.selectbox[0].disabled)
      self.assertTrue(app.radio[0].disabled)
      self.assertTrue(app.checkbox[0].disabled)
      self.assertTrue(app.button[0].disabled)
  ```

  Add a terminal-error AppTest using `JobStatus("job-1", "failed",
  error_text="bad input")`; assert the failure message is rendered and all
  request widgets are enabled. This proves unlock happens only after a
  terminal state is rendered.

- [x] **Step 2: Run the focused AppTest file to verify RED.**

  Run:

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page
  ```

  Expected: FAIL because the page currently renders Horizon as a selectbox,
  retains the mode selector, has a default horizon, and stores only one job id.

- [x] **Step 3: Implement page-only state, controls, and rendering.**

  Make the following precise changes in `app/pages/backtest_lab.py`:

  ```python
  def _config_label(config: BacktestConfig) -> str:
      theme = "VN-Index AND" if config.theme_variant == "background-theme" else "No theme"
      return f"{HORIZON_LABELS[config.horizon]} — {theme}"


  def _read_job_entries(job_entries, read_status_fn, status_dir):
      snapshots = []
      for config, job_id in job_entries:
          try:
              snapshots.append((config, job_id, read_status_fn(job_id, status_dir), None))
          except (FileNotFoundError, ValueError, KeyError) as error:
              snapshots.append((config, job_id, None, error))
      return tuple(snapshots)


  def _jobs_are_busy(snapshots) -> bool:
      return any(
          status is None or status.state in ("queued", "running")
          for _, _, status, _ in snapshots
      )
  ```

  Change `_render_controls` to accept `disabled: bool`. Pass `disabled` to the
  ticker, range, Custom-date, Horizon-radio, theme-checkbox, and Run widgets.
  Use the exact radio/checkbox controls:

  ```python
  horizon = st.radio(
      "Horizon", HORIZON_OPTIONS, index=None,
      format_func=lambda value: HORIZON_LABELS[value], disabled=disabled,
  )
  include_theme = st.checkbox(
      INCLUDE_THEME_OPTION, value=False, disabled=disabled,
  )
  run_clicked = st.button("Run backtest", type="primary", disabled=disabled)
  ```

  In `render_backtest_page`, read `st.session_state.get("backtest_jobs", ())`
  and status snapshots before rendering controls. On a valid explicit click,
  submit all configs with `submit_run_requests`, save the returned tuple under
  `backtest_jobs`, and rerun. Then render each snapshot with its
  `_config_label`, progress/error state, and every successful output artifact.
  Leave `backtest_jobs` in session state after terminal completion so results
  remain visible until a later explicit Run replaces them.

  A status-read error must render its error and be treated as busy, preventing
  a duplicate request while the job's actual state is unknown. Do not clear the
  job entries automatically.

- [x] **Step 4: Run the focused AppTest file to verify GREEN.**

  Run the command from Step 2.

  Expected: PASS. Confirm AppTest sees `None` as initial radio value, the
  unchecked theme checkbox, disabled controls for `running`, and enabled
  controls plus the rendered error for `failed`.

- [x] **Step 5: Do not commit.**

  Run `git log -1 --oneline`; do not run any command that changes commit
  history.

---

### Task 3: Regression Gate, Self-Review, and Documentation Evidence

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-04-backtest-page-run-variants-verification.md`

**Interfaces:**
- Consumes: completed page behavior and Docker test output.
- Produces: Phase 10 recorded RED/GREEN/gate evidence and a resumable project
  stopping point.

- [x] **Step 1: Run the complete focused Backtest and Technical regression gate.**

  Run:

  ```powershell
  docker compose --env-file .env -f docker/docker-compose.yml exec -T -e PYTHONPATH=/app app python -B -m unittest tests.test_backtest_page tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_signal_combos tests.test_backtest_rolling_window tests.test_backtest_trade_execution tests.test_backtest_validation tests.test_backtest_certification tests.test_backtest_persistence tests.test_backtest_early_warning tests.test_backtest_vnindex_theme tests.test_technical_analysis_indicators tests.test_technical_dimension_grouping tests.test_technical_dimension_scoring tests.test_technical_snapshot tests.test_technical_visualization_ui
  ```

  Expected: all named tests pass. Record the exact count; do not reuse the old
  69/69 count without executing this changed suite.

- [x] **Step 2: Run code and boundary checks.**

  Run:

  ```powershell
  python -m compileall -q app/pages/backtest_lab.py
  git diff --check
  git diff --name-only -- app/commons/common_queries.py app/pages/data_preparation.py IMPLEMENTED.md .env docker Dockerfile docker-compose.yml
  git log -1 --oneline
  ```

  Expected: compile succeeds; whitespace check is clean except known CRLF
  warnings; protected-file list is empty; commit head remains unchanged.

- [x] **Step 3: Run implementation self-review and revise every finding.**

  Load `ai-skills/skill-implementation-review.md`. Review:

  ```text
  - Config ordering: no-theme first; checked adds exactly one AND variant.
  - State safety: controls and Run are disabled for queued/running/unreadable jobs.
  - Completion: all terminal outcomes render before a later request can replace state.
  - Concurrency: page submits no synchronous engine work; each job remains in the existing spawned runner.
  - Scope: no SQL, BIGINT, persistence, engine, dependency, Docker, or protected-file changes.
  ```

  Fix every logic, medium/high performance, convention, or comment-quality
  finding, then re-run this task's test and boundary commands.

- [x] **Step 4: Record evidence and close Phase 10.**

  In the verification report, record exact RED failures, GREEN counts, Docker
  command results, boundary results, and any documented limitation. Mark only
  verified Phase 10 tasks complete in `FOCUS.md`; update its current stopping
  point. Update `current-status.md` with completed behavior, exact test count,
  unchanged engine/persistence scope, and the existing full-discovery issue.

- [x] **Step 5: Do not commit.**

  Confirm the head shown by `git log -1 --oneline` is still the pre-existing
  commit and report that no commit was created.

---

## Plan Self-Review

- **Spec coverage:** Task 1 covers no-theme/AND tuple construction, no default
  horizon validation, and submit-only fan-out. Task 2 covers radio/checkbox
  defaults, busy lock, terminal unlock, status errors, labels, and results.
  Task 3 covers Docker regression, self-review, and documentation evidence.
- **Scope:** The plan deliberately reuses the existing job runner and two
  persistence variants; it does not introduce a batch request, a both-horizons
  selector, or an engine/persistence/SQL change.
- **TDD:** Each production task starts with focused tests and an expected RED
  command before the corresponding implementation, then specifies its GREEN
  command.
- **Type consistency:** `build_backtest_configs` returns the tuple consumed by
  `submit_run_requests`; submitted session entries remain `(BacktestConfig,
  str)` and are consumed by the status/render helpers.
- **Completeness:** Every implementation step has an exact behavior, test, and
  command; the engine batch design is explicitly out of scope rather than an
  unfinished part of this plan.
