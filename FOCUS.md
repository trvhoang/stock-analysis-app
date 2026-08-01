----
----
# FOCUS.md
# Updated: 2026-08-01

## Task
[enhancement] - Add optional OHLC and trading-volume export fields.
Source: WIP from current-status.md

## Target Files
app/pages/analyze_visualization.py - Export form checkbox and export-column handling.
tests/ - Tests for optional OHLC/volume columns and preserved export options.

## Out of Scope
app/common_queries.py - Boundaried file; do not modify.
Price storage and ingestion scaling - Preserve BIGINT values stored as price x 1000.
Export form required state - Keep ticker, export time range, and export time unit required.
Percentage change - Keep optional and unchanged.
Portfolio, Suggestion, Technical Analyze, and API export flows - Not requested.

## Task-Specific Rules
- Add one optional checkbox for full OHLC prices and trading volume.
- Keep required fields: ticker, export time range, and export time unit.
- Keep percentage change optional.
- Include OHLC and volume only when checkbox selected; preserve current default columns otherwise.
- Keep optional OHLC values in original BIGINT storage units; do not divide them by 1000.
- Preserve existing default close-price export scaling by dividing close by 1000.
- Preserve export form collapse/expand behavior, validation, query range, filename, and download flow.
- Use existing dependencies and patterns; add no new dependency.

## Acceptance Criteria
- [x] Optional checkbox appears in the export form.
- [x] Default export columns remain ticker, trading date, close price, and optional percentage change.
- [x] Checkbox adds open, high, low, close, and trading volume columns.
- [x] Optional OHLC values remain raw/original BIGINT storage values.
- [x] Required fields remain required; percentage change remains optional.
- [x] Existing collapse/expand, validation, query, filename, and download behavior remains unchanged.
- [x] Tests cover both checkbox states and output scaling/columns.

## Skill to Load
`ai-skills/skill-implementation-review.md` after implementation.

## Stopping Point
Last completed: Added optional full OHLC and trading-volume export fields; 20 tests pass.
Next action: Await next prioritized task.
----
----
