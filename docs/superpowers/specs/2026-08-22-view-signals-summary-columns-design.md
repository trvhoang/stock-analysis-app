# View Signals Summary Columns Design

**Date:** 2026-08-22
**Status:** Approved design — implementation plan pending review

## Scope

Simplify the read-only View Signals table. This is a UI-only projection: it
does not change schema-4/V3 JSON, catalog fields, signal artifacts, rulebook
calculation, or position behavior.

## Visible table

Show these columns in this exact order:

```text
Ticker | Horizon | Theme | Train-test | n | Win rate % | Profit % | Sharpe
```

- `Theme` is `Included` for `background-theme`; otherwise `Excluded`.
- `Train-test` is `YES` only when preferred-treatment training and test metric
  blocks both exist; otherwise `NO`.
- `n`, `Win rate %`, `Profit %`, and `Sharpe` each show `train - test`, using
  the preferred-treatment values in that order.
- Missing metric values display `N/A`; no value is invented or rescaled.

Hide rulebook ID, selected gates, raw treatment payloads, evaluation label,
group metadata, and every other catalog field.

## Terminal results

View Signals no longer renders terminal results. Current schema-4/V3 terminal
JSON (`empty`, `failed`, `requires_regeneration`) stays unchanged on disk and
continues to support its existing job/artifact behavior. Invalid-artifact and
group-metadata warnings remain visible.

## Verification

Tests must prove exact output columns/order, Included/Excluded mapping,
YES/NO metric-block detection, `train - test` values, hidden raw fields, no
terminal dataframe/caption, and unchanged catalog JSON behavior.
