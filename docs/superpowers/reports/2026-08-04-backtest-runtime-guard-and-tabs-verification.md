# Backtest Runtime Guard and Tabs Verification

**Date:** 2026-08-04

## Scope

- Replace the opaque Backtest worker `ValueError: invalid literal for int() with base 10: ''` failure mode with a safe database-URL port error.
- Preserve the traceback for Docker-log diagnosis without placing configuration values in job status or UI.
- Group the existing Backtest Lab UI under `Collect Signals` and add a static `Validate Signals` tab.

## Diagnosis Record

The first failed status was written at 0% before pipeline progress reaches 5%.
The saved FPT request subsequently passed raw-history loading, data quality,
and indicator construction in a different restarted container. The original
container was stopped before its traceback could be retained.

The later live failure supplied the exact evidence. Its worker traceback ended
at `_database_url()`'s existing `DATABASE_URL` branch. The running Streamlit
parent had `POSTGRES_PORT='5432'`, but its credential-redacted database URL
authority was `db:`. Constructing a URL from the already-injected
`POSTGRES_*` variables parsed successfully as `postgresql`, host `db`, port
`5432` without connecting or writing data.

`docker/docker-compose.yml` constructs `DATABASE_URL` with `${POSTGRES_PORT}`
in its `environment` block, while `env_file: ../.env` injects `POSTGRES_*`
only into the resulting container. Compose performs interpolation first;
therefore `env_file` alone cannot supply that template value. The required
operational command is:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --force-recreate app
```

The user confirmed that the Backtest function ran without error after this
runtime configuration was corrected. The URL guard and trace logging remain
in place for any future configuration regression.

## Test-First Evidence

| Requirement | RED evidence | GREEN evidence |
|---|---|---|
| Empty explicit database URL port is rejected safely | `test_database_url_rejects_an_empty_explicit_port` failed: `RuntimeError not raised` | `tests.test_backtest_pipeline` passed 2/2 |
| Worker error retains traceback diagnostics | `test_failure_records_an_exception_trace_in_worker_logs` failed: no ERROR log | `tests.test_backtest_job_runner` passed 8/8; captured record has `exc_info` |
| Backtest Lab has both tabs | `test_page_groups_current_ui_under_collect_signals_tab` failed: `[] != ['Collect Signals', 'Validate Signals']` | `tests.test_backtest_page` passed 14/14 |

## Final Verification

| Check | Command / method | Result |
|---|---|---|
| Backtest regression gate | Explicit `tests.test_backtest_*` module list in Docker | PASS — 75/75 |
| Syntax | `python -m compileall -q backtest_engine pages/backtest_lab.py` in `stock_app` | PASS |
| Whitespace | trailing-whitespace scan of changed production and test files | PASS — no matches |
| Diff whitespace | `git diff --check` on tracked targets | PASS — exit 0; Backtest files remain user-owned untracked worktree content |
| Live configuration diagnosis | Redacted PID 1 environment plus Compose-file comparison | PASS — isolated malformed `DATABASE_URL ...@db:` despite `POSTGRES_PORT=5432` |
| Live fallback preflight | Construct URL from injected `POSTGRES_*`; printed only driver/host/port | PASS — `driver=postgresql host=db port=5432` |
| Live Backtest function | User confirmation after Compose runtime correction | PASS — completed without error |
| Live artifact safety | No Backtest job submitted | PASS — no `ticker-signals` artifact was overwritten |

The first attempted `unittest discover -s tests` invocation was not used as
evidence: it imports fixtures as top-level `test_backtest_job_runner`, which
the isolated subprocess cannot import. The `-t .` alternative is invalid
because `tests/` is not a classic importable package. The explicit-module gate
above preserves the existing worker test contract and passed.

## Implementation Review

| Category | Findings | Severity |
|---|---|---|
| Logic | URL validation occurs before `get_engine_with_retry`; `JobStatus` payload and automatic polling contracts are unchanged; all current page interaction remains in Collect Signals. | None |
| SQL | No SQL, binding, query, CTE, connection-wrapper, or BIGINT-scaling change. The existing raw-connection path remains untouched. | None |
| Performance | URL parsing is one constant-time preflight per worker. Tabs add no database query, job, artifact read, or validation control to Validate Signals. | None |
| Logging confidentiality | The log message contains only the job identifier; URL values and credentials are not interpolated. | None |
| Comments | The new exception-log comment explains why the traceback is log-only and why UI status stays safe. | None |

**Verdict:** PASS. No implementation-review finding required a revision.

## Boundaries Confirmed

- `app/common_queries.py`, `app/data_preparation.py`, Docker files, credentials, and BIGINT storage/display behavior were not modified. The Compose recovery was an operational app-container recreation, not a Docker-file edit.
- No dependency, commit, merge, push, or signal-artifact overwrite occurred.
