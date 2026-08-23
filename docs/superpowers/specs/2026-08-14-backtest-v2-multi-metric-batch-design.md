# Backtest V2 Multi-Metric Candidates and Sequential Batch Design

## Goal

Persist one certified candidate when same strategy wins multiple metrics, then
run up to five ticker Backtests in strict sequence through one background batch
worker.

## Locked decisions

- Artifact format is V2 only. No reader supports V1.
- After V2 implementation and test gate pass, delete exact V1 signal-artifact
  files only. Do not regenerate live artifacts; user reruns later.
- Candidate wins multiple metrics only when current per-metric selection chooses
  exact same `IndicatorCombo`. Never use approximate values or performance.
- Ranking, `n >= 30`, Deflated-Sharpe, permutation, audit, long-only, ATR, and
  data/price/SQL rules remain unchanged.
- Batch ticker input: comma/space separated, auto-capitalized, entered-order
  preserving, unique, one through five tickers.
- No-theme batch: run one ticker at a time.
- Theme batch: create one VN-Index confirmation for request horizon/date range,
  then process tickers one at a time. Each ticker still writes no-theme and
  VN-Index AND artifacts.
- Ticker failure does not stop first pass. Retry every failed ticker exactly
  once after first pass. Final failure remains recorded.
- Shared VN-Index preflight failure waits five seconds, retries once, then
  stops whole batch with clear terminal error if still failing.
- No commits. Current position history is not migrated or altered.

## Chosen architecture

Use one isolated batch-worker subprocess. It owns sequence, shared theme,
retry timing, progress, and terminal records. UI job chaining cannot share
VN-Index safely; disk cache adds stale-data and cache-atomicity risk.

## Artifact V2

Current ticker/theme paths stay unchanged. V2 document:

```json
{
  "schema_version": 2,
  "ticker": "FPT",
  "theme_variant": "no-background-theme",
  "certified_at": "2026-08-14T09:00:00+07:00",
  "empty": false,
  "signal_sets": [
    {
      "metrics": ["win_rate", "profit"],
      "combo": {
        "strategy_id": "ma_cross_rsi_obv",
        "indicators": {
          "trend_direction": ["MA cross"],
          "momentum": ["RSI"],
          "volume": ["OBV"]
        },
        "threshold_score_buy": 60,
        "adx_gate_mode": "hard",
        "horizon": "swing",
        "theme_variant": "no-background-theme",
        "theme_mode": null,
        "direction": "long"
      },
      "horizon": "swing",
      "theme_variant": "no-background-theme",
      "theme_mode": null,
      "vnindex_condition": null,
      "direction": "long",
      "n": 42,
      "win_rate": 63.5,
      "profit": 18.2,
      "sharpe": 1.14,
      "deflated_sharpe": 0.97,
      "p_value": 0.01,
      "date_range": ["2011-08-04", "2026-08-04"]
    }
  ]
}
```

`signal_sets` has unique candidates only. Every `metrics` list is non-empty,
unique, registry-ordered; a metric appears in zero or one candidate. Candidate
order is first winning metric in registry order. `empty` is true only for an
empty list. Future metrics join grouping once added to existing metric registry
and selector/serializer.

V2 writer rejects V1 mapping shape. V2 loader rejects every version except 2;
it never transforms V1. Cleanup is outside application code after final V2
verification.

## Certification and consumers

`certify_top_sets()` keeps current independent winner selection, groups winners
by exact `IndicatorCombo`, serializes each group once, and adds all selected
metric names to `metrics`.

Persistence owns one shared V2 group validator/indexer. It validates no metric
duplication and returns a per-metric view where needed, preventing duplicate
reader logic.

- Result/Markdown: one candidate section, labelled with all metrics. Metrics
  absent from groups retain no-certified-result notice.
- View Signals: one row per candidate, joined Metric labels.
- Validate Signals/early warning: replay unique candidate once, expose it to
  listed metrics for existing advice/grouping without duplicate replay.
- Saved-set dropdown: one option per candidate with complete `metrics` list.
- New position creation uses existing multi-metric reference shape, creating
  virtual per-metric frozen snapshots from one candidate for current link-key
  validation. Existing position files remain unchanged.

## Batch contract

Immutable batch request contains shared horizon/date/theme selection plus
normalized ticker tuple. Reject blank, invalid, duplicate, or >5 ticker input
before worker submission.

One atomic batch status sidecar carries overall state/progress plus ordered
per-ticker records: ticker, attempts, state, produced artifact paths, and error
text. Overall state is `done` after retries, even with terminal ticker failures;
UI shows each failure. Overall `failed` means unrecoverable request/worker or
shared-theme preflight failure.

No-theme: load/evaluate/persist one ticker before next. Theme: load/validate
VN-Index and build confirmation once; each ticker only aligns shared
confirmation as-of its dates. Per ticker, load/build indicators once, then
persist no-theme followed by VN-Index AND before next ticker begins.

After first pass, retry failed tickers in original order, once each. Preserve
first and final error status. Shared preflight sleeps five seconds inside worker
only, retries once, then stops before ticker work when retry fails.

Collect Signals uses `Tickers` input. Existing controls lock during queued,
running, or unreadable batch. Existing automatic polling displays each ticker
state and completed artifacts in request order; no manual refresh control.

## Tests and cleanup gate

Tests precede production code. Cover exact-combo grouping, three-metric group,
distinct winners, deterministic order, V2 persistence rejection/atomicity,
single candidate replay/display, current-position compatibility, ticker parser,
strict sequence, one theme load, ticker retry, terminal ticker failure,
five-second preflight retry/fatal stop, and page locking/status/results.

Only after V2 tests, compilation, whitespace, protected-boundary review, and
live health pass: inventory exact `schema_version: 1` artifact paths. Delete
only verified V1 files. Record deleted paths. Never delete positions, status
sidecars, DB data, directories, or generate live artifacts.

## Out of scope

- Certification formula or threshold changes.
- New metrics themselves.
- Parallel execution, V1 conversion/fallback, automatic real Backtests,
  position-history migration, SQL/schema/BIGINT/credential/Docker/dependency
  changes.
