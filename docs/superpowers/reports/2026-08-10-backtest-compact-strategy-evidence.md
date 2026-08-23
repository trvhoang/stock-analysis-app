# Backtest Compact Strategy Revamp Evidence

## Task 0 — Frozen Baseline

**Date:** 2026-08-10

### Contract RED Gate

Command:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_backtest_signal_combos -v
```

Observed result: 5 existing tests passed and the new compact-rulebook test
failed exactly as expected. Legacy combinations have no `strategy_id`; the
generated set is 270 no-theme combinations and 810 include-theme combinations
(no-theme, `AND`, and `OR`). This proves the fixed three-strategy rulebook is
not already implemented.

### VCB Baseline Evidence

The previous fresh 15-year VCB Mid-term themed job persisted an empty
certification payload at
`ticker-signals/VCB/VCB_signals_background-theme.json`. Captured payload hash:

```text
48b82c4b86425b21fa52c9f1a725c646a65e16275334d01f79a75afcfff01d2d
```

The prior read-only probe found non-zero VCB score activity and crossings, so
the empty artifact is a certification outcome, not proof of missing raw price
history. VCB remains a canary, never a tuning target.

### Simulation Boundary

`simulation-result-VCB-15y.md` is not a production oracle. Its existing
Mid-term trace resolves timeout after one weekly bar and some Swing exits occur
before the production three-daily-bar minimum. It may inform candidate-trade
inspection only after production golden traces prove the native execution
contract.

### Write Boundary

Task 0 performed no database query, job submission, signal-artifact write,
position write, or Git commit.

## Task 7 — Current Database Audit Blocker

The deterministic test/compile gate passes, but the required live frozen-
universe audit cannot complete from current database data under the approved
OHLC-ordering rule.

Read-only audit result for 2011-08-09 through 2026-08-09:

```text
candidate tickers: 1,864
clean: 0
indeterminate: 0
invalid: 1,864
VCB: invalid; 3,737 rows; OHLC ordering is invalid
```

The first VCB examples have `close = high + 1` raw unit. The aggregate
database result is materially larger, so a one-unit rounding tolerance would
not solve it:

```text
invalid rows: 513,433
maximum GREATEST(open, close) - high: 23,696,720 raw units
maximum low - LEAST(open, close): 88,163 raw units
```

No audit result, universe selection, job, current signal artifact, position,
or database row was written. The next action needs an explicit policy for
material OHLC-ordering violations; silently weakening or removing this audit
would contradict the approved clean-universe contract.

## Task 7 — Approved Audit Scope Policy

The approved policy scopes exact OHLC ordering to `audit_history()` only.
Normal `validate_ohlcv()` still rejects missing, non-numeric, non-positive, or
out-of-order structural data, but it does not repair or reject an exact OHLC
ordering violation. Each new normal Backtest artifact records
`audit_eligibility`; Backtest Lab warns when that marker is false.

Regression evidence:

```text
Docker Backtest suite: 84 tests ran; 1 expected unmounted CLI skip; no failures
Docker compileall: backtest_engine and pages/backtest_lab.py passed
Live VCB preflight (2011-08-10 through 2026-08-10):
  normal_backtest_valid: True
  normal_errors: ()
  audit_status: invalid
  audit_errors: (OHLC ordering is invalid,)
  rows: 3,738
Full VCB 15-year Swing pipeline in auto-deleted temporary output:
  empty: False
  audit_eligibility: {eligible: False, status: invalid,
                      reasons: [OHLC ordering is invalid]}
```

This read-only preflight created no job, signal artifact, position, or database
write. It restores normal VCB Backtest execution while preserving the strict
frozen-universe exclusion and its unresolved current-database blocker.

## Task 7 — Current-Database OHLC Policy Verification

The approved derived-data policy fixes the false rejection without changing a
raw DB value: shared available history is used when requested history predates
the database; an OHLC mismatch `<=1%` is a warning and Backtest derives an
OHLC envelope in memory; a mismatch `>1%` remains invalid. The `>=15%`
close-discontinuity exclusion is unchanged.

```text
Docker Backtest suite: 88 tests ran; 1 expected unmounted CLI skip; no failures
Docker compileall: backtest_engine and pages/backtest_lab.py passed
Current-database frozen-universe audit:
  clean: 21; indeterminate: 6; invalid: 1,837
  VCB: clean; shared history 2011-08-10 through 2026-08-10
  VCB warning: OHLC ordering mismatch 0.95% is within 1.00% tolerance
  selection: VCB, DHC, HJS, ELC, VPL, C47, HAP, CSM
