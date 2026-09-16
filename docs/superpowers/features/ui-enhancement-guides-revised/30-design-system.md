# Design System Guide

## Purpose

Define a small, practical visual system for a compact and professional Streamlit application.

## Read This Document When

The current phase is `DESIGN_SYSTEM`.

## Depends On

- `./00-master-plan.md`
- `./01-core-constraints.md`
- Latest approved UI audit output
- Latest approved UI architecture output
- `./artifacts/00-decisions-and-approvals.md` if present

## Required Output

Generate a corresponding Markdown file containing the design-system plan. Choose a concise descriptive filename, save it under `./artifacts/`, and report the created path.

## Design Direction

- Modern B2B application
- Restrained and professional
- Compact but readable
- Clear hierarchy
- Low visual noise
- Consistent across pages

## Define

### Typography

Define roles for:

- page title;
- section title;
- body;
- secondary text;
- metadata;
- table text.

Use few sizes and weights.

### Spacing

Use a small scale, such as:

`4, 8, 12, 16, 24, 32`

Apply it consistently to gaps, padding, and section rhythm.

### Color

Define semantic roles:

- primary;
- neutral;
- success;
- warning;
- destructive;
- border;
- surface;
- background.

Use color to communicate meaning, not decoration.

### Controls

Define usage for:

- primary;
- secondary;
- ghost;
- destructive;
- icon-only.

### Containers

Define when to use:

- plain section;
- bordered group;
- card;
- expander;
- tabs;
- dialog.

Do not use cards as the default wrapper.

### Feedback

Define consistent patterns for:

- loading;
- empty;
- success;
- warning;
- error.

## Technology Use

- Prefer Streamlit theme configuration and native controls.
- Use `streamlit-shadcn-ui` only for an approved gap.
- Keep CSS centralized and limited to stable needs.
- Use one consistent icon family.

## Required Artifact Structure

1. Design principles
2. Tokens and semantic roles
3. Typography and spacing
4. Color and status usage
5. Control hierarchy
6. Container rules
7. Table, form, and feedback patterns
8. Accessibility requirements
9. Adoption sequence
10. Self-critique

## Acceptance Criteria

The system must be concise, reusable, accessible, and implementable within Streamlit without a frontend rewrite.
