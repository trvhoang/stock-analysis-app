# Validate Positions Risk and Trade-row Design

## Status

Phase A is implemented and verified on 2026-08-22 after the schema-4 V3
replacement. Its deferred Phase B section is superseded by the approved
`2026-08-22-validate-positions-risk-phase-b-design.md`; this document remains
authoritative for Phase A only.

## Goal

Add a fourth Backtest Lab tab, **Validate Positions**, for an after-session
assessment of selected OPEN positions. It produces a current risk suggestion
for the position's BUY trade. Redesign Current Positions so every position is
one collapsible group with a BUY row and a SELL row, while retaining all
existing position controls for both pre-existing and newly created positions.

This feature is informational and manual only. It does not support real-time
data, submit orders, create automatic SELLs, or change the existing ATR
stop-loss/take-profit/timeout exit contract.

## Non-negotiable Operating Contract

- All assessments use persisted database data after a trading session has
  finished; no intraday or real-time market source is added.
- A validation run uses the latest completed database bar available to the
  application. Its result area shows one informative common
  `As of: DD/MM/YYYY` label.
- The as-of date is not persisted in a position's risk value and is not shown
  in Current Positions or elsewhere.
- One run accepts one through five selected OPEN positions, processes them
  sequentially, and continues after an individual failure. The result reports
  each failed position separately.
- The risk result is advice only. It never opens, closes, or edits a trade.

## V3-only Boundary

- A saved-set position is eligible for signal-backed risk evaluation only when
  its frozen reference is schema version 4. Its assessment uses that saved
  rulebook and its single saved horizon.
- A pre-V3/V2 saved-set position remains historical P&L/manual-management
  data. Validate Positions neither reads its legacy artifact nor calculates a
  risk suggestion from it; its BUY risk remains `N/A`.
- A position without a saved signal set is not a V2 fallback. It evaluates
  fresh current V3 Backtest-owned indicators for **both** Swing and Mid-term.

## Phase A — UI Structure and Position Presentation

### Backtest Lab tabs

Backtest Lab has four tabs in this order:

1. Collect Signals
2. Validate Signals
3. Current Positions
4. Validate Positions

Phase A renders the new Validate Positions tab as an explicit unavailable
risk-model surface. It does not offer a fake Run action or write a risk value
before the formula is approved.

`View Signals` remains a read-only native popover inside both Collect Signals
and Validate Signals. It is not a fifth tab and cannot submit a job or alter
validation state.

### Current Positions groups

Keep the current ticker/state filters, sorting, refresh, New Position,
selection, Select all visible, editable fields, and permanent
delete-with-confirmation behavior. Apply the group layout consistently to
existing and newly created positions.

Each visible logical position is one independently collapsible group. Its
existing selection identity remains the position ID, so bulk deletion and
selection operate on logical positions, never individual BUY/SELL rows.
Inside the group, render exactly two labelled rows:

| Row | OPEN position | CLOSED position |
|---|---|---|
| BUY | Existing BUY identity, price, date, quantity, saved-set identity, P&L context, and `Risk Suggestion`. Until a Phase B value exists, render `N/A`. | Same BUY information. A non-`N/A` Risk Suggestion is rendered struck through because the position has closed. `N/A` is not struck through. |
| SELL | Render available SELL suggestion fields (projected exit, holding/time, SL, TP) and actual SELL fields as `-`. If no suggestion is available, both suggestion and actual SELL fields show `-`. | Render available SELL suggestion fields and the actual SELL price/date. A missing suggestion remains `-`; actual SELL values remain the stored trade facts. |

The layout changes presentation, not financial meaning: saved signal set stays
read-only; ticker changes still require delete-and-create; editing prices,
dates, volume, and state preserves the existing contracts. The existing manual
close, explicit confirmation, and permanent delete behavior remain unchanged.
The two rows are read-only. A group-local **Edit position** control opens the
existing editable fields for that one position and saves through its immutable
locator. This avoids Streamlit 1.32's column-wide editing limitation while
keeping the user-facing edit capability inside the selected position group.

## Phase B — Risk Evaluation and Persistence

> Superseded historical boundary. Do not use this section to plan or implement
> Phase B; use `2026-08-22-validate-positions-risk-phase-b-design.md`.

Phase B is a separate future design and implementation plan. Its formula,
risk thresholds, full result table, and detailed interaction behavior are not
part of this approved phase.

The locked boundary for that future work is:

| Position type | Evaluation coverage | BUY Risk Suggestion display |
|---|---|---|
| OPEN V3 saved-set position | Its one saved-set horizon only | `<Horizon>: <percent>% - <risk level>` |
| OPEN position without a saved set | Both Swing and Mid-term | `Swing: <percent>% - <risk level>` and `Mid-term: <percent>% - <risk level>` on separate lines |
| Pre-V3/V2 saved-set historical position | No evaluation | `N/A` |

Risk levels will be `low`, `medium`, `high`, or `very`; the percent-to-level
mapping and risk formula are intentionally unchosen. The given display shape
is illustrative only, for example:

```text
Swing: 90% - very
Mid-term: 20% - low
```

Each successful validation replaces only that position BUY row's previous
risk suggestion. No risk-history series is retained. A later CLOSED position
keeps its last non-`N/A` risk text only as struck-through historical context.

The Phase B batch must reuse a loaded current frame for duplicate
ticker/horizon work within the same run, but must not alter its sequential
position processing, five-position cap, error isolation, raw-BIGINT data
rules, or V3-only artifact boundary.

## Required Future Acceptance Evidence

Before Phase B can be implemented, its dedicated design must define and test:

1. The deterministic risk formula and its exact Low/Medium/High/Very bands.
2. Required current inputs and the unavailable/invalid-data result for each
   position type.
3. The complete batch result table and all user-facing failure messages.
4. V3 saved-set horizon-only evaluation, no-signal two-horizon evaluation,
   V2 non-reading, overwrite-only persistence, and CLOSED strike-through
   rendering.
5. Sequential five-position cap, duplicate ticker/horizon frame reuse, and
   continue-on-error behavior.
6. Proof that all calculation uses raw DB values and latest completed bars,
   while UI price display uses the shared conversion only.

## Out of Scope

- Real-time or intraday position risk.
- A market-calendar or clock lock; users operate after session completion and
  the system reports the actual latest completed DB as-of date.
- V2 artifact replay, migration, conversion, or compatibility.
- Risk-result history, automatic SELL, order execution, fees, taxes, or
  changes to existing ATR risk levels and exit eligibility.
