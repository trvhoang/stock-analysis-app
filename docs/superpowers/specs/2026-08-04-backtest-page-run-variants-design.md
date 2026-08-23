# Backtest Page Run Variants Design

## Goal

Let the Backtest page submit the requested one or two certified-signal
searches for one selected horizon without allowing inputs to change while any
submitted job is non-terminal.

## Approved User Flows

1. The Horizon control is a radio with `Swing` and `Mid-term` only. It has no
   default selection; clicking Run before choosing one shows a validation
   message and submits no work.
2. `INCLUDE_THEME_OPTION` is an unchecked checkbox. The page has no theme-mode
   selector.
3. With one selected horizon and the checkbox unchecked, submit exactly one
   no-theme run.
4. With one selected horizon and the checkbox checked, submit exactly two
   runs: no theme, then VN-Index background theme with the fixed `AND` rule.
5. The four supported configurations are Swing/Mid-term crossed with
   no-theme/VN-Index-AND. A single click never runs both horizons.
6. While any submitted job is queued or running, all request-defining controls
   and the Run button are disabled. They become usable only after every job is
   terminal and its success result or failure message is rendered.

## Chosen Architecture

The page will build a tuple of the existing immutable `BacktestConfig` values
and submit each through the existing `submit_backtest` contract. This retains
the proven one-config pipeline, separate overwrite-only files for each
`(ticker, theme_variant)` pair, and the existing spawned worker behavior. The
page will store the submitted job identifiers with their configuration so it
can poll and label each status/result independently.

No engine, persistence, SQL, BIGINT-storage, Docker, dependency, or commit
workflow changes are required. The engine-level `OR` capability remains
unchanged but is not exposed by this page.

## Error and Completion Semantics

- A missing horizon is a page validation error, not a queued job.
- A two-run request remains locked until both jobs are terminal.
- A failed job renders its persisted error; a successful sibling still renders
  its available artifact. After terminal statuses are rendered, controls are
  unlocked so the user can retry or start a new request.
- A new request replaces the displayed prior-request job list only when the
  user explicitly clicks Run after controls have unlocked.

## Test Evidence Required

- Unit tests prove the exact one- and two-config contracts and fixed `AND`
  theme mode.
- AppTest proves radio-without-default, unchecked theme checkbox, disabled
  controls during non-terminal status, and submit-only behavior.
- Focused Docker page/pipeline tests prove existing one-config behavior is not
  regressed, followed by the Backtest/Technical regression gate.

## Scope Boundaries

This is a Backtest-page orchestration enhancement only. It does not add
multi-ticker search, a both-horizons option, a new theme algorithm, batch
engine contracts, data-query changes, or changes to persisted signal schemas.
