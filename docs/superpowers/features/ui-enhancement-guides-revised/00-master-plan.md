# UI Enhancement Master Plan

## Purpose

Guide Codex through a safe, evidence-based UI improvement process for the existing Python and Streamlit application.

This file is the entry point. Read it first, then load only the documents required for the current phase.

## Technical Context

- Python
- Streamlit
- Streamlit native layout and theming
- `streamlit-shadcn-ui` only when it provides clear value
- Minimal, centralized custom CSS
- Reusable Python UI helpers

## Current State

- **Current phase:** `UI_AUDIT`
- **Implementation approved:** `No`
- **Approved implementation scope:** `None`
- **Latest approved artifact:** `None`

Do not implement code unless the current phase is `IMPLEMENTATION` and the approved scope is recorded in `./artifacts/00-decisions-and-approvals.md`.

## Phase Routing

| Phase | Read | Required prior artifacts | Produce |
|---|---|---|---|
| `UI_AUDIT` | `./01-core-constraints.md`, `./10-ui-audit.md` | Decision record if present | Corresponding UI audit Markdown output |
| `UI_ARCHITECTURE` | `./01-core-constraints.md`, `./20-ui-architecture-and-resources.md` | Latest approved UI audit output and decisions | Corresponding UI architecture Markdown output |
| `DESIGN_SYSTEM` | `./01-core-constraints.md`, `./30-design-system.md` | Latest approved UI audit and architecture outputs, plus decisions | Corresponding design-system Markdown output |
| `PAGE_ENHANCEMENT_PLAN` | `./01-core-constraints.md`, `./40-page-layout-and-actions.md` | Latest approved audit, architecture, and design-system outputs, plus decisions | Corresponding page-enhancement Markdown output |
| `IMPLEMENTATION` | `./01-core-constraints.md`, `./50-implementation-and-validation.md` | Latest approved plan outputs and decisions | Corresponding implementation-log Markdown output |

Each phase must generate one corresponding Markdown output file. Choose a concise descriptive filename, save it under `./artifacts/`, and report the actual path. Do not rely on a predefined output filename. After approval, record the actual path in the current state or decision record so later phases can locate it.

## Startup Procedure

1. Read this file.
2. Identify the current phase.
3. Read only the required files listed for that phase.
4. Read required prior artifacts if they exist.
5. Inspect repository files needed to complete the phase.
6. Report:
   - current phase;
   - documents read;
   - missing inputs;
   - instruction conflicts;
   - whether code changes are allowed.
7. Produce only the output required for the current phase.

Do not read all linked guides preemptively.

## Evidence and Uncertainty

Use these labels:

- `CONFIRMED`
- `INFERRED`
- `UNKNOWN`
- `REQUIRES_DECISION`

Do not convert missing evidence into an assumption.

## Instruction Priority

1. Latest explicit user instruction
2. Approved decisions in `./artifacts/00-decisions-and-approvals.md`
3. `./01-core-constraints.md`
4. Current phase guide
5. Approved artifacts from earlier phases
6. Repository evidence
7. General design guidance

If two instructions conflict, stop and report `INSTRUCTION_CONFLICT`.

## Approval Gates

- Audit and planning phases must not modify code.
- Each plan must be reviewed before the next phase.
- Implementation must be limited to the explicitly approved scope.
- A behavior-changing proposal must be recorded as a decision before implementation.
