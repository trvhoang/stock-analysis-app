----
----
# FOCUS.md
# Updated: 2024-05-24

## Task
[feature] — Enhance Suggestion Page logic with technical scores and multi-criteria sorting.
Source: WIP from current-status.md

## Target Files
app/pages/suggestion_visualization.py  ← (Completed) Update filtering logic and implement 3-tier sorting.
app/commons/common_functions.py  ← (Completed) Verify technical trend/score consistency for batch processing.

## Out of Scope
app/common_queries.py  ← Boundaried file; do not modify.

## Task-Specific Rules
- Dual Filter: Statistical Trend must align with Technical Trend (e.g., both must be 'Up' for "Top 5 Up" categories).
- Sort Priority (Descending): 1. Primary Metric (Possibility or Delta), 2. Total Signals count, 3. Exchange Priority (HSX > HNX > UPCOM).
- BIGINT prices: Must be handled via the standard scale (Value / 1000) for display.

## Acceptance Criteria
- [x] "Top 5" categories only include tickers where statistical and technical trends match.
- [x] Sorting logic correctly implements the descending hierarchy (Metric -> Signals -> Exchange).
- [x] Technical scores and trends are accurately accounted for in the suggestion generation.

## Skill to Load
@ai-skills/skill-analyze-wip.md → Session start — WIP analysis

## Stopping Point
Last completed: Implemented Dual Filter (Stat + Tech trend alignment) and 3-tier descending sort for the Suggestion Page.
Next action: Monitor performance and user feedback on suggestion quality.
Blocker: None
----
----
