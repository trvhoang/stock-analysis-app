# UI Architecture and Resource Guide

## Purpose

Define maintainable UI boundaries and classify resources as shared or feature-specific.

## Read This Document When

The current phase is `UI_ARCHITECTURE`.

## Depends On

- `./00-master-plan.md`
- `./01-core-constraints.md`
- Latest approved UI audit output referenced by the master plan or decision record
- `./artifacts/00-decisions-and-approvals.md` if present

## Required Output

Generate a corresponding Markdown file containing the UI architecture and resource plan. Choose a concise descriptive filename, save it under `./artifacts/`, and report the created path.

## Shared Resources

A resource may be shared when it has a stable purpose and real reuse across pages.

Typical shared candidates:

- theme and design tokens;
- centralized CSS;
- app shell and page header;
- section header and action toolbar;
- icon mapping;
- status badge;
- common feedback states;
- confirmation pattern;
- reusable table, list, and form primitives;
- low-level layout helpers.

## Dedicated Resources

Keep a resource inside its feature when it contains:

- domain-specific fields or actions;
- workflow-specific state;
- page-only filters;
- specialized tables or forms;
- unique visualizations;
- feature-specific interaction logic.

## Boundary Rules

- Do not share code based only on visual similarity.
- Do not move domain logic into shared UI modules.
- Avoid a monolithic `common.py`.
- Avoid highly configurable components with many unrelated options.
- Keep ownership and intended reuse clear.
- Prefer composition over broad abstraction.

## Structure Direction

Adapt to the repository; do not force a new tree without evidence.

A possible structure is:

```text
ui/
  theme/
  layout/
  components/
  tables/
  forms/
  icons/

features/
  <feature>/
    page.py
    components.py
    forms.py
    tables.py
```

## Required Artifact Structure

1. Current UI structure summary
2. Shared-resource proposal
3. Dedicated-resource boundaries
4. Proposed folder and ownership model
5. Components to consolidate, keep local, or retire
6. Dependency and migration risks
7. Recommended sequence
8. Self-critique

For each proposed shared component, include purpose, consumers, API boundary, and reason for sharing.

## Acceptance Criteria

The architecture should:

- reduce duplication without hiding domain behavior;
- keep feature ownership clear;
- minimize CSS and component coupling;
- support incremental migration;
- remain understandable to Python and Streamlit engineers.

Do not implement restructuring in this phase.
