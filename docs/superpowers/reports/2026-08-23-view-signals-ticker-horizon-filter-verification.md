# View Signals Ticker and Horizon Filters Verification

## Scope

The shared View Signals table now has an optional uppercase partial ticker
filter and a `Both`/`Swing`/`Mid-term` Horizon select box. Both filters are
local and intersect; Horizon defaults to `Both`.

## Test-first evidence

- RED: `test_view_signal_rows_filter_by_partial_ticker_and_horizon` failed
  because `_filter_view_signal_rows` did not exist.
- RED: `test_view_signals_renders_ticker_and_both_default_horizon_filters`
  failed because no Ticker input existed.
- GREEN: both focused tests passed after the minimal projection and widgets.

## Final verification

- `docker exec stock_app python -m unittest tests.test_backtest_page -v` —
  passed, 33 tests.
- `docker exec stock_app python -m py_compile pages/backtest_lab.py` — passed.

The Docker test output includes pre-existing Streamlit `SyntaxWarning` messages
from installed package source; the project tests themselves passed.

## Review

| Area | Result |
| --- | --- |
| Filter semantics | Partial ticker matching and Horizon selection use AND semantics. |
| Streamlit state | Explicit View Signals keys prevent widget collisions. |
| SQL, artifacts, jobs, positions | Untouched. |
| Performance | One in-memory pass over already-projected catalog rows. |

No Git action, commit, commit-tree change, dependency, Docker, credential,
database, SQL, price-scaling, catalog, artifact, job, validation, or position
change was made.
