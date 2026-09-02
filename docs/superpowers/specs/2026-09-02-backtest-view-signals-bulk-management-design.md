# Backtest View Signals — Filtering and Bulk Candidate Management

**Status:** Implemented and verified in Docker (2026-09-02).

## Purpose

Make the Backtest **View Signals** tab usable for reviewing several tickers and
removing unwanted saved candidates without weakening schema-5 artifact,
position-history, or evidence rules.

## Scope

Only the View Signals projection and the schema-5 candidate-removal boundary
change. Collect, Validate, Current Positions, rulebook evaluation, source
fingerprints, and artifact schema remain unchanged.

## View controls

- **Ticker** is one text field. It accepts exact ticker codes separated by
  commas and/or whitespace, normalizes to uppercase, removes duplicates, and
  filters by membership. Blank means every catalog ticker. It is a view filter,
  so it has no 15-ticker batch limit.
- **Horizon** remains `Both`, `Swing`, or `Mid-term`.
- **Columns** is a multi-select display filter. Default visible data columns
  are `No`, `Select`, `Ticker`, `Horizon`, `Train-test`, `n`, `Win rate %`,
  `Profit %`, and `Sharpe`. `Evidence` and `Theme` are available but hidden by
  default. `No`, `Select`, and `Ticker` remain fixed so selection is legible.

## Table and selection

- `No` is the first column and is the 1-based ordinal of the currently visible
  filtered rows. It is display-only and is never an identity.
- `Select` is the second column. Every row begins unchecked.
- The `Select` header control selects or deselects all currently visible rows.
- A selected row is identified only by `(ticker, horizon, rulebook_id)`.
- Selection is cleared after a successful removal, a blocked removal, or any
  catalog refresh. It is therefore impossible to remove a hidden prior-filter
  selection accidentally.
- A compact native `🗑️` remove button is placed beside **Select all visible**.
  It is disabled when `N` is zero and its tooltip is exactly
  **Remove selected signals (N)**.

## Removal contract

1. The UI sends selected immutable candidate identities to one domain helper;
   it never edits JSON directly.
2. The helper fresh-loads and validates every affected schema-5 artifact.
3. Before any write, it checks every selection against saved OPEN and CLOSED
   position references. If any selected candidate is referenced, the complete
   request is blocked without changing an artifact. The UI lists the protected
   ticker, horizon, and rulebook ID.
4. Otherwise, each selected candidate is removed from its artifact's full
   `candidates` collection, not merely hidden from the current Top 3 view.
5. If candidates remain, the helper recomputes `top_rulebook_ids` with the
   existing immutable training ranking (win rate, profit percentage, Sharpe,
   lexical ID), so the next candidate may become visible.
6. If no candidates remain, the helper writes a valid schema-5 `empty`
   document preserving its source/evidence/split metadata and using rejection
   reason `All saved candidates were removed by user.` A later Collect run can
   replace it normally.
7. Every artifact rewrite is atomic through the existing persistence path.
   Invalid artifacts, stale selected IDs, and filesystem errors result in no
   partial write and a user-visible error.

## Error and safety behavior

- Unknown ticker filter tokens simply yield no matching rows; they never query
  or create data.
- A position-referenced candidate blocks the entire bulk request, avoiding a
  surprising partial deletion.
- Evidence eligibility is not changed by removal. A candidate that remains
  displayable but evidence-ineligible remains blocked from BUY eligibility.
- No artifact file is deleted. The final-candidate case is an explicit,
  regeneratable `empty` artifact.

## Tests

- Pure ticker filter parses comma/space values, normalizes case, deduplicates,
  and uses exact membership.
- Projection gives visible rows 1-based `No` values and defaults to Evidence /
  Theme hidden.
- UI selection header affects only visible rows; zero selection disables the
  removal action.
- Domain removal preserves nonselected candidates, reranks Top 3, converts the
  final candidate to valid `empty`, and is atomic on stale/invalid input.
- Any OPEN or CLOSED saved-position reference blocks every selected removal and
  reports each protected identity.

## Non-goals

- No rulebook recalculation, ranking-threshold change, artifact schema change,
  position deletion, legacy artifact migration, or automatic trade action.
- No custom HTML component or new dependency. The view uses native Streamlit
  controls and the existing scrollable table pattern.
