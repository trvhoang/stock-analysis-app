# Validate Signals signal date and win-rate design

## Goal

Show one causal signal date and preferred-treatment training/test win rates in
each available Validate Signals result. Preserve the same signal date in a
saved-signal position without replacing the user's actual Buy date.

## Source of truth

`early_warning._current_rulebook_facts()` already owns the calendar-filtered,
causal replay frame. It will derive `signal_date` from the last **observed
false-to-true** entry edge of the selected rulebook treatment. A missing edge
is `None`; the UI renders it as `—`. This is intentionally distinct from the
latest replay `as_of_date` and from a manual position's `buy_date`.

## Flow

1. Replay adds `signal_date` to `current` without recalculating indicators or
   changing entry eligibility.
2. `validate_saved_signals()` exposes that date on each result and obtains the
   preferred treatment's `training.win_rate` and `test.win_rate` from the
   immutable candidate already loaded for the replay.
3. Validate Signals renders exactly:
   `Monitoring: A% - classification | position action | signal date: DD/MM/YYYY | win rate training / test: X% / Y%`.
   A missing date or metric renders `—`; numeric win rates retain their stored
   precision rather than creating a new ranking or metric.
4. A saved-signal New Position displays the same read-only date and saves it
   as `entry_context.signal_date`; Buy date remains manual actual execution
   history.
5. Signal-backed position T+3 timing reads `signal_date`. Existing position
   histories lack that optional field, so they safely retain the legacy
   `as_of_date` fallback. No position migration occurs.

## Non-goals

- No artifact schema change or artifact rewrite.
- No change to current `can BUY` eligibility, selected gates, rulebook ranking,
  evidence eligibility, or risk formula beyond choosing the corrected saved
  timing date.
- No database, dependency, Docker, price-scaling, or Git change.

## Verification

Tests must cover observed-edge date derivation, preferred treatment metrics,
UI formatting, saved-context persistence, T+3 use of new date, and legacy
`as_of_date` fallback. Focused Backtest tests then run in Docker.
