# Current Positions Bulk Delete Verification

Date: 2026-08-12

## Delivered

- Reordered Current Positions controls into the requested three lines:
  filter/state/sort/direction; New position plus refresh; then Delete position.
- Added page-owned individual and all-visible selection. Selection is pruned
  to the currently filtered table and clearing/reloading/add/save/delete clears
  it.
- Added a disabled-by-default Delete position trigger and retained exactly-one
  selection for Save changes.
- Added batch prevalidation of every immutable locator before the first
  deletion, stable table-order execution, one multi-record confirmation, and
  stop-on-first-error behavior. Manual and legacy stores remain the only
  source-specific atomic writers.
- Bound a confirmation to its selected IDs, visible ordering, and normalized
  filter/sort state. Refresh, filtering, sorting, or selection changes cancel
  it before a write.
- Added an exact two-second full-success message. Partial batches reload with
  a durable error and never display a success message.

## Verification Evidence

- Task 1 RED: the requested visible-selection helper was missing; GREEN passed
  after the smallest implementation. Full page regression: `33` passed.
- Task 2 RED: batch preparation/execution helpers were missing; GREEN passed.
  The batch, exact locator, and stale-confirmation gate passed `3/3`; full page
  regression: `34` passed.
- Task 3 RED: timed full-success feedback was missing; GREEN passed. The page,
  manual-store, legacy-store, and overview regression gate passed `63/63`.
- Self-review safety regression: a pending confirmation did not bind a filter
  change that left the same rows visible. A new RED test failed on the missing
  filter-state contract; the repaired guard passed.
- Final package-qualified Backtest gate: `188` passed, `1` expected skip. The
  emitted worker traceback is the deliberate synthetic-failure fixture in
  `test_backtest_job_runner.py`.
- Docker compilation of `backtest_engine` and `pages/backtest_lab.py`: passed.
- `git diff --check`: exit `0`; only existing line-ending warnings were
  emitted.
- Streamlit health: `http://127.0.0.1:3501/_stcore/health` returned `200 ok`.

## Boundary Inspection

The feature changed only `app/pages/backtest_lab.py`,
`tests/test_backtest_page.py`, and task documentation. It added no SQL,
database schema, dependency, Docker, credential, BIGINT-scaling, artifact, or
commit change. Current SHA-256 values recorded for protected boundaries:

| File | SHA-256 |
| --- | --- |
| `app/commons/common_queries.py` | `4A8C77004B89A92FE575EF44C46BD19DFDC0C04F04F1E027F1B810CE8D6880E3` |
| `app/pages/data_preparation.py` | `1345407BE2AE0D9D80C88FF3C3A445BF59BA1562879A03A99532F14C2F5C10E7` |
| `app/main.py` | `5AFB3E317A67FA88B99CFEE304EB1F5BA7B63417333C454B0D0BFB15FD5B5013` |
| `docker/Dockerfile` | `456CC62E2ABC28F8C16A044C72C7FC4483C39DAE0A21A4FFB542E9B50F6C0744` |
| `docker/docker-compose.yml` | `795F692B60814EE5474DA3A4D0E9C1FEA310E5E110685BA65060E10D1403C35D` |
| `requirements.txt` | `F8882E9765CE5275E8B2243D226A25CCB2545E829B23154A75A14E5F84D4BC90` |

## Implementation Review

| Category | Findings | Severity |
| --- | --- | --- |
| Logic | Raw BIGINT values remain at rest and the existing `k` converters remain the sole UI boundary. Every selected locator is validated before a writer runs; confirmation is stale on filter/sort/selection/refresh changes; partial deletes stop safely. | Pass |
| SQL | No query, SQL text, connection, or schema change. | Pass |
| Performance | One cached overview supplies filtering/sorting. Selection uses vectorized pandas filtering; no per-row database query or new N+1 path exists. | Pass |

## Known Limitation

Streamlit 1.32 AppTest exposes `st.data_editor` as a dataframe and cannot
click its grid checkboxes or open popovers programmatically. The selection,
batch, and store mutation paths are therefore covered by pure helper and real
atomic-store tests; rendered controls are covered by AppTest.

No commit was created.
