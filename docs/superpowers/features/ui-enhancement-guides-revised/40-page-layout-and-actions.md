# Page Layout and Action Guide

## Purpose

Improve page composition, information density, and action clarity without changing workflows.

## Read This Document When

The current phase is `PAGE_ENHANCEMENT_PLAN`.

## Depends On

- `./00-master-plan.md`
- `./01-core-constraints.md`
- Latest approved UI audit output
- Latest approved UI architecture output
- Latest approved design-system output
- `./artifacts/00-decisions-and-approvals.md` if present

## Required Output

Generate a corresponding Markdown file containing the page-enhancement plan. Choose a concise descriptive filename, save it under `./artifacts/`, and report the created path.

## Page Composition

Each page should make these clear within a few seconds:

- page purpose;
- primary information;
- primary action;
- secondary actions;
- destructive actions.

Use a compact header with:

- title;
- optional one-line description;
- one primary action;
- necessary secondary actions.

Avoid oversized headers, repeated descriptions, and empty decorative space.

## Space Efficiency

- Group related content with hierarchy and whitespace before adding containers.
- Reduce nested containers, repeated labels, excess padding, and unnecessary scrolling.
- Use progressive disclosure for secondary details.
- Keep pages compact without reducing readability.

## Tables and Lists

- Show only useful columns.
- Align content deliberately.
- Use concise headers and compact readable rows.
- Move secondary details to an expandable view where appropriate.
- Avoid several large text buttons in each row.

## Filters and Forms

- Prefer compact filter bars, popovers, or collapsible sections.
- Use the sidebar for global or numerous filters.
- Group related fields.
- Use two columns only when the relationship is clear and narrow layouts remain usable.
- Keep validation and help text close to the relevant field.

## Icon Policy

Icon-only controls are suitable for familiar repeated actions such as:

- edit;
- delete;
- refresh;
- copy;
- duplicate;
- download;
- expand or collapse;
- more actions.

Icon-only controls require:

- one consistent icon set;
- tooltip;
- accessible label;
- adequate hit target;
- confirmation for destructive data loss.

Keep text labels for important or ambiguous business actions, such as:

- Create;
- Run;
- Save;
- Submit;
- Approve;
- Import.

## Required Artifact Structure

For each page include:

1. Current issues and evidence
2. Target information hierarchy
3. Proposed layout
4. Space-saving changes
5. Action and icon changes
6. Shared components
7. Dedicated components
8. Behavior-change risk
9. Validation method

Finish with priorities, dependencies, decisions required, and self-critique.

Do not implement in this phase.
