# Backtest Multi-Group Membership Verification

Date: 2026-08-14  
Status: Complete and verified. No commit created.

## Delivered contract

- One ticker may belong to zero or more named Group JSON files.
- One named Group still owns zero or more deterministic ticker symbols.
- Existing V2 signal artifacts retain their independent one-ticker-to-many-
  signal-set relationship.
- A named Collect Group is add-only after a qualifying final Backtest result;
  it preserves all earlier named memberships.
- Blank/`N/A` is a no-op writer input. `N/A` readers derive ungrouped tickers
  as artifact tickers absent from every named Group.
- View Signals keeps exactly one candidate row per ticker/theme/signal set. Its
  `Ticker Groups` filter matches private membership tuples; Group is not a
  result-table column.
- Validate named-Group and derived-`N/A` resolution remain deterministic and
  disjoint. The existing 15-ticker cap is unchanged.

## RED / GREEN evidence

### Task 1 — Group store

RED command:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_persistence.BacktestPersistenceTests.test_group_membership_is_add_only_and_na_is_derived tests.test_backtest_persistence.BacktestPersistenceTests.test_group_reader_rejects_duplicate_group_name_or_same_file_ticker tests.test_backtest_persistence.BacktestPersistenceTests.test_group_resolver_lists_real_and_no_group_artifact_tickers
```

Observed expected RED: the plural `groups_for_ticker` interface was absent and
the old reader rejected `FPT` in two distinct valid Group files.

GREEN evidence:

```text
Focused: Ran 3 tests in 0.071s — OK
Persistence module: Ran 14 tests in 2.286s — OK
```

The store now permits cross-file membership, still rejects duplicate entries in
one Group JSON, and retains Group identity/payload validation plus crash-journal
recovery.

### Task 2 — catalog and View Signals filtering

RED command:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_page.BacktestPageTests.test_catalog_group_names_preserves_all_memberships tests.test_backtest_page.BacktestPageTests.test_view_signals_popovers_filter_by_group_in_collect_and_validate
```

Observed expected RED: the catalog retained only the last scalar Group, the
plural page helper was absent, and an AppTest could not select `BANK` from a
multi-Group row.

GREEN evidence:

```text
Catalog/page modules: Ran 53 tests in 5.167s — OK
```

AppTests prove `BANK` and `ETF VN30` each show the same single ticker row,
while `N/A` shows only the ungrouped ticker.

### Task 3 — qualification-only pipeline behavior

Two real-store regressions were added for the unchanged batch pipeline seam:
a qualified final result adds `ETF VN30` without evicting `BANK`; a terminal
empty result preserves `BANK` and creates no new Group. The tests were a direct
GREEN proof after Task 1 because `pipeline.py` already called the shared store
only after final qualification; no pipeline production edit was warranted.

```text
Pipeline module: Ran 17 tests in 0.186s — OK
Focused Backtest gate: Ran 97 tests in 6.066s — OK
```

The focused gate's logged `synthetic engine failure` is the expected failure
fixture in `tests.test_backtest_job_runner`; the test command exited zero.

## Final checks

```text
docker exec stock_app python -m compileall backtest_engine pages
Exit 0; compiled result_store.py, signal_catalog.py, and backtest_lab.py.

rg -n -F "group_for_ticker" app tests
No singular group_for_ticker references.

rg -n -P '\"_group\"' app tests
No scalar _group membership references.

SIGNAL_CATALOG_COLUMNS
('Ticker', 'Theme', 'Metric', 'Horizon', 'Certified at', 'n',
 'Win rate %', 'Profit %', 'Sharpe')

http://127.0.0.1:3501/_stcore/health
200
```

The installed Streamlit version emits two pre-existing dependency
`SyntaxWarning`s about invalid escape sequences during page imports; neither is
from this feature and all test commands exit successfully.

## Full-discovery boundary

The required branch-handoff command was also run:

```text
docker exec stock_app python -m unittest discover -s tests
Ran 377 tests in 13.242s — FAILED (failures=2, errors=4, skipped=1)
```

This is not a Multi-Group regression. The failures occur before the feature's
store/catalog/page paths:

- `backtest_engine.diagnostics` imports removed `_default_dates` from
  `pipeline.py`; the current function is `_requested_dates`. Its retained call
  to `_theme_signal(frame, vnindex, horizon)` also disagrees with the current
  two-argument helper.
- Discovery imports `test_backtest_job_runner` as a top-level module, while the
  worker tests expect the package-qualified `tests.test_backtest_job_runner`.
  The subprocess then cannot import the top-level discovery module; the later
  `UnboundLocalError` is a consequence of that terminal worker failure.
- `test_trend_classification_probe` imports `scripts`, which the application
  container does not mount.

The explicit package-qualified focused Backtest gate avoids these unrelated
test-topology/stale-import failures and passes 97/97. Repairing them needs a
separate approved test-topology/diagnostics task; no speculative fix was made.

## Implementation review

| Category | Finding | Severity |
|---|---|---|
| Logic | Pass — Group JSON is the sole membership source; `N/A` is derived and cannot erase named memberships. | — |
| SQL / BIGINT | Pass — no database, query, price, or scaling path changed. | — |
| Performance | Pass — membership is read once per catalog build and filtered in memory; no query, row expansion, or N+1 loop was added. | — |
| UI | Pass — private tuple filtering preserves one candidate row and the visible columns omit Group. | — |

Known inherited behavior: if Group metadata is corrupt, the catalog keeps
showing artifacts and emits its existing warning, while membership falls back
to the empty tuple. This feature does not weaken that safe, read-only fallback.

## Boundary and Git status

No SQL, BIGINT storage/scaling, protected query helper, Docker, credential,
dependency, signal-artifact schema, or position code was changed by this work.
The worktree contained unrelated pre-existing modifications and untracked
Backtest files; they were preserved. No commit, amend, reset, or cleanup was
performed.

`git diff --check` exits zero; it emits only pre-existing CRLF conversion
notices. The protected-path status command reports existing tracked changes in
`app/main.py` and `app/pages/data_preparation.py`; this feature did not modify
either file. `app/commons/common_queries.py` and Docker files have no current
tracked diff.