VCB 15-year Mid-term no-theme temporary pipeline:
  audit_eligibility: {eligible: True, status: clean}
  empty: True; certified metrics: []
```

The Mid-term empty result is no longer an OHLC/audit failure. It requires the
planned multi-ticker diagnostics before any rule or threshold change.

## Tasks 6–7 — Frozen-Universe Diagnostic and Final Gate

The approved implementation-plan split overrides the earlier master-design
split for this evidence: calibration ends `2020-12-31`, holdout starts
`2021-08-09`, and `2021-01-01` through `2021-08-08` is excluded from both
partition reports. Certification still uses the complete unique-event history.

The final collector is read-only. It loads candidate OHLCV once, loads
VN-Index once, reuses those raw frames for eight tickers × four
horizon/theme variants × three strategies, and creates no job, database row,
or `ticker-signals` artifact. Calibration and holdout are reporting-only
completed-event partitions; only full history runs DSR/permutation gates.

```text
Current-DB query range: 2011-08-10 through 2026-08-10
Frozen universe: VCB, DHC, HJS, ELC, VPL, C47, HAP, CSM
Variants: Swing no-theme, Swing VN-Index AND,
          Mid-term no-theme, Mid-term VN-Index AND
Strategies per variant: 3
Results: 96
Statistical inputs: n >= 30; DSR >= 0.95; permutation p <= 0.05;
                    1,000 moving-block samples; seed 42; block size 20
