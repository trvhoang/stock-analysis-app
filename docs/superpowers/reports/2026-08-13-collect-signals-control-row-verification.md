# Collect Signals Control-Row Verification

Date: 2026-08-13

## Delivered

- Collect Signals line 1 now renders Ticker, Time range, Horizon, and
  `VN-Index theme` in four Streamlit columns.
- Time range choices remain `5y`, `15y`, `Custom`, with `15y` selected by
  default.
- Horizon is now a dropdown with `-`, Swing, and Mid-term. `-` maps to `None`,
  so existing required-horizon validation remains authoritative.
- Custom Start/End dates and Run backtest remain below the control row.
- Validate Signals continues using its existing `Include VN-Index background
  theme` label.

## Test-First Evidence

- RED: focused tests failed because Horizon was a radio, Time range defaulted
  to `5y`, and the old theme label/layout remained.
- GREEN: focused layout/default/job-lock tests passed `3/3`.
- Full Backtest page suite: `37/37` passed.
- Full package-qualified Backtest gate: `190` passed, `1` expected skip. The
  emitted worker traceback is the deliberate synthetic-failure fixture in
  `test_backtest_job_runner.py`.
- Docker compilation of `backtest_engine` and `pages/backtest_lab.py` passed.
- Streamlit health endpoint `http://127.0.0.1:3501/_stcore/health` returned
  `200 ok`.

## Implementation Review

| Category | Findings | Verdict |
| --- | --- | --- |
| Logic | The dropdown maps only its display sentinel to existing `None` validation. Config generation, Custom dates, and job-lock behavior remain unchanged. | Pass |
| SQL / data integrity | No query, persistence, schema, raw-BIGINT, or price-display conversion path changed. | Pass |
| Performance | Four UI columns add no query, cache, loop, or background-job path. | Pass |

No commit was created.
