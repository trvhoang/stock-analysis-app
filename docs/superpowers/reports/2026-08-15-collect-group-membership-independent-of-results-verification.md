# Collect Group Membership Independent of Backtest Results — Verification

**Date:** 2026-08-15  
**Status:** Verified

## Delivered

- A named Collect Signals Group receives every configured batch ticker through
  one recoverable Group JSON update before theme preflight or ticker execution.
- Empty certifications, ticker failures, retries, and theme failures no longer
  decide Group membership. A Group-store write failure aborts before theme or
  ticker work begins.
- Blank and `N/A` Group choices remain no-op membership writes.
- Single-ticker `assign_ticker_group()` remains available and delegates to the
  batch writer. Named Group membership stays add-only.
- Validate named-Group execution keeps its existing no-saved-signal filter:
  skipped tickers do not validate, eligible siblings run in entered Group order,
  and skipped tickers remain visible in feedback.
- Group JSON ticker order is now nonsemantic: unordered uppercase unique lists
  load as sorted deterministic members. Duplicate or non-uppercase stored
  tickers remain invalid. The existing BANK JSON was not rewritten.

## TDD Evidence

| Cycle | RED evidence | GREEN evidence |
| --- | --- | --- |
| Batch Group writer | 2 failures: `assign_tickers_group` was absent. | 4 store/compatibility tests passed. |
| Pipeline preflight write | 3 expected errors: pipeline lacked `assign_tickers_group`. | 3 targeted tests passed; full pipeline module 17/17 passed. |
| Validate skip contract | Existing behavior test was tightened to require `FPT`, then `MBB`, with `VCB` reported skipped. | 1 page regression passed; no Validate production code changed. |
| Unordered Group JSON | Reader raised `Group JSON tickers are invalid`. | 5 Group tests passed after order-only rule relaxation. |
| Uppercase contract | New test failed because lowercase `vCB` was accepted. | 6 Group tests passed after restoring uppercase validation. |

## Final Verification

Executed in running `stock_app`:

```text
python -m unittest tests.test_backtest_persistence \
  tests.test_backtest_signal_catalog tests.test_backtest_pipeline \
  tests.test_backtest_job_runner tests.test_backtest_worker \
  tests.test_backtest_page
Ran 108 tests in 9.681s
OK

python -m compileall backtest_engine pages
exit 0

GET http://127.0.0.1:3501/_stcore/health
200 ok
```

The focused suite emits its expected synthetic job-runner traceback and
pre-existing third-party Streamlit `SyntaxWarning` messages; neither is a test
failure.

## Implementation Review

| Category | Findings | Severity |
| --- | --- | --- |
| Logic | Pass — named membership is written once before any execution; empty and failed outcomes cannot remove it. Reader order relaxation preserves uppercase and duplicate validation. | Low |
| SQL | Pass — JSON-only Group store; no SQL, database connection, CTE, or BIGINT price path changed. | Low |
| Performance | Pass — one Group JSON journal/write per batch; no per-ticker Group write remains in the pipeline; no query or cache path added. | Low |

**Verdict:** ✅ PASS

## Scope

No signal artifact, position, replay, UI, dependency, Docker, credential, or
commit change. No runtime Group JSON was modified.
