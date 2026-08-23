# Current Positions New Position Section Design

**Date:** 2026-08-22
**Status:** Implemented and verified

## Layout

Replace native New Position popover with collapsed `New Position` expander at
top of Current Positions. Keep live controls so Saved signal set refreshes from
Ticker. Field order:

1. Ticker, State, Saved signal set
2. BUY price, BUY date, Volume, SELL price, SELL date
3. Add Position

Price labels omit `(k)`; values remain k-VND UI inputs and preserve existing
raw-BIGINT conversion. Below section: existing filters, then existing
expandable BUY/SELL groups. No flat-table conversion.

## Saved signal set refresh and safety

When the user commits a Ticker value, uppercase it and run one fresh
`validate_saved_signals()` replay for that ticker. Keep this result in
New-Position-only session state; it must not overwrite the Validate Signals
tab's batch result. Reset the selected saved-set control to `Manual P&L only`
before rendering the new ticker's options.

Only current `buy_eligible` schema-4 results are selectable as signal-backed
positions. Existing saved artifacts that are audit-ineligible, already open,
or otherwise not BUY-eligible remain blocked. If artifacts exist but no option
is eligible, retain the manual-only choice and show the concise blocking reason
to the user. Validation failures likewise retain manual-only selection and
show the replay error. This preserves the V3 rule that audit-ineligible
rulebooks are display-only and cannot create a signal-backed BUY position.

## Boundaries

No schema, persistence, validation, price scaling, risk, SQL, signal, or
dependency change. Widget keys and live saved-set behavior remain.
