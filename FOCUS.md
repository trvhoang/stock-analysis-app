----
----
# FOCUS.md
# Updated: 2026-08-01

## Task
[enhancement] - Add collapse/expand icon for Analyze-page export form.
Source: WIP from current-status.md

## Target Files
app/pages/analyze_visualization.py - Export form collapse/expand control.
tests/ - Tests for export form visibility state and existing export behavior.

## Out of Scope
app/common_queries.py - Boundaried file; do not modify.
Price storage and ingestion scaling - Preserve BIGINT values stored as price x 1000.
Export query, validation, CSV transformation, and download behavior - Already complete; do not change.
Portfolio, Suggestion, Technical Analyze, and API export flows - Not requested.

## Task-Specific Rules
- Keep export form hidden by default on initial Analyze-page render.
- Use an icon control to toggle export form collapse/expand state.
- Preserve existing export validation, query parameters, BIGINT scaling, percentage change, filename, and download behavior.
- Use existing dependencies and patterns; add no new dependency.

## Acceptance Criteria
- [x] Icon control appears with the Analyze-page export form.
- [x] Icon toggles form between expanded and collapsed states.
- [x] Export form remains hidden until the Export button is clicked.
- [x] Existing export validation and download flow remain unchanged.
- [x] Tests cover native collapsible-container configuration; Streamlit handles expanded/collapsed interaction.

## Skill to Load
`ai-skills/skill-implementation-review.md` after implementation.

## Stopping Point
Last completed: Added native collapse/expand icon to Analyze-page export form; 19 tests pass.
Next action: Await next prioritized task.
----
----
