# Validate Signals Drafts and Manual Positions Verification

Date: 2026-08-12

## Delivered

- Score similarity now uses `current_score / BUY threshold` even when VN-Index
  eligibility is false. Eligibility remains a separate BUY/SELL-draft gate.
- Added atomic generic per-ticker histories for P&L-only records and immutable,
  multi-metric saved-set records. Legacy tuple histories remain unchanged.
- Current Positions reads both sources, uses latest raw close for OPEN P&L, and
  counts only database OHLCV dates after BUY through the SELL/latest reference
  date as completed hold sessions.
- Saved-set catalog only reads artifacts. Its preparation replay is read-only
  and freezes ATR/max-hold inputs before position creation.
- Validate Signals has leaf-only indicator names, date-only signal dates,
  `k` price labels, hidden-by-default date-range column, summary grouping, a
  collapsed native popover of column checkboxes, a non-persistent selected row,
  and one session-only trade draft.
- Current Positions completes or cancels that draft, supports ungated manual
  P&L-only/saved-set positions, and routes edits/closes to exactly one legacy
  or generic record. No action auto-trades or auto-closes.

## Verification Evidence

- Focused Task 1 validation-advice gate: 8 pass.
- Generic/legacy position-store gate: 14 pass.
- Overview/session gate: 16 pass.
- Catalog/validation/monitor gate: 18 pass.
- Backtest Lab AppTest gate: 24 pass, including manual Current Positions add
  and completed-session hold-time display regressions.
- Complete package-named Backtest suite:
  `172` pass, `1` expected skip because top-level `scripts` is not mounted in
  Docker.
- Docker compilation for `backtest_engine` and `pages/backtest_lab.py`: pass.
- Scoped trailing-whitespace check and `git diff --check`: pass.
- Read-only live VCB themed replay returned:
  `{'availability': 'available', 'match_level': 100.0, 'theme_eligible': False, 'advice': 'observe'}`.

## Implementation Review

| Category | Finding | Severity |
| --- | --- | --- |
| Logic | Frozen saved-set links, one OPEN saved set, manual close, theme gate, and database-session hold time covered. | Pass |
| SQL | New session loader uses `sqlalchemy.text()`, raw connection, and bound arrays; no SQL price scaling. | Pass |
| Performance | Latest-close and completed-session loads are each batched once per refresh; no per-position query. | Pass |

No artifact, database, Docker, dependency, protected-boundary, or commit change was made.
