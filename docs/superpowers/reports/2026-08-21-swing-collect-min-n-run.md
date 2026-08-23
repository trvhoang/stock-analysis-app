# Swing Collect Run: `min_n` Rejections

**Run:** 2026-08-21 21:38 ICT  
**Job:** `ef0412da7a504a76843fe3abb7657b95`  
**Request:** TCB, VCB, REE, FPT, HPG, MSN; Swing; 2011-08-21--2026-08-21;
VN-Index theme enabled.

## Result

Job completed without errors. It wrote all 12 requested schema-3 documents
(six no-theme and six themed). Every document is terminal `empty` with
`rejection_reason: min_n`; no `signal_set` was certified.

Swing certification requires at least 22 completed exits per treatment.

| Ticker | No-theme exits | Themed exits | Audit |
| --- | ---: | ---: | --- |
| TCB | 2 | 2 | clean |
| VCB | 8 | 5 | clean |
| REE | 5 | 5 | ordering-mismatch, ineligible |
| FPT | 5 | 4 | ordering-mismatch, ineligible |
| HPG | 6 | 5 | ordering-mismatch, ineligible |
| MSN | 8 | 6 | ordering-mismatch, ineligible |

Best observed count is 8, below the locked minimum of 22. The four
ordering-mismatch audits remain normal V3 results but are audit-ineligible by
design; they did not cause the `min_n` rejection.

## Decision

This is a controlled certification outcome, not a job, persistence, or Docker
failure. Do not tune rules or lower `min_n` to force a result. Task 7's required
manual nonempty V3 proof remains unmet; do not start Task 8 bulk backfill.

**Evidence:** `app/backtest-status/ef0412da7a504a76843fe3abb7657b95.json`
and its 12 output paths.
