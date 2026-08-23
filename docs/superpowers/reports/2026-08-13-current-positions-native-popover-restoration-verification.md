# Current Positions Native New Position Popover Restoration Verification

Date: 2026-08-13

## Delivered

- Restored the compact `st.popover("New position")` container.
- Removed panel-only visibility session state, placeholder, and Close button.
- Preserved ticker capitalization, optional saved-signal selection, BUY/SELL
  pairing validation, raw-price conversion, frozen risk snapshot, and manual
  position persistence.
- Added `TODO(streamlit-upgrade)` beside the popover. Streamlit 1.32 exposes
  no supported programmatic popover-close API, so unsaved forms dismiss through
  click-outside or Escape.

## Test-First Evidence

- RED: native-popover regression coverage failed because the page still exposed
  `_render_new_position_panel`; the native-popover structure count was `0`.
- GREEN: focused Current Positions tests passed `2/2` after restoration.
- Full page suite: `37/37` passed.
- Full package-qualified Backtest gate: `190` passed, `1` expected skip. The
  emitted worker traceback is the deliberate synthetic-failure fixture in
  `test_backtest_job_runner.py`.
- Docker compilation of `backtest_engine` and `pages/backtest_lab.py` passed.
- Streamlit health endpoint `http://127.0.0.1:3501/_stcore/health` returned
  `200 ok`.

## Implementation Review

| Category | Findings | Verdict |
| --- | --- | --- |
| Logic | Existing creation validation and persistence calls are unchanged; native popover dismissal does not mutate position data. | Pass |
| SQL / data integrity | No SQL, database, schema, raw-BIGINT, or price-display conversion path changed. | Pass |
| Performance | Removed panel session-state and placeholder work; native popover adds no query, cache, or looped-fetch path. | Pass |

## Known Limitation

Streamlit 1.32 AppTest exposes popover contents through `app.get("popover")`,
but cannot simulate browser open/dismiss interaction. Native click-outside and
Escape behavior therefore remain a manual runtime concern; the source TODO
requires reconsideration after a Streamlit upgrade adds supported control.

No commit was created.
