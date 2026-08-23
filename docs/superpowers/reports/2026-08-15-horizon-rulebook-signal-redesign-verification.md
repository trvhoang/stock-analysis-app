# Horizon Rulebook Signal Redesign — Task 7 Verification

Evidence run: 2026-08-21 (Asia/Ho_Chi_Minh)

## Scope and boundary

The locked temporary roster is `VCB, REE, FPT, SSI, VIC, PLX, DHG, HPG`.
Task 0 independently recorded sufficient Swing and Mid-term history for all
eight, but only VCB as `price_audit_clean`. Aggregate study results therefore
include VCB only; the remaining seven stay transparently excluded for their
material raw-OHLC ordering errors. Normal UI availability is unchanged.

Roster was selected for long observed histories and blue-chip liquidity; it
is not evidence of edge or generalization across thin or small-cap names.

The evidence call was read-only: its declared boundary was database `false`,
jobs `false`, and artifacts `false`. It did not inspect V2 files or status
paths. It made no database, artifact, position, or job-status write.

## Verification gates

- Task 7 focused Docker Backtest gate: 90 passed.
- Diagnostic regression gate: 5 passed.
- Final full Docker Backtest suite: 132 passed.
- Docker compilation, `git diff --check`, and diagnostic import: passed.
- The V3 diagnostic uses the same Boolean entry and flat-to-flat execution
  functions as production; it has no compact-score execution dependency.

## Read-only VCB result

The default 15-year request was evaluated as of 2026-08-21. Raw VCB data
available to both horizons was 3,737 rows from 2011-08-22 through 2026-08-14;
the raw audit was `clean`. It reported the known 0.95% derived-envelope OHLC
warning, calendar-gap warnings, and one 7.00% close-move warning. The timed
two-horizon run completed in 0.945 seconds.

Sequential gate-rejection counts show rows rejected at the first failed gate,
not independent overlapping failures.

| Horizon | Treatment | Missing input | RSI | Joint trend | Volume | ADX | VN-Index AND | Entries | Non-overlap skips | Exits | n / result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Swing | No theme | 26 | 3,449 | 191 | 57 | 6 | — | 8 | 0 | 4 stop / 4 target | 8 / empty: `min_n` |
| Swing | VN-Index AND | 26 | 3,449 | 191 | 57 | 6 | 3 | 5 | 0 | 3 stop / 2 target | 5 / empty: `min_n` |
| Mid-term | No theme | 26 | 726 | 4 | 13 | 1 | — | 4 | 0 | 4 stop | 4 / empty: `min_n` |
| Mid-term | VN-Index AND | 26 | 726 | 4 | 13 | 1 | 2 | 2 | 0 | 2 stop | 2 / empty: `min_n` |

Swing no-theme used its genuine one-trial PSR family; themed Swing used its
two-trial `(no-theme, VN-Index AND)` DSR family. The equivalent Mid-term
families used the same PSR/DSR split. No treatment reaches the locked floors
of Swing `n >= 22` or Mid-term `n >= 20`, so significance scores and p-values
are deliberately absent. No gate, match band, or minimum was adjusted to make
the result qualify.

V3 defines no walk-forward calibration or holdout split. Calibration and
holdout metrics are therefore unavailable, not zero or favorable values. This
is not adjusted-price proof, a VCB guarantee, portfolio-return evidence, or
live-fill/cost realism.

## Manual-proof preflight

Before asking for the required UI proof, a separate read-only no-theme Swing
preflight examined every locked-roster ticker. None can produce the required
nonempty result under the locked V3 rules: VCB `n=8`, SSI `n=7`, DHG/HPG/PLX
`n=6`, and FPT/REE/VIC `n=5`; all terminate empty with `min_n`. No manual
Collect run on that roster can clear Task 7 Step 6. A user must choose a
different ticker for the manual proof; it may not relax a rule, band, or
minimum.

## Excluded roster members

| Ticker | Study history sufficient | Aggregate-study decision |
| --- | --- | --- |
| REE | true | Exclude: price audit not clean |
| FPT | true | Exclude: price audit not clean |
| SSI | true | Exclude: price audit not clean |
| VIC | true | Exclude: price audit not clean |
| PLX | true | Exclude: price audit not clean |
| DHG | true | Exclude: price audit not clean |
| HPG | true | Exclude: price audit not clean |

## Next gate

Task 7 implementation and read-only evidence are complete. Before any Task 8
bulk backfill, the user must manually run Collect Signals for a different,
user-chosen ticker and produce one valid, nonempty schema-3 V3 document. Its
job outcome and exact document will then be inspected read-only. An empty or
invalid result stops the plan.
