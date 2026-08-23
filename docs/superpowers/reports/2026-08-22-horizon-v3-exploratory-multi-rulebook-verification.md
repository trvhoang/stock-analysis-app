# Horizon V3 Exploratory Multi-Rulebook Verification

**Date:** 2026-08-22  
**Result:** Complete. Validate Positions remains blocked pending user direction.

## Verification

- Focused Docker suite: **91/91 passed**.
- Static checks: `compileall backtest_engine pages/backtest_lab.py` passed; exploratory and regeneration imports passed.
- Legacy invalidation: **18** V3 artifact filenames overwritten without payload reads; **12** canonical schema-4 `requires_regeneration` artifacts written; **56** job IDs marked `requires_regeneration`.
- Fresh normal collection: VCB Swing, requested `2011-08-22` to `2026-08-22`; effective end `2026-08-21`; clean audit; `calendar_10y_5y`; **15** candidates; success.

## Fresh VCB Swing Top 3

All rows are **Exploratory — gross**. Ranking uses training only.

| Rulebook | Preferred | Train n / win rate / profit % / Sharpe | Test n / win rate / profit % / Sharpe |
|---|---|---|---|
| `swing_rulebook_v4__joint_trend__rsi_upcross` | no-theme | 33 / 57.57575757575758 / 67.61378227059511 / 0.41541725001967417 | 21 / 47.61904761904761 / 17.879465947338044 / 0.1956099334936919 |
| `swing_rulebook_v4__adx__joint_trend__rsi_upcross` | no-theme | 27 / 55.55555555555556 / 54.125406062071505 / 0.3876926335265331 | 20 / 45.0 / 15.221045228947034 / 0.17120081476345958 |
| `swing_rulebook_v4__joint_trend__rsi_upcross__volume` | no-theme | 11 / 54.54545454545454 / 26.475265945272106 / 0.3871632185130638 | 7 / 42.857142857142854 / 0.2909778356112753 / 0.011240081661864973 |

P-values are informational. The first two preferred no-theme training rows have p-value `0.000999000999000999`; the third is N/A because `n <= 20`.

## Self-review

| Category | Result |
|---|---|
| Logic | Pass: independent partitions, three-date boundary filtering, unrounded ranking, DSR-only treatment selection, p-value informational only. |
| SQL | Pass: no new SQL; existing bounded raw-connection loaders retain parameter binding. |
| Performance | Pass: one ticker and one VN-Index load per run; fixed 30 in-memory treatment executions. |
| Safety | Pass: regeneration is filename-only; audit-ineligible results are blocked in UI and direct schema-4 signal-backed position creation. |

One defect surfaced in the fresh run: the `n > 20` persistence branch referenced an undefined p-value-status constant. A regression test was added, the constant was corrected, and the rerun succeeded.

The broader Docker discovery suite also exposed a pre-existing environment-only import failure for `test_trend_classification_probe` (`scripts` is not available inside the app container). It is outside this V3 scope; focused V3 verification passes.
