# Validate Signals Advice and Position Monitoring — Verification

Date: 2026-08-09

## Scope

Verified approved `Validate Signals` advice, manual-position persistence,
native-clock monitoring, and Streamlit orchestration. No commit was created.

## Automated gates

| Gate | Result |
| --- | --- |
| Task 4 service gate | 30/30 passed: advice, position store, monitor, replay. |
| Task 5 UI/job/replay gate | 47/47 passed. |
| Final explicit Backtest gate | 105 passed; 1 expected skip. |
| Python compilation | `backtest_engine` and `pages` compiled in Docker. |
| Whitespace | `git diff --check` exited 0. |

The skipped diagnostics test requires top-level `scripts`, deliberately absent
from the Docker test container. Dependency `SyntaxWarning` output and pandas'
DBAPI warning did not produce a test failure or application exception.

## Regression proof

- Corrupt themed position history leaves no-theme advice available.
- Stale ticker/theme selection guard was forced RED, then restored GREEN.
- Multi-BUY test reproduced a partial write when later input had invalid ATR.
  Every selected tuple now preflights before any position file write.

## Live-safe validation

Real FPT history ran against temporary Docker artifact/position roots. Current
`ticker-signals` was not overwritten.

| Check | Result |
| --- | --- |
| No-theme artifact | Available |
| VN-Index AND artifact | Available; current eligibility `false` |
| Selected no-theme metrics | `win_rate`, `profit` |
| Shared locked BUY as-of | `2026-08-07` |
| Raw/UI BUY round trip | Exact equality |
| Manual close | Closed history retained |
| Second tuple | Remained independently open |
| Cleanup | Temporary Docker directory absent |

Temporary artifact has three non-null metrics only to exercise multi-selection;
it is test evidence, not a certified recommendation.

## Implementation review

| Category | Finding | Severity |
| --- | --- | --- |
| Logic | Raw/UI conversion, locked as-of BUY date, long-only manual actions, and stale-result protection pass. | Pass |
| Timezone | SELL default uses `Asia/Ho_Chi_Minh`. | Pass |
| SQL | No SQL added or changed. | Pass |
| Performance | Validation occurs only after click; result is session-scoped; page adds no query-in-loop. | Pass |
| Storage | Independent per-tuple writes are atomic. A filesystem failure after one independent write can still leave that tuple open; UI reports count and requires revalidation. Cross-file transaction is out of scope. | Low |

Protected-path review found no changed `common_queries.py`, data preparation,
Docker, or credentials. Existing `app/main.py` Backtest navigation diff
predates this task and was not changed.

## Verdict

Approved-plan functionality verified. Cross-file filesystem rollback remains
intentionally excluded by append-only separate tuple histories.
