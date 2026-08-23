# V3 Frozen-Roster Price Audit

Audit run: 2026-08-21 (Asia/Ho_Chi_Minh)

Locked temporary input: `VCB, REE, FPT, SSI, VIC, PLX, DHG, HPG`

The audit made one parameterized, read-only raw-OHLCV query for the literal
roster, from 1900-01-01 through 2026-08-21. It wrote no database rows, jobs,
or signal artifacts. The latest observed row for every ticker was 2026-08-14.
Swing coverage measures daily history; Mid-term coverage measures completed
`W-FRI` labels only.

| Ticker | Raw rows | First / last observed | Price audit | Swing years | Mid-term years | Study history sufficient | Research decision |
| --- | ---: | --- | --- | ---: | ---: | --- | --- |
| VCB | 3,988 | 2010-08-17 / 2026-08-14 | clean | 15.99 | 15.98 | true | include |
| REE | 3,989 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 2.97% | 15.99 | 15.98 | true | exclude: not clean |
| FPT | 3,987 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 1.51% | 15.99 | 15.98 | true | exclude: not clean |
| SSI | 3,989 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 2.96% | 15.99 | 15.98 | true | exclude: not clean |
| VIC | 3,988 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 1.33% | 15.99 | 15.98 | true | exclude: not clean |
| PLX | 2,326 | 2017-04-21 / 2026-08-14 | invalid: OHLC ordering mismatch 2.06% | 9.32 | 9.32 | true | exclude: not clean |
| DHG | 3,985 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 1.09% | 15.99 | 15.98 | true | exclude: not clean |
| HPG | 3,987 | 2010-08-17 / 2026-08-14 | invalid: OHLC ordering mismatch 1.80% | 15.99 | 15.98 | true | exclude: not clean |

`price_audit_clean` means the existing raw-price audit returned `clean`.
`study_history_sufficient` is independent and requires both at least five
daily Swing years and at least eight completed weekly Mid-term years. All eight
tickers pass the history floors; only VCB is clean. Future V3 research must
therefore exclude REE, FPT, SSI, VIC, PLX, DHG, and HPG without changing normal
UI availability.

The audit also emitted calendar-gap and large-close-move warnings. They do not
alter the decision above: each exclusion is caused by its listed material OHLC
ordering error. This is raw-data quality evidence, not adjusted-price proof.

Roster was selected for long observed histories and blue-chip liquidity; it is
not evidence of edge or generalization across thin or small-cap names.
