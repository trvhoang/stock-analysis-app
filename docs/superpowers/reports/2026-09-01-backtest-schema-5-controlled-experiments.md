# Backtest Schema 5 Controlled Experiments

**Exploratory — gross. Training is in-sample; test is historical test —
previously observed. Nothing here is statistically certified, profitable,
tradable, or promoted.**

## Outcome

The two predeclared experiments ran against the frozen schema-5 sample through
`2026-08-28`.

- Eligible completed runs: **14**.
- Explicit `not_run`: **2** (`HAP` Swing and Mid-term; source gap 58 sessions).
- Variants passing every training gate: **0**.
- Product promotions or canonical changes: **0**.
- Immutable research artifacts:
  `app/backtest-research/schema5-controlled-experiments/`.
- Baseline prerequisite report SHA-256:
  `fc55e501084744d148098d3be3250488192e9dea51d0e332ead3a276f7d8ca9c`.
- All 16 canonical baseline hashes still exactly match the pre-experiment
  verification report.

Every definition evaluated both no-theme and VN-Index-AND. Training DSR chose
the preferred treatment for that definition; ties or unavailable DSR chose
no-theme. All four training executions completed before any historical-test
execution. The frozen training selection digest remained unchanged after test
metrics were calculated.

## Immutable definitions

| Horizon | Role | Definition | Immutable ID |
|---|---|---|---|
| Swing | Control | EMA5>EMA13 + Alligator up; RSI(9) upcross 52 | `btr_d5412fca5c74c0e211194cc4775d20f0423296c8c9dc14ec71049281567bd2f8` |
| Swing | Variant | EMA5>EMA13; RSI(9) upcross 52 | `btr_72f3a40911c011c8d278368aa4ebfc16370f093acc867b619bdf70868208554c` |
| Mid-term | Control | SMA8>SMA21 + Alligator up; RSI(14) upcross 65 | `btr_65f401783a4c4e350249462e9dfdd0d0a0e705b0be7c45e272016d927971d40a` |
| Mid-term | Variant | Same setup; close upcross SMA8 | `btr_3c87bd229f988c292719a9b308a47bb69767d14e31dc34f7f9bea55624a8d06d` |

## Training decisions

Treatments are `Excluded` (no-theme) or `Included` (VN-Index-AND). `Pairs`
shows matched control/variant intervals; unmatched counts are control/variant.
A positive lead means the variant signal fired earlier in native bars.

| Ticker | Horizon | Control theme | Variant theme | Pairs | Unmatched | Median lead | Failed gates |
|---|---|---|---|---:|---:|---:|---|
| VCB | Swing | Excluded | Excluded | 33 | 0 / 41 | 0.0 | rank; lead; MAE; stop rate; drawdown |
| DHC | Swing | Excluded | Included | 28 | 10 / 21 | 0.0 | lead |
| DSN | Swing | Included | Included | 28 | 0 / 17 | 0.0 | lead; stop rate; drawdown |
| ELC | Swing | Excluded | Excluded | 27 | 0 / 34 | 3.0 | rank; MAE; stop rate; drawdown; year omission |
| BVH | Swing | Included | Included | 25 | 0 / 27 | 0.0 | rank; lead; MAE; stop rate; drawdown |
| HAP | Swing | — | — | — | — | — | `not_run`: `max_gap_sessions_exceeds_20` |
| DRC | Swing | Excluded | Excluded | 38 | 0 / 33 | 0.0 | lead; stop rate; drawdown |
| CSM | Swing | Excluded | Excluded | 31 | 0 / 38 | 0.0 | rank; lead; MAE; stop rate; drawdown |
| VCB | Mid-term | Excluded | Excluded | 7 | 3 / 5 | 1.0 | distinct years; year omission |
| DHC | Mid-term | Excluded | Excluded | 8 | 6 / 7 | 0.5 | rank; concentration |
| DSN | Mid-term | Excluded | Excluded | 5 | 10 / 10 | 0.0 | rank; concentration; drawdown; year omission |
| ELC | Mid-term | Excluded | Included | 6 | 5 / 3 | 1.5 | concentration |
| BVH | Mid-term | Excluded | Excluded | 2 | 6 / 8 | -2.0 | concentration |
| HAP | Mid-term | — | — | — | — | — | `not_run`: `max_gap_sessions_exceeds_20` |
| DRC | Mid-term | Included | Included | 5 | 4 / 6 | 1.0 | rank; distinct years; concentration; drawdown; year omission |
| CSM | Mid-term | Excluded | Excluded | 7 | 2 / 4 | 0.0 | rank |

No failed gate was relaxed. DHC Swing came closest, but its median entry lead
was 0 rather than the required at least 1 bar. ELC and BVH Mid-term ranked
ahead on training metrics but failed the fixed annual concentration guard.

## Training diagnostics

Cells show control → variant. Values below are rounded for reading; immutable
JSON retains exact unrounded values and every leave-one-year-out record.

### Swing

