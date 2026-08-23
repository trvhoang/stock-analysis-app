# Current Positions Inline Management Verification

Date: 2026-08-12

## Delivered

- Replaced separate Current Positions add/edit/refresh flows with a two-row
  toolbar: uppercase three-character ticker filter, OPEN/CLOSED filter, native
  `New position` popover, refresh icon, sort key, and sort direction.
- Added the native three-row New Position popover. It keeps saved-signal
  selection optional, keeps prices at the shared `k` UI boundary, and requires
  volume inputs to use a minimum and step of 100.
- Replaced per-row edit forms with one `st.data_editor` selection table. Only
  State, BUY/SELL price, BUY/SELL date, and volume are editable; ticker,
  saved-signal association, derived P&L, and audit timestamps remain read-only.
- Added atomic inline lifecycle updates and exact permanent deletion to both
  manual and legacy position histories. Reopening clears closure data and
  retains the cross-history one-OPEN saved-set protection.
- Added a two-step permanent-delete flow: immutable position summary first,
  explicit confirmation and spinner second. The summary includes ticker,
  state, BUY/SELL price and date, quantity, and saved signal set. Changing the
  selected/visible row or refreshing cancels a stale confirmation.

## Verification Evidence

- RED/GREEN focused page/store/overview gate: `58/58` pass.
- Final package-qualified Backtest suite:
  `185` pass, `1` expected skip. The emitted worker traceback is the deliberate
  synthetic-failure fixture in `test_backtest_job_runner.py`.
- Docker compilation of `backtest_engine` and `pages/backtest_lab.py`: pass.
- `git diff --check`: exit `0`; only existing line-ending conversion warnings
  were printed.
- Protected file hashes exactly match the pre-task baseline for
  `common_queries.py`, `data_preparation.py`, `main.py`, Docker files, and
  `requirements.txt`.
- Runtime smoke: `stock_app` is configured for Streamlit port `3501`; its
  `/_stcore/health` endpoint returned `200 ok`. An initial port-`8501` refusal
  was diagnosed as probing the wrong port, not an application failure.

## Requirements Coverage

| Requirement | Evidence |
| --- | --- |
| Filter, default oldest-first order, all sort keys/directions, refresh | Page helpers/AppTest regression coverage |
| Reactive optional saved set, paired SELL validation, volume 100 | New Position AppTests |
| One selected row, immutable identity, raw/UI price conversion | Editor helper and locator routing regressions |
| Close/reopen lifecycle, frozen-risk update, one-OPEN protection | Manual and legacy store regressions |
| Permanent exact delete after confirmation only | Delete/store routing, summary, and stale-confirmation regressions |

## Implementation Review

| Category | Finding | Severity |
| --- | --- | --- |
| Logic | Raw BIGINT values remain at rest; UI uses the shared `k` converters. One-row change-set, exact locator, lifecycle, and stale-delete guards are covered. | Pass |
| SQL | No query, database schema, SQL text, or connection path was added or changed. | Pass |
| Performance | Filtering, sorting, and editor work are in-memory after one cached overview load. Refresh is explicit; no per-row query exists. | Pass |

## Known Test Limitation

Streamlit 1.32 AppTest exposes `st.data_editor` as a dataframe and has no
programmatic grid-edit or popover-open API. Rendered-column/controls contracts
are covered by AppTest; the exact update/delete persistence path is covered by
direct helper and real atomic-store regressions. Browser-driven visual clicking
was not available in this headless agent environment.

No database, signal artifact, protected boundary, dependency, Docker-file, or
commit change was made for this feature.
