# Trend Classification Validation

## Status

Live read-only validation completed on 2026-08-02. No production threshold,
SQL, storage, or UI behavior was changed.

## Scope

The validation compares these existing contracts:

- Legacy: `common_functions.provide_advice()` classifies from
  `possibility_up` only.
- Current: `pages.analyze_visualization._classify_statistical_trend()` uses
  direct Up and Down probabilities.

The pure comparison helpers are in `app/commons/validation.py`. The read-only
collector is in `scripts/validate_trend_classification.py`; it reuses
`analyze_ticker()` and fixed windows `(5, 5)`, `(10, 5)`, and `(20, 10)`.

## Execution record

| Check | Result |
|---|---|
| Docker/PostgreSQL services | PostgreSQL healthy; app running |
| Deterministic ticker sample | 64 tickers, lexicographically ordered, excluding `VNINDEX` and requiring at least 260 rows |
| Fixed windows | `(5, 5)`, `(10, 5)`, `(20, 10)` |
| Valid observations | 190 |
| Excluded observations | 2: `ACC`/`20,10`, `ACS`/`20,10`, both no valid signals |
| Eligible observations | 151 (`total_signals >= 30`) |
| All valid label changes | 75 / 190 (39.47%) |
| Eligible label changes | 65 / 151 (43.05%) |
| Focused validation and mocked probe tests | 14 passed on host |
| Docker focused validation/page/probe suite | 22 passed |
| Docker full unittest discovery | 137 passed |
| Probe CLI and AST checks | Passed on host |
| Reproducible raw observation snapshot | `2026-08-02-trend-classification-validation-data.csv` |

The existing compose service mounts `app/` at `/app` but does not mount the
repository-level `scripts/` directory. For this run, the reviewed probe was
copied temporarily into the running app container; no Docker configuration was
changed.

## Eligible transition matrix

| Legacy \ Current | Strong Up | Up | Sideways | Down | Strong Down |
|---|---:|---:|---:|---:|---:|
| Strong Up | 2 | 0 | 0 | 0 | 0 |
| Up | 0 | 21 | 0 | 0 | 0 |
| Sideways | 0 | 0 | 30 | 2 | 0 |
| Down | 0 | 0 | 59 | 31 | 0 |
| Strong Down | 0 | 0 | 5 | 1 | 2 |

Eligible legacy/current counts:

- Legacy: Strong Up 2, Up 21, Sideways 30, Down 90, Strong Down 8.
- Current: Strong Up 2, Up 21, Sideways 94, Down 32, Strong Down 2.

## Divergence interpretation

- The largest change is legacy bearish to current Sideways: 64 eligible rows.
  Of those, 46 had Down as the dominant probability, 11 had Up dominant, and
  7 had No Change dominant.
- The 7 No Change cases are the intended correction for treating low Up
  probability as bearish evidence.
- The 46 Down-dominant cases are threshold-sensitive: direct Down probability
  remained below the current `53%` Down cutoff, so the current classifier
  correctly followed its defined contract but deserves separate product review
  if Down-majority outcomes should not display Sideways.
- Three eligible rows became current bearish from a non-bearish legacy label;
  all had direct Down evidence and Down as the dominant outcome. This supports
  the current classifier's direct-evidence distinction.
- Changed eligible rows by window: `5,5` = 25, `10,5` = 28, `20,10` = 12.
  Their signal-count ranges were 32–550, 31–720, and 48–330 respectively.

No threshold recalibration is justified by this descriptive sample alone.
Any change to current display semantics requires a separate approved task.

## Interpretation

The sample confirms both intended and review-worthy divergence classes. The
validation task is complete. Production behavior remains unchanged pending any
separate approved review of the 46 Down-dominant rows displayed as Sideways.
