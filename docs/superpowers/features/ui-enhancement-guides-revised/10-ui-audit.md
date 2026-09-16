# UI Audit Guide

## Purpose

Create an evidence-based view of the current UI before proposing architecture or design changes.

## Read This Document When

The current phase is `UI_AUDIT`.

## Depends On

- `./00-master-plan.md`
- `./01-core-constraints.md`

## Required Output

Generate a corresponding Markdown file containing the completed UI audit. Choose a concise descriptive filename, save it under `./artifacts/`, and report the created path.

## Audit Scope

Inspect:

- page hierarchy and navigation;
- layout containers and information hierarchy;
- headers, actions, forms, tables, lists, filters, tabs, dialogs, and sidebars;
- loading, empty, success, warning, and error states;
- theme, CSS, assets, icons, and UI helpers;
- repeated patterns and duplicated code;
- spacing, alignment, density, scrolling, and responsive behavior;
- accessibility and keyboard interaction.

## Findings

For each material issue, record:

| Field | Required content |
|---|---|
| Location | Page, file, function, or component |
| Evidence | What proves the issue |
| Issue | Clear description |
| User impact | Why it matters |
| Severity | `HIGH`, `MEDIUM`, or `LOW` |
| Scope | `SHARED`, `DEDICATED`, or `NO_CHANGE` |
| Confidence | Evidence label |
| Direction | Short recommendation, not implementation detail |

Avoid generic observations that are not tied to repository evidence.

## Required Artifact Structure

1. Executive summary
2. UI and navigation map
3. Evidence-based findings table
4. Repeated patterns and duplication
5. Accessibility and feedback-state gaps
6. Confirmed constraints
7. Unknowns and decisions required
8. Highest-impact opportunities
9. Self-critique

## Self-Critique

Check whether:

- a finding is based only on personal taste;
- a proposed direction could change behavior;
- another page uses the same pattern differently;
- the issue is local or systemic;
- missing runtime evidence should be marked `UNKNOWN`.

## Stop Conditions

Stop and request a decision when:

- current behavior is unclear;
- UI and business logic are tightly coupled;
- a recommendation requires a workflow change;
- required pages or repository files cannot be inspected.

Do not modify code or create a design system in this phase.
