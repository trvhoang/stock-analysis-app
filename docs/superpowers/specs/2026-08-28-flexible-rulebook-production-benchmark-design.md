# Flexible Rulebook Production Benchmark Design

## Purpose

Provide one explicit, read-only Docker command that measures real Flexible
Rulebook discovery cost against PostgreSQL history.  It produces immutable
measurement evidence for later human review; it does not enable Discover,
increase worker count, alter V3, or create trading advice.

## Scope

The command is `python -m flexible_rulebook.benchmark_runner`.  It runs only
Swing Flexible discovery and uses the existing bounded Flexible history loader,
catalog revision, full catalog `feature_profile`, reference executor,
campaign runner, and isolated worker boundary.

The caller supplies:

- one or more explicit ticker symbols;
- a required fixed `--as-of` date;
- a fixed seed list;
- cold and warm sample counts; and
- an absolute report output path under a mounted directory such as `/data`.

The ticker list, source fingerprints, catalog hash, feature-build-contract
hash, candidate-space hash, execution contract, split, seed, and selected
global slots are recorded in the report.  The report is evidence only.  A
future policy loader may consume a separately reviewed approval document, but
this task leaves `ScalePolicy()` at zero discovery attempts.

## Execution model

Each sample has two timed phases.

1. **Preflight:** fresh-load bounded real history at the fixed as-of date,
   validate/fingerprint it, and resolve the full finite catalog feature profile.
2. **Maximal slot:** freeze a one-slot `CampaignRequest`, start the existing
   isolated Flexible worker, re-verify the frozen source, reuse the exact
   compatible components built in preflight, execute
   train/test/selection/checkpoint/write, and return a terminal campaign
   state.

Cold means the isolated root begins with no component cache. Its parent
preflight fresh-loads and fingerprints source, then builds the full catalog
profile once; the worker must `reuse` those just-built components rather than
build them again. Warm samples rebuild that same isolated cache *before*
timing, persist its source fingerprint, then fresh-load source and use
`reuse`. A changed warm source is `SOURCE.CHANGED`; a missing, stale, partial,
or corrupt warm component is a safe miss, never a silent rebuild. A warm result
is diagnostic only and can never raise an authorized discovery cap.

The benchmark root is temporary and separate from `app/Flexible-Rulebook`.
It may contain cache, campaign, ledger, and signal-set test evidence during a
sample, but it is removed after measured byte counts are recorded.  The final
report is the only durable output.

## Production evidence requirements

A report records every complete and incomplete sample.  It must never replace
an error, source change, invalid history, or watchdog interruption with a zero
duration.  Per sample it records:

- ticker, seed, global slot, frontier stratum, canonical candidate index,
  per-sample frozen split identity, and source fingerprint;
- cold or warm mode;
- preflight, training, test, selection, write, and maximal-slot durations;
- terminal campaign state and safe error code when present;
- peak process RSS when available;
- peak SQLAlchemy pool checkout count when available; and
- temporary cache and artifact byte counts.

The report derives cold p50, p95, and p99 timing from completed samples only.
Its discovery proof is ineligible unless every configured **ticker and seed**
has at least 100 completed cold samples, every source fingerprint remains
stable for that ticker, and every cold sample reaches the full
training/test/selection/write path with a `completed` terminal campaign state
and no safe error code. A training-only rejection is recorded but is never
called maximal-slot proof.

The report exposes a `BenchmarkRecord` summary only when it is eligible. A
one-slot report leaves `measured_discovery_attempt_caps` empty, so it **cannot**
authorize a nonzero `ScalePolicy` discovery cap. A later, separately reviewed
end-to-end cap-length measurement is required for that authority. No additional
headroom is invented by this task; the existing 25-minute terminal reserve
remains the documented safety boundary.

## Ticker-wide time boundary

Samples run serially in fresh benchmark-child processes. The runner gives each
ticker one fixed 17,700-second (4h55) budget, below five hours. Before another
slot begins it checks the remaining budget; an exhausted ticker writes every
unstarted scheduled sample as `BENCHMARK.TICKER_BUDGET_EXHAUSTED` and continues
to the next ticker. A running child is process-group terminated at its remaining
budget so its nested worker cannot outlive the ticker boundary. The resulting
report is truthfully ineligible rather than silently running a ticker for days.

## Canonical report storage

`ProductionBenchmarkReport` has schema version 1 and a SHA-256 digest of its
canonical payload.  The writer uses a same-directory temporary file, flush,
fsync, and atomic replace.  The reader recomputes the digest and rejects
malformed, changed, incomplete, or non-canonical documents.

The report contains a corpus scope. It is valid only for the exact listed
tickers, catalog/build/execution revisions, and seed set recorded in it. Exact
per-ticker partition boundaries live on samples because shorter histories can
use the approved 65/35 split. A future approval/policy task must reject a source
ticker outside that scope.

## CLI behavior

Target command:

```text
docker exec stock_app python -m flexible_rulebook.benchmark_runner \
  --tickers FPT VCB \
  --as-of 2026-08-28 \
  --seed frb-default-seed-v1 \
  --cold-samples 100 \
  --warm-samples 100 \
  --output /data/flexible-benchmark/report.json
```

The command rejects a non-absolute output path, duplicate/invalid ticker,
non-date as-of value, zero sample count, or a report path below the Flexible
Rulebook evidence root.  It creates no database writes, uses no V3 artifact,
and returns non-zero when the report is ineligible or cannot be written.

## Non-goals

- No automatic discovery-cap authorization.
- No UI control that authorizes or runs the benchmark.
- No worker-pool, fast-executor, append-extension, or 100–200 ticker scan
  enablement.
- No persistent production cache or Flexible Rulebook evidence writes.
- No change to SQL, BIGINT storage/scaling, Docker configuration, credentials,
  V3, Backtest Lab, positions, or validation.
