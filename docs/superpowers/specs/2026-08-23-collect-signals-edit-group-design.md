# Collect Signals Edit Group Design

## Goal

Let a user edit a selected named Collect Group safely before running any
backtest.

## Layout and visibility

- Collect row 1 is `Tickers`, `Group`, `Edit Group`.
- Collect row 2 is `Horizon`, `Range`, `Run Backtest`.
- `Edit Group` is a native popover, hidden until a defined named Group is
  selected. It is absent for `N/A` and `New group…`.
- Existing-group Tickers remains disabled and shows current members.

## Editing contract

- The popover begins with the selected Group's current uppercase sorted
  members. Each has a Remove control.
- A user can add a normalized ticker through the input; duplicates are ignored.
- Changes remain popover-local until `Save Group`.
- `Save Group` atomically replaces the named Group's entire membership using
  the existing recoverable journal mechanism. Empty Groups are valid and
  remain selectable.
- After save, the Collect row refreshes to show the saved member list. No
  backtest, artifact, or job is started.

## Boundaries

Only Group JSON membership changes. No price data, SQL, artifact/job schema,
position, rulebook, dependency, Docker, credential, or Git behavior changes.
