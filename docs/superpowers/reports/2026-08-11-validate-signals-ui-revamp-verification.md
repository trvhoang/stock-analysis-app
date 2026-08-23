# Validate Signals UI Revamp — Verification

Date: 2026-08-11

## Delivered

- Validate Signals now clears progress after either success or failure, renders
  No theme before VN-Index AND, shows collapsed signal summaries/details, and
  keeps one manual BUY or Close position action per eligible item.
- Current Positions is the third Backtest Lab tab. It initially loads OPEN
  records, filters by ticker/state, sorts oldest open time first, and refreshes
  saved records plus latest close/P&L only when requested.
- Position histories support optional positive whole-share quantity and atomic
  BUY/SELL price edits. BUY-price edits recalculate only pinned SL/TP from the
  frozen ATR; timestamps, status, frozen ATR, and max hold remain unchanged.
- P&L uses raw BIGINT values internally. UI prices are k VND. OPEN positions
  use latest close for unrealized P&L; CLOSED positions use saved SELL price.
  Quantity multiplies absolute P&L only. Fees and taxes are excluded.
- Existing quantity can be removed through the explicit `Remove quantity`
  control because a populated numeric input cannot reliably express clearing.

## RED/GREEN Evidence

- Task 1 host RED proved `update_position` was absent; host GREEN passed 7/7
  position-store tests.
- Task 2 host RED proved the overview module was absent; host GREEN passed
  12/12 position-store/overview tests.
- Task 3 Docker RED showed only two Backtest Lab tabs. GREEN added Validate
  hierarchy/progress/individual-action coverage.
- Task 4 UI regression initially proved a populated quantity field could not
  be cleared. RED failed with `StopIteration` for missing `Remove quantity`;
  GREEN passed after adding the explicit control. The same test verifies an
  OPEN BUY edit recalculates 50.000 to 51.000 k VND SL/TP with frozen ATR,
  clears quantity, and a CLOSED SELL edit writes 53.000 k VND.

## Final Docker Gate

Command:

```powershell
$backtestModules = Get-ChildItem tests -Filter 'test_backtest*.py' |
  ForEach-Object { 'tests.' + $_.BaseName }
docker compose --env-file .env -f docker/docker-compose.yml exec -T app \
  python -m unittest $backtestModules -v
```

Result: 155 tests passed, 1 expected diagnostics skip, zero failures.
Package-qualified module names are required: plain `unittest discover` makes
the worker subprocess unable to import its fixture module.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec -T app \
  python -m compileall -q backtest_engine pages/backtest_lab.py
```

Result: exit 0.

Read-only live refresh result:

```text
{'records': 0, 'errors': 0, 'latest_tickers': ['FPT', 'VCB'], 'summaries': 0}
```

No position/artifact/database record changed. pandas emitted its expected
DBAPI raw-connection warning because project SQL convention requires
`engine.raw_connection()` for this query.

## Implementation Review

| Category | Result |
| --- | --- |
| Logic | PASS — no auto-close path; per-tuple history prevents cross-signal edits. |
| SQL | PASS — one `sqlalchemy.text()` query, `%(tickers)s` binding, raw connection, no SQL price scaling. |
| Performance | PASS — one latest-close query for deduplicated OPEN tickers; session cache avoids unrelated rerun reads. |
| Integrity | PASS — raw BIGINT persistence, UI-only k VND conversion, atomic history replacement, frozen ATR/max-hold retained. |

No high-severity review findings remain. No protected-boundary, dependency,
Docker, database, artifact, or commit change was made.
