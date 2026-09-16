# Core Constraints

## Purpose

Define rules that apply to every UI enhancement phase.

## Product and Behavior

- Preserve business logic, data behavior, backend contracts, persisted formats, and existing workflows.
- Do not silently fix or reinterpret current behavior.
- Separate UI improvements from product-behavior changes.
- Report any required behavior change as `REQUIRES_DECISION`.

## Technical Boundaries

- Keep Streamlit as the application framework.
- Do not propose a React, Next.js, or other frontend rewrite.
- Prefer native Streamlit layout, theming, and controls.
- Use `streamlit-shadcn-ui` only when it solves a verified usability or consistency problem.
- Keep custom CSS minimal, centralized, and maintainable.
- Avoid fragile selectors that depend on undocumented Streamlit DOM details.
- Do not add unnecessary dependencies or heavy assets.

## Code Quality

- Keep changes small, focused, and reversible.
- Avoid unrelated refactoring.
- Keep business and data-access logic outside shared UI helpers.
- Prefer explicit components over generic components with many flags.
- Reuse only stable patterns with real cross-page value.

## User Experience

- Preserve keyboard usability, focus visibility, readable contrast, and accessible labels.
- Keep important business actions clear and discoverable.
- Do not trade comprehension for visual compactness.
- Use consistent feedback for loading, success, warning, empty, and error states.

## Evidence

Important findings and recommendations must reference repository evidence such as:

- file path;
- function or component;
- current interaction;
- screenshot or observed behavior;
- existing test where relevant.

Use `CONFIRMED`, `INFERRED`, `UNKNOWN`, or `REQUIRES_DECISION`.

## Change Control

- Do not edit code during audit or planning phases.
- Do not implement an unapproved plan.
- Stop when a requested change would violate these constraints.
