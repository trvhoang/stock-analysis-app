# Flexible Rulebook Discover Activation — Verification and Operator Runbook

## Status — 2026-08-30

Implementation and activation verification is complete. A real PostgreSQL
fixed-cap report for VCB exists at
`/data/flexible-benchmark/reports/bedd2992e4a1b783fb8fe53275322a9b123c804c19d10338bce0f91b6721cc74.json`.
Its immutable policy is active at
`/data/flexible-benchmark/policies/f5a304a583890c527e359477687b7bae9af66b21cd6bde267a2abb2a4ea014b6.json`.
Discover is unlocked for VCB with seed `frb-default-seed-v1` and cap 8; normal
preflight and explicit cache-treatment controls still apply.

## Verified in Docker

```text
python -m unittest discover -s tests -p "test_flexible_rulebook*.py" -v
300 tests passed

python -m compileall -q flexible_rulebook
passed

python -m flexible_rulebook.cap_benchmark_runner --help
passed without opening the database or writing evidence

python -m flexible_rulebook.activation --help
passed without opening the database or writing evidence
```

The Streamlit test runtime emitted third-party `SyntaxWarning` messages during
import; the suite completed with exit code zero.

## Production cap evidence

```text
ticker / seed: VCB / frb-default-seed-v1
fixed cap: 8 attempts; worker count: 1
cold windows: 100 completed, 0 failed
p99 preflight: 1.221570579729866 s
p99 cap window: 5.0511912855900984 s
p99 total observed: 6.073418846459721 s
activation total bound: 6.272761865319965 s (p99 preflight + p99 window)
serial ticker elapsed: 531.776620955 s
```

The first activation attempt exposed independent-p99 quantiles whose sum could
exceed measured total. `benchmark_record_from_cap_report` now stores a
conservative additive total bound, covered by a regression test; no benchmark
evidence was edited or regenerated.

## Focused safety review

- Direct-cap policy accepts only the exact cap measured by 100 complete cold
  windows under one 17,700-second serial ticker budget; one-slot evidence
  cannot activate Discover.
- Benchmark roots remain outside the live Flexible evidence root. A policy
  binds a digest-named report, static runtime, ticker/seed scope, source anchor,
  split, and one worker.
- Start validates its historical anchor before freezing fresh current data.
  Resume and Continue reload the campaign's immutable named policy, not the
  mutable active pointer.
- The chosen cache treatment reaches the worker. A cache offer that changes
  after UI preflight is rejected and requires a fresh preflight.
- No SQL, dependency, Docker, price-scaling, V3, positions, or protected-query
  changes were made by this activation work.

## Controlled operator sequence

1. Run the existing one-slot benchmark only as timing context. Independently
   choose a conservative fixed `<cap>`; do not infer it automatically.
2. Choose one allowed ticker, one allowed seed, and a completed historical
   `<as-of>` date. Run exactly 100 cold windows into an absolute location
   outside `Flexible-Rulebook`:

   ```text
   docker exec stock_app python -m flexible_rulebook.cap_benchmark_runner \
     --tickers <TICKER> \
     --as-of <YYYY-MM-DD> \
     --seed <SEED> \
     --cap-attempts <CAP> \
     --cold-samples 100 \
     --warm-samples 0 \
     --output /data/flexible-benchmark/cap-report.json
   ```

   This is a read-only database benchmark, but it can use up to 17,700 seconds
   for its selected ticker. Do not run it while a live production campaign owns
   the Flexible worker lease.
3. Inspect the resulting report. It must be eligible and show 100 completed
   cold windows, the chosen exact cap, one-worker serial budget compliance,
   matching source anchors/splits, and direct timing evidence. An ineligible
   report remains useful diagnostic evidence but must not update
   `active-policy.json`.
4. After independent review, create the immutable policy and atomically set
   the pointer:

   ```text
   docker exec stock_app python -m flexible_rulebook.activation \
     --report /data/flexible-benchmark/cap-report.json \
     --benchmark-directory /data/flexible-benchmark \
     --ticker <TICKER> \
     --seed <SEED> \
     --approved-by <OPERATOR> \
     --approval-note <REVIEW_NOTE>
   ```

5. Open Flexible Rulebook → Discover. Select only the displayed uppercase
   ticker and approved seed, run Preflight, select the offered cache treatment,
   then Start one campaign. Use Refresh for status. Library, Qualification, and
   Current Group BUY Scan consume only committed evidence.

Passing tests alone cannot unlock Discover. Only steps 2–4 create and activate
the required production evidence.
