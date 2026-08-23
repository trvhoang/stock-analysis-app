# Validate Signals Match-Classification Filter Design

Date: 2026-08-14
Status: user-confirmed

## Goal

Let users narrow already-rendered Validate Signals results by current match
classification without performing another validation run.

## UI Contract

- Render `Match classification` above stored validation results.
- Use a multi-select with `Observe`, `Nearly match`, and `Closely match`.
- All three classifications are selected on first render in a browser session.
- The selected classes filter signal-summary rows and metric detail panels.
- If no class is selected, show `Select classification` and render no result
  rows or metric detail panels.
- The control is local display state. It does not alter the validation request,
  rerun the validator, change artifacts, positions, price handling, or trading
  advice/risk rules.

## Data Contract

The filter uses existing validation values only:

| Stored value | UI label |
| --- | --- |
| `observe` | Observe |
| `nearly_match` | Nearly match |
| `closely_match` | Closely match |

Only available metric results have a match classification. Artifact/variant
availability errors do not become a filter option.

## Boundaries

- No database, SQL, artifact, persistence, replay, position, indicator, or
  BIGINT price conversion change.
- No dependency or Docker change.
- Every Streamlit widget key remains unique across repeated ticker/theme
  results.

## Validation

AppTests prove default options, one-class filtering of summaries/details, and
the empty-selection message. Focused Backtest tests and compilation verify the
existing page remains intact.