Read-only runtime: 204.64 seconds
Write boundary: database=False, jobs=False, artifacts=False
```

| Ticker | Audit | Rows | Pre-2021 return | Qualified results |
|---|---|---:|---:|---:|
| VCB | clean | 3,741 | 612.35% | 5 |
| DHC | clean | 3,625 | 1,904.74% | 11 |
| HJS | clean | 2,598 | 1,519.41% | 7 |
| ELC | clean | 3,634 | -28.97% | 0 |
| VPL | clean | 408 | 12.59% | 0 |
| C47 | clean | 3,549 | 292.52% | 2 |
| HAP | clean | 3,680 | 247.57% | 1 |
| CSM | clean | 3,733 | 378.77% | 3 |

All selected records have zero `>=15%` discontinuity findings. This does not
prove adjustment correctness: a smoothed or hidden corporate action can still
be false-clean with database-only OHLCV.

### VCB Result and Funnel

`missing_next_bar`, `invalid_atr`, and `invalid_entry_price` are zero for all
VCB strategy rows. Full-history `ticker crossings / theme crossings /
completed trades` are reported below with calibration and holdout completed
trade metrics (`n / total return % / Sharpe`).

| Variant | Strategy | Full `n`, return %, Sharpe, DSR | Funnel | Calibration | Holdout | Result |
|---|---|---|---|---|---|---|
| Swing no-theme | MA Cross + RSI + OBV | 189, 171.72, 0.202, 0.996 | 190 / 190 / 189 | 120 / 113.70 / 0.200 | 61 / 53.50 / 0.215 | qualified |
| Swing no-theme | Alligator + RSI + OBV | 184, 184.97, 0.222, 0.998 | 186 / 186 / 184 | 114 / 154.88 / 0.292 | 60 / 41.33 / 0.164 | qualified |
| Swing no-theme | Consensus + RSI + OBV | 163, 147.21, 0.198, 0.992 | 164 / 164 / 163 | 97 / 87.68 / 0.190 | 57 / 55.90 / 0.233 | qualified |
| Swing AND | MA Cross + RSI + OBV | 135, 136.36, 0.230, 0.989 | 190 / 135 / 135 | 83 / 86.37 / 0.227 | 44 / 45.48 / 0.258 | qualified |
| Swing AND | Alligator + RSI + OBV | 143, 123.83, 0.192, 0.971 | 186 / 143 / 143 | 91 / 99.33 / 0.236 | 42 / 35.73 / 0.205 | qualified |
| Swing AND | Consensus + RSI + OBV | 119, 77.39, 0.147, 0.893 | 164 / 119 / 119 | 66 / 34.92 / 0.115 | 44 / 38.84 / 0.216 | DSR reject |
| Mid-term no-theme | MA Cross + RSI + OBV | 32, 34.40, 0.109, 0.677 | 32 / 32 / 32 | 20 / 57.04 / 0.265 | 10 / -8.34 / -0.105 | DSR reject |
| Mid-term no-theme | Alligator + RSI + OBV | 34, 19.47, 0.059, 0.573 | 34 / 34 / 34 | 19 / 33.88 / 0.163 | 13 / -0.11 / -0.001 | DSR reject |
| Mid-term no-theme | Consensus + RSI + OBV | 33, 38.40, 0.120, 0.701 | 33 / 33 / 33 | 18 / 53.46 / 0.270 | 13 / -0.76 / -0.007 | DSR reject |
| Mid-term AND | MA Cross + RSI + OBV | 22, 37.62, 0.186, 0.749 | 32 / 22 / 22 | 13 / 51.25 / 0.412 | 7 / 0.68 / 0.011 | `min_n` reject |
| Mid-term AND | Alligator + RSI + OBV | 26, 26.90, 0.108, 0.633 | 34 / 26 / 26 | 14 / 32.28 / 0.215 | 10 / 8.91 / 0.106 | `min_n` reject |
| Mid-term AND | Consensus + RSI + OBV | 22, 20.24, 0.099, 0.607 | 33 / 22 / 22 | 11 / 33.68 / 0.295 | 9 / 0.85 / 0.012 | `min_n` reject |

Thus VCB's original Mid-term null result is explained by gates, not missing
signals: no-theme has enough trades but fails DSR; theme confirmation reduces
the event count below 30. This evidence does not authorize threshold tuning.

### VCB Trace Endpoints

The returned in-memory diagnostic includes every VCB event. Endpoints below
prove native clock, next-bar entry, long-only exit, and first/last trace range;
no trace was persisted.

| Variant | Strategy | Events | First event | Last event |
|---|---|---:|---|---|
| Swing no-theme | MA Cross | 189 | 2011-11-24 signal; 2011-11-25 BUY; 2011-11-30 SL | 2026-05-18 signal; 2026-05-19 BUY; 2026-06-08 SL |
| Swing no-theme | Alligator | 184 | 2012-01-18 signal; 2012-01-19 BUY; 2012-01-31 TP | 2026-05-14 signal; 2026-05-15 BUY; 2026-05-20 TP |
| Swing no-theme | Consensus | 163 | 2012-01-18 signal; 2012-01-19 BUY; 2012-01-31 TP | 2026-05-18 signal; 2026-05-19 BUY; 2026-06-08 SL |
| Mid-term no-theme | MA Cross | 32 | 2012-02-19 signal; 2012-02-26 BUY; 2012-03-04 TP | 2026-01-18 signal; 2026-01-25 BUY; 2026-02-08 SL |
| Mid-term no-theme | Alligator | 34 | 2012-02-19 signal; 2012-02-26 BUY; 2012-03-04 TP | 2026-02-01 signal; 2026-02-08 BUY; 2026-02-15 SL |
| Mid-term no-theme | Consensus | 33 | 2012-02-19 signal; 2012-02-26 BUY; 2012-03-04 TP | 2026-01-18 signal; 2026-01-25 BUY; 2026-02-08 SL |

Theme variants show the same first/last native-event behavior with fewer
eligible signals; their complete traces are included in the returned report.

### Final Verification and Self-Critique

```text
Docker focused Backtest suite: 66 passed; 1 expected unmounted CLI skip
Compile: backtest_engine and pages/backtest_lab.py passed
Whitespace: git diff --check and changed-file scan passed
```

Review passed: no look-ahead, daily/weekly isolation, raw BIGINT handling,
long-only equal BUY/SELL event contract, unique-event partitioning, per-ticker
statistics, parameterized raw-connection access, artifact compatibility, and
no-write diagnostics. Deliberate ceiling: serial 32-variant evidence takes
about 205 seconds; parallelism would change DB connection behavior and needs
separate approval.
