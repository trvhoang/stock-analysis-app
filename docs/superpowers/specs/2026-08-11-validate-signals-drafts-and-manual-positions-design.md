# Validate Signals Drafts and Manual Positions Design

Date: 2026-08-11

## Goal

Make Validate Signals summaries actionable through a selected-row trade draft,
and let Current Positions create both signal-backed and P&L-only manual
positions. Preserve manual trading, long-only behavior, raw BIGINT storage,
and existing saved positions.

## Constraints

- No automatic BUY, SELL, close, job submission, re-certification, artifact
  rewrite, database write, dependency, Docker, protected-boundary, or commit
  change.
- Validate Signals gates remain suggestions: a BUY draft requires current BUY
  eligibility and no matching OPEN position; a SELL draft requires the
  selected matching OPEN position and `monitor.sell_allowed`.
- Current Positions direct creation bypasses those suggestion gates. It may
  create either OPEN or CLOSED records, including saved-set records.
- Existing per-ticker/theme/metric JSON position histories remain valid and
  retain their current edit/close behavior. No automatic migration or rewrite
  is allowed.

## Root-Cause Finding: Match Level

Live VCB replay proved the observed zero is intentional current behavior, not
a score-calculation failure. No-theme replay had score `75`, threshold `60`,
and match `100`. Themed replay had the same score and threshold but match `0`
because `validation_advice.match_level()` returns zero before comparing scores
when VN-Index is not confirmed.

New contract separates these concepts:

- Match level is always the capped score similarity:
  `min(100, current_score / BUY_threshold * 100)`.
- Theme eligibility remains a separate displayed field.
- Theme eligibility still blocks BUY eligibility and advice/actions. A themed
  set can therefore be `100%`, `Closely match`, `Theme eligible: No`, and
  `Observe`.

## Validate Signals Summary

### Display

- No theme remains first, VN-Index AND second.
- `Trade: Signal date` renders date only: `YYYY-MM-DD`.
- Price displays and input labels retain `k` scaling but remove `VND` text.
  Raw stored values remain unchanged.
- `Strategy: Indicators` displays leaf indicator names only, such as
  `MA cross, RSI, Alligator, OBV`; it never displays dimension labels such as
  momentum, trend direction, or volume.
- Summary-column controls move into a collapsed `Summary columns` expander
  containing one checkbox per field. They remain session-only.
- `Backtest: Date range` is available but hidden by default. Existing default
  fields otherwise remain visible unless the user unchecks them.

### Grouping and Selection

- Metric rows are grouped only when every non-Metric displayed value and
  action state are identical. `Identity: Metric` becomes a joined list of all
  grouped metrics.
- Streamlit 1.32 `st.dataframe` has no row-selection API. The summary uses
  `st.data_editor` with a non-persistent `Select` checkbox column while all
  summary data columns stay non-editable.
- Exactly one row may be selected. `Create trade` is disabled or reports a
  clear validation error for zero/multiple selections.
- `Create trade` derives BUY or SELL from the selected row's action state,
  then writes only one session draft. It never persists a position.
- A pending draft blocks another draft until user completes or cancels it.

## Draft Contract

### BUY Draft from Validate Signals

- Available only for an eligible set without a matching OPEN position.
- Captures immutable ticker, theme, linked metric list, certified-set snapshot,
  replay context, current replay as-of date, and frozen risk inputs.
- Current Positions completes the draft. BUY date remains locked to validation
  as-of date, as previously approved.

### SELL Draft from Validate Signals

- Available only for the selected set's matching OPEN position when its
  monitor permits SELL.
- Captures immutable selected-position identity. Current Positions completes
  it by recording the manual SELL price and date against that exact OPEN
  record.

## Position Model

### New Generic History

New records use one generic per-ticker position history. This is separate from
legacy per-theme/per-metric histories, which are read through an adapter.
This avoids rewriting valid user files while supporting no-signal records and
one position linked to several metrics.

Every new record has immutable identity, ticker, status, actual BUY/SELL data,
quantity, buy/sell dates, creation/close timestamps, and creation source.

### Signal-Backed Record

- Optional saved-set reference is immutable and contains its theme, all linked
  metrics, certified snapshot, and replay identity.
- Creation replays that saved set read-only at current as-of date and freezes
  current ATR, SL, TP, and max-hold values. This remains true even if user
  enters an older BUY date.
- One OPEN record per saved set is allowed across legacy and generic histories.
- Its monitor remains enabled. Direct Current Positions creation may still
  create it OPEN or CLOSED without Validate gate requirements.

### P&L-Only Record

- Saved-set reference, risk snapshot, and monitor are absent.
- Several P&L-only OPEN records may coexist for one ticker.
- User may create OPEN with no SELL price/date, or CLOSED with both values.
  Saving exactly one SELL value is rejected.
- P&L uses current latest close while OPEN and actual SELL while CLOSED.
  Quantity is optional positive whole shares; absent quantity means per-share
  absolute P&L. Fees/taxes remain excluded.
- Hold time counts completed ticker trading sessions after BUY through the
  latest ticker session on or before SELL date (CLOSED) or current as-of date
  (OPEN). BUY/SELL dates accept any calendar date.
- For a signal-backed manual BUY on a non-trading calendar date, native monitor
  timing starts at the first ticker database session on or after BUY date. The
  database OHLC/volume rows are the sole trading-calendar source.
- Manual close is always allowed.

## Current Positions UI

- Add `Add new position` with its own required Ticker field; the existing
  ticker list filter remains filter-only.
- New-position form defaults saved set to `-`. Selecting one shows available
  saved signal sets for that ticker and applies the signal-backed contract;
  leaving `-` applies P&L-only contract.
- Form accepts BUY price, BUY date, optional Volume, optional SELL price and
  SELL date. It rejects incomplete SELL pairs.
- Existing list keeps OPEN default filtering, oldest-open ordering, latest
  OPEN price/P&L, direct price/volume editing, and no automatic closure.
- Signal association is immutable after creation. To use another set, user
  creates another position.

## Compatibility and Read Model

- Overview combines legacy and generic records without mutating either.
- Validation maps a generic signal-backed OPEN record to every metric in its
  immutable linked-metric list. This keeps grouped summary action state exact.
- Legacy records retain their original one-metric behavior. No records are
  merged or rewritten.
- Duplicate OPEN saved-set detection checks both sources before creating a new
  generic signal-backed record.

## Verification Requirements

- Root-cause regression: unconfirmed theme retains score-based match level but
  has ineligible Observe advice/actions.
- Summary tests: leaf indicator formatting, date-only signal dates, no `VND`,
  hidden Date range, collapsed checkbox selector, exact-one selection, grouped
  metrics, and differing action states preventing grouping.
- Draft tests: BUY/SELL gate enforcement, immutable payload, cancel/complete,
  and pending-draft block.
- Position-store tests: legacy compatibility, generic signal/no-signal records,
  direct OPEN/CLOSED creation, incomplete SELL rejection, multi-metric link,
  one OPEN saved-set invariant, unlimited no-signal OPEN records, immutable
  signal association, and frozen current-as-of risk snapshot.
- Overview/monitor tests: combined legacy/generic records, raw-price P&L,
  calendar-date session counting, direct CLOSED P&L, and P&L-only manual close.
- Final Docker gate: full package-named Backtest suite, compile, scoped
  whitespace/protected-boundary check, and read-only live replay/refresh.
