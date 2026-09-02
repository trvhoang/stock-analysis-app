# Flexible Rulebook Production Benchmark — Verification

## Status

Implementation and Docker runtime verification are complete. No real
PostgreSQL production benchmark has been run, so no production evidence report
or discovery-cap approval exists.

## Implemented

- Read-only `python -m flexible_rulebook.benchmark_runner` CLI.
- Canonical digest-verified report and atomic report writes.
- Isolated cold/warm component-cache sample roots; warm reuse requires a
  matching full source fingerprint and complete reusable cache.
- Fresh parent preflight plus isolated worker source recheck, full catalog
  profile, campaign worker path, phase telemetry, outcome proof, and safe
  incomplete records.
- 4h55 serial ticker-wide sample budget; unstarted slots become
  `BENCHMARK.TICKER_BUDGET_EXHAUSTED`.
- One-slot timing evidence cannot authorize a nonzero discovery cap. Discover
  remains disabled and no policy/UI state changed.

## Host verification

Passed on 2026-08-28:

```text
PYTHONPATH=<workspace>/app python -m unittest discover -s tests -p 'test_flexible_rulebook*.py' -v
245 tests passed; 20 Streamlit AppTest cases skipped because that runtime is unavailable.

python -m compileall -q app/flexible_rulebook
passed

python -m flexible_rulebook.benchmark_runner --help
passed without opening a database connection or writing output
```

## Docker verification

Docker server `24.0.6` passed on 2026-08-28:

```text
docker exec stock_app python -m unittest tests.test_flexible_rulebook_benchmark tests.test_flexible_rulebook_benchmark_runner -v
29 tests passed

docker exec stock_app python -m unittest discover -s tests -p "test_flexible_rulebook*.py" -v
245 tests passed

docker exec stock_app python -m compileall -q flexible_rulebook/benchmark.py flexible_rulebook/benchmark_runner.py
passed

docker exec stock_app python -m flexible_rulebook.benchmark_runner --help
passed without opening a database connection or writing output
```

The container-only test fixture now derives the live Flexible evidence root
instead of assuming the host source layout; the output-root guard itself was
already correct.

A human may explicitly choose a frozen corpus and run the production
benchmark command from the design. A resulting report is evidence only; it does
not enable Discover or change `ScalePolicy`.
