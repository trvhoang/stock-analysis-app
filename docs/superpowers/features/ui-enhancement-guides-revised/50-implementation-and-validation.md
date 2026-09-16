# Implementation and Validation Guide

## Purpose

Apply an approved UI plan in small, verifiable increments.

## Read This Document When

The current phase is `IMPLEMENTATION`.

## Depends On

- `./00-master-plan.md`
- `./01-core-constraints.md`
- `./artifacts/00-decisions-and-approvals.md`
- latest approved architecture, design-system, and page-plan outputs relevant to the scope

## Required Output

Generate a corresponding Markdown file containing the implementation and validation log. Choose a concise descriptive filename, save it under `./artifacts/`, and report the created path.

## Entry Conditions

Implementation may start only when:

- the master plan phase is `IMPLEMENTATION`;
- the scope is explicitly approved;
- required artifacts exist;
- open decisions affecting the scope are resolved.

## Implementation Cycle

For each approved batch:

1. State the approved scope.
2. List files expected to change.
3. Identify protected behavior and validation checks.
4. Implement the smallest coherent change.
5. Run relevant tests and application checks.
6. Review affected pages visually.
7. Record results, deviations, and remaining risks.
8. Stop before starting another unapproved batch.

## Change Rules

- Keep diffs focused and reversible.
- Avoid unrelated refactoring.
- Do not expand scope silently.
- Reuse only approved shared patterns.
- Preserve behavior and contracts.
- Stop when implementation requires a new product decision.

## Validation

Validate as applicable:

- existing automated tests;
- page load and navigation;
- create, edit, delete, and refresh flows;
- forms and validation;
- tables, filters, and dialogs;
- loading, empty, success, warning, and error states;
- keyboard access and focus visibility;
- normal and narrow-width layouts;
- absence of regressions in untouched workflows.

If visual verification is unavailable, report that limitation.

## Implementation Log

Record:

- approved batch;
- files changed;
- tests and checks run;
- visual findings;
- behavior verification;
- deviations from plan;
- unresolved risks;
- rollback notes;
- next approval required.

## Completion Criteria

A batch is complete only when:

- approved scope is implemented;
- checks pass or failures are documented;
- affected UI is visually reviewed;
- behavior remains preserved;
- the implementation log is updated.

Do not claim improvement based only on code changes. Evaluate against approved acceptance criteria.
