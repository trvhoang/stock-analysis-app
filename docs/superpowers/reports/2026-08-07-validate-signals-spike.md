# Validate Signals — Task 0 Spike Report

**Date:** 2026-08-09  
**Scope:** Read-only artifact, replay, price, and timeframe evidence for the
Validate Signals plan. No Backtest job, database record, current signal
artifact, or source module was changed.

## Evidence

### Current artifacts

| File | Theme | Empty | Certified metrics |
|---|---|---:|---|
| `FPT_signals_no-background-theme.json` | no theme | yes | all `null` |
| `FPT_signals_background-theme.json` | background theme | yes | all `null` |

Both files were last certified on 2026-08-04. The Validate UI must render this
as an unavailable/no-certified-set state; it must not invent a zero-score set.
A temporary non-empty no-theme artifact saved and loaded correctly with only
the `win_rate` metric populated, proving the existing atomic artifact contract
can represent the future read-only fixture path.

### Existing replay and price boundaries

The targeted Docker gate passed **28/28**:

```powershell
docker exec stock_app python -m unittest tests.test_backtest_early_warning tests.test_backtest_trade_execution tests.test_backtest_vnindex_theme tests.test_price_utils -v
```

`check_current_situation(metric="all")` currently returns each metric's
`current` state, entry, SL/TP, signal/entry/exit dates and prices, and theme
state. It does not yet return current score, ATR, latest raw close, or actual
as-of date. A temporary all-three-metric probe measured **three FPT history
loads**—one per metric—so Task 1 must safely consolidate replay work by
horizon.

`prepare_price_for_output(..., PRICE_OUTPUT_UI)` converts raw values to k VND;
the export mode returns original raw values unchanged. No UI-input-to-raw helper
exists yet; Task 2 owns that narrow addition.

### Mid-term as-of probe

Input daily rows were 2026-08-03, 2026-08-04 (BUY date), and 2026-08-05
(as-of date). `to_weekly_ohlcv()` returned one weekly row with label
2026-08-09, `open=100`, `high=103`, `low=99`, `close=102`, and `volume=33`.
The BUY date and weekly output share the same `W-SUN` period. No source row
after 2026-08-05 was supplied or used.

The Sunday timestamp is a resampling period label, not future market data.
Therefore it must never become the current market as-of date.

## Frozen holding contract

1. A manually entered BUY or SELL date must match a ticker trading date.
2. Validation `as_of_date` is always the maximum raw ticker source date, never
   a weekly resample label.
3. Swing holding counts raw daily ticker bars on or after the BUY date through
   `as_of_date`, inclusive.
4. Mid-term maps BUY and as-of dates to `W-SUN` periods, counts only periods
   containing raw source rows through `as_of_date`, and counts the current
   partial period as its current weekly bar. No daily exit calculation is
   permitted.
5. The pre-existing Mid-term next-week minimum exit and inclusive 16-bar
   timeout remain unchanged: a partial entry week is bar 1; normal exits first
   become eligible in the following weekly period.

The probe proves no future source data was consumed, so this contract clears
the Task 0 no-look-ahead gate.

## Environment precondition

The running `stock_app` currently has `POSTGRES_PORT='5432'` but its explicit
`DATABASE_URL` authority is `db:`. This is the known Compose interpolation
issue, not a Task 0 test failure. Live validation in Task 6 requires the app
to be recreated from the repository root with:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --force-recreate app
```

## Task 0 Gate

**PASS.** Artifact states, non-empty fixture behavior, replay gap, price
boundary, as-of mapping, and the runtime precondition are evidenced. Task 1
may start only on user signal.