| Ticker | n | Win rate % | Gross return % | Sharpe | Mean MAE % | Stop % | Max DD % | Positive year omissions |
|---|---|---|---|---|---|---|---|---|
| VCB | 33 → 74 | 57.576 → 48.649 | 66.827 → 53.452 | 0.409 → 0.132 | 2.866 → 3.448 | 36.364 → 47.297 | 10.935 → 22.027 | 10 → 10 |
| DHC | 38 → 49 | 42.105 → 51.020 | 5.513 → 68.377 | 0.020 → 0.179 | 4.829 → 4.510 | 47.368 → 44.898 | 38.651 → 22.430 | 4 → 10 |
| DSN | 28 → 45 | 50.000 → 53.333 | 14.471 → 33.115 | 0.172 → 0.241 | 2.239 → 2.138 | 39.286 → 40.000 | 7.973 → 9.817 | 9 → 10 |
| ELC | 27 → 61 | 40.741 → 39.344 | 3.445 → -21.229 | 0.017 → -0.045 | 5.278 → 5.383 | 48.148 → 57.377 | 31.524 → 59.891 | 6 → 4 |
| BVH | 25 → 52 | 52.000 → 50.000 | 45.788 → 67.246 | 0.306 → 0.215 | 3.451 → 3.813 | 44.000 → 46.154 | 14.882 → 20.457 | 10 → 10 |
| DRC | 38 → 71 | 50.000 → 50.704 | 51.569 → 99.387 | 0.223 → 0.246 | 3.814 → 3.471 | 44.737 → 46.479 | 14.626 → 21.628 | 10 → 11 |
| CSM | 31 → 69 | 54.839 → 47.826 | 50.451 → 66.821 | 0.246 → 0.165 | 3.831 → 3.855 | 41.935 → 46.377 | 24.027 → 24.333 | 10 → 11 |

### Mid-term

| Ticker | n | Win rate % | Gross return % | Sharpe | Distinct years | Concentration | Max DD % | Positive year omissions |
|---|---|---|---|---|---|---|---|---|
| VCB | 10 → 12 | 70.000 → 83.333 | 63.290 → 101.605 | 0.676 → 1.160 | 8 → 7 | 0.275 → 0.262 | 8.081 → 6.314 | 8 → 7 |
| DHC | 14 → 15 | 64.286 → 60.000 | 74.939 → 73.386 | 0.401 → 0.358 | 9 → 9 | 0.204 → 0.233 | 35.493 → 31.272 | 9 → 9 |
| DSN | 15 → 15 | 53.333 → 40.000 | 37.174 → 19.324 | 0.349 → 0.153 | 9 → 9 | 0.241 → 0.267 | 10.387 → 18.817 | 9 → 8 |
| ELC | 11 → 9 | 54.545 → 66.667 | 52.707 → 81.320 | 0.303 → 0.575 | 5 → 5 | 0.516 → 0.633 | 23.985 → 20.275 | 4 → 5 |
| BVH | 8 → 10 | 25.000 → 40.000 | -35.045 → 16.557 | -0.356 → 0.100 | 6 → 7 | 0.318 → 0.333 | 45.026 → 32.918 | 0 → 5 |
| DRC | 9 → 11 | 66.667 → 63.636 | 68.771 → 65.427 | 0.611 → 0.441 | 6 → 5 | 0.259 → 0.438 | 11.307 → 28.887 | 6 → 5 |
| CSM | 9 → 11 | 66.667 → 54.545 | 66.006 → 53.251 | 0.649 → 0.476 | 6 → 7 | 0.374 → 0.287 | 8.770 → 8.770 | 6 → 7 |

## Previously-observed test evidence

These values were opened only after training selection was frozen. They did
not promote, reject, or reverse a definition.

| Ticker | Horizon | n C→V | Win % C→V | Gross return % C→V | Sharpe C→V |
|---|---|---|---|---|---|
| VCB | Swing | 21 → 34 | 47.619 → 55.882 | 16.350 → 47.104 | 0.176 → 0.317 |
| DHC | Swing | 11 → 29 | 45.455 → 41.379 | -3.604 → -9.482 | -0.073 → -0.070 |
| DSN | Swing | 19 → 31 | 36.842 → 29.032 | -4.015 → -17.318 | -0.059 → -0.175 |
| ELC | Swing | 16 → 38 | 50.000 → 39.474 | 18.841 → -13.807 | 0.137 → -0.051 |
| BVH | Swing | 10 → 27 | 70.000 → 44.444 | 24.453 → 18.207 | 0.461 → 0.126 |
| DRC | Swing | 16 → 37 | 50.000 → 43.243 | 10.759 → 3.317 | 0.116 → 0.016 |
| CSM | Swing | 16 → 39 | 50.000 → 41.026 | 12.005 → -3.622 | 0.115 → -0.015 |
| VCB | Mid-term | 5 → 5 | 20.000 → 40.000 | -13.781 → 1.022 | -0.636 → 0.023 |
| DHC | Mid-term | 4 → 5 | 50.000 → 80.000 | 17.854 → 23.645 | 0.391 → 0.479 |
| DSN | Mid-term | 6 → 5 | 50.000 → 40.000 | 15.944 → 0.634 | 0.286 → 0.013 |
| ELC | Mid-term | 6 → 3 | 50.000 → 66.667 | 25.794 → 22.617 | 0.275 → 0.437 |
| BVH | Mid-term | 6 → 5 | 50.000 → 20.000 | 7.426 → -28.917 | 0.094 → -0.558 |
| DRC | Mid-term | 2 → 4 | 50.000 → 25.000 | -10.288 → -11.256 | -0.675 → -0.213 |
| CSM | Mid-term | 2 → 4 | 0.000 → 75.000 | -20.511 → 40.665 | -11.422 → 0.746 |

## Limits and promotion gate

- Gross simulation excludes fee, tax, slippage, impact, and partial fills.
- Test evidence has been viewed previously and is not untouched.
- MAE is a conservative daily-bar proxy using lows through the exit bar;
  daily OHLC cannot reveal intrabar order and may include a low after the
  simulated exit trigger.
- The sample is a falsification set, not a representative market claim.
- DSR selects treatment only; no result is statistically certified.
- Research artifacts are content-addressed `backtest_research_schema5_v1`
  documents and contain no product rulebook ID.

The promotion gate is closed. The controls remain selected for every completed
run, and no canonical Top 3, saved-signal set, validation action, or position
identity was changed.
