# VCB/REE Counterfactual `min_n` Run

**Run:** 2026-08-21, read-only  
**Scope:** VCB and REE, 2011-08-21--2026-08-21, both no-theme and VN-Index
AND treatments. Swing `min_n=15`; Mid-term `min_n=10`.

This temporarily changed only the in-process certification threshold. Canonical
V3 rulebooks, jobs, artifacts, and DB data were not changed.

| Horizon | Ticker | No-theme `n` | Themed `n` | Result |
| --- | --- | ---: | ---: | --- |
| Swing, `min_n=15` | VCB | 8 | 5 | both `empty: min_n` |
| Swing, `min_n=15` | REE | 5 | 5 | both `empty: min_n` |
| Mid-term, `min_n=10` | VCB | 4 | 2 | both `empty: min_n` |
| Mid-term, `min_n=10` | REE | 6 | 5 | both `empty: min_n` |

VCB used 3,742 rows and remained audit-clean. REE used 3,743 rows and remains
ordering-mismatch audit-ineligible; it still executed normally and failed only
on `min_n`.

## Decision

Requested thresholds do not produce a certified signal set. Highest result is
VCB Swing no-theme `n=8`, still seven exits below 15. Statistical certification
did not proceed: all treatments stopped at `min_n`.

This is counterfactual research evidence, not a valid V3 manual proof. Do not
start Task 8 bulk backfill or change canonical thresholds from this run.
