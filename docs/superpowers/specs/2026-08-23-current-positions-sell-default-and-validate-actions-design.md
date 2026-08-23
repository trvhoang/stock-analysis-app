# Current Positions SELL Default and Validate Actions Design

## Goal

Make a new OPEN position visibly have no SELL date, and make each available
Validate Signals result state its current position action alongside monitoring.

## New Position SELL date

- The `SELL date` date input in `New Position` initializes with `value=None`.
- The empty control represents Python `None`, not the literal text `"None"` or
  `"-"`.
- An OPEN submission continues to ignore SELL controls and persists
  `actual_sell_price: null` and `sell_date: null`.
- A CLOSED submission still requires a valid SELL price and SELL date.

## Position action

`validation_advice` owns one action for every available schema-4 rulebook
validation result. The renderer only displays it.

| Existing matching OPEN position | Condition | Action |
| --- | --- | --- |
| No | Current literal entry is BUY-eligible | `can BUY` |
| No | Current literal entry is not BUY-eligible | `expired BUY` |
| Yes | Latest close is at or below frozen stop-loss, at or above frozen take-profit, or any currently-required entry gate fails | `can SELL` |
| Yes | None of the SELL conditions holds | `HOLD` |

For OPEN positions, `can SELL` takes precedence over `HOLD`; BUY actions are
never emitted. SELL uses only the already-persisted risk snapshot and the
existing causal current replay. No new threshold, risk score, fee, or exit
strategy is introduced.

## Validate Signals UI

- On a Validate run, show a progress bar at zero before sequential processing.
  Update it once after every ticker, whether that ticker succeeded or failed.
  The final bar reports completion using the requested ticker count.
- Every visible result shows this top summary inside its existing expander:
  `Monitoring: {number}% — {classification} | {position-action}`.
- The existing diagnostic JSON remains available but is collapsed by default.
- Classification filtering retains its current local re-render behavior and
  does not rerun validation.

## Boundaries

No SQL, price scaling, artifact or job schema, saved-position schema,
validation batch ordering, risk formula, dependency, Docker, credential, or
Git change is permitted.

## Verification

Tests must cover the empty OPEN SELL-date default, each of the four action
states, frozen SL/TP and gate-failure SELL precedence, progress updates after
success and failure, summary copy, and collapsed JSON diagnostics.
