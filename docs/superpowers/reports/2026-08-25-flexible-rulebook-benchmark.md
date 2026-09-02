# Flexible Rulebook scale-gate report

**Date:** 2026-08-27  
**Status:** Safe default remains active; no production scale expansion enabled.

## Measured evidence

- Flexible campaign/current-scan regression gate: **189 tests passed** in the
  Docker `stock_app` container, plus module compilation.
- This gate measures correctness only. It is **not** a production timing
  benchmark and does not claim 20/100/200-ticker capacity.
- Synthetic Docker fixture (20 tickers, 260 daily bars, one RSI primitive,
  real cache/artifact path): cold **0.473677 s**, warm **0.166481 s**. All 20
  results were `no_current_setup`, with 20 feature receipts and 20 current-scan
  artifacts. These numbers exclude DB latency and are fixture observations,
  not an enablement proof.
- Deterministic discovery maximal-slot fixture: **100 cold** and **100 warm**
  samples in Docker. The fixture used FPT's actual 3,740-bar date shape
  (2011-08-29 through 2026-08-27) and an in-memory cyclic price path solely to
  force one legal RSI(9)-upcross/ATR(14)-target candidate through every phase.
  It completed 165 training and 83 test trades per sample, and verified the
  frozen one-slot `discover_and_evaluate()` result plus reference/dispatcher
  trade equality. It does not claim that FPT produced those returns.

  | p99 phase (seconds; NumPy linear percentile) | Cold | Warm |
  |---|---:|---:|
  | Feature resolve / preflight | 0.088020 | 0.042127 |
  | Training | 0.016695 | 0.012135 |
  | Test | 0.007526 | 0.006172 |
  | Selection | 0.000320 | 0.000343 |
  | Immutable writes | 0.032008 | 0.067083 |
  | Complete maximal slot | 0.049267 | 0.081563 |
  | Total | 0.133270 | 0.110010 |

  Every sample used a distinct temporary cache/artifact subtree; the maximal
  slot included entry-mask composition, train/test execution, metric and Top-3
  selection, definition/receipt/signal-set/ledger/selection writes. The warm
  cache was first populated once, then resolved with `reuse`. There is no
  separate fast executor: parity proves only that the public dispatcher still
  delegates exactly to the reference executor.

  This fixture deliberately excludes repeated database loading/fingerprinting,
  real full-catalog frontier mix, RSS/cache-byte/connection telemetry, retries,
  resume, source-change, and production artifact volume. It therefore does not
  create a `BenchmarkRecord`, choose a discovery attempt cap, or support a
  larger group/worker policy. No missing measurement is represented as zero.

## Active policy

`ScalePolicy()` remains the only enabled policy:

- current Group BUY Scan: at most **15 tickers**;
- discovery attempts: **disabled until a separate discovery record**;
- workers: **1**;
- event fast executor and append extension: **disabled**.

The validator rejects larger limits unless a matching completed benchmark hash,
operation-specific measurements, cold p99 maximal-slot evidence, deadline
headroom, and parity proof are present. The deterministic fixture and
20-ticker current-scan fixture are complete; a separate production-scale
benchmark remains required before any policy expansion.
