# Validate Signals — Progressive Signal State

## Purpose

Validate a saved schema-5 candidate from its latest observed entry event to the
latest common completed native bar.  The state assesses present BUY freshness;
it never changes the candidate's historical metrics, rank, artifact, or
rulebook definition.

## Inputs and boundaries

- The assessment uses the existing calendar-aligned rulebook frame.
- It uses only the candidate's selected gates and the indicators which form
  those gates, plus price movement from the signal-bar close normalised by the
  signal-bar ATR.
- A background-theme candidate also uses its original theme eligibility.
- No unselected RSI, ADX, Stochastic, Alligator, or other indicator can change
  the state.
- Age is measured in completed native bars: daily VN-Index sessions for Swing
  and completed calendar-valid W-FRI bars for Mid-term.

## State machine

Precedence is `Invalidated`, `Fresh`, then age-weighted `On-going` or
`Weakening`.

| State | Conditions |
|---|---|
| Fresh | Latest observed false-to-true entry event is the latest native bar. |
| On-going, 1–3 bars | No adverse price fact and no selected-source deterioration. |
| On-going, 4–6 bars | Price remains at or above signal close and every persistent selected source is holding. |
| On-going, >6 bars | The two independent facts remain present: positive price continuation and selected-source support. |
| Weakening | An early adverse price/source fact, or the age-weighted continuation proof is insufficient. |
| Invalidated | A selected structural continuation fails, or a severe price loss (at least 1.5 signal ATR) is confirmed by selected-source deterioration. Age alone never invalidates. |

An adverse price fact is a loss of at least 0.5 signal ATR from the signal
close, or two latest declining closes with at least that drawdown from the
post-signal high.

## Gate-specific continuation

- `joint trend`: current joint ordering must pass. Two consecutive contractions
  in the minimum EMA/Alligator bullish spread are deterioration.
- ADX: it must remain at or above the selected rulebook minimum. Two
  consecutive ADX declines are deterioration.
- RSI upcross: it is a one-bar event; continuation requires RSI to remain at
  or above the original crossing level. Two consecutive RSI declines are
  deterioration.
- Volume: it is a breakout event. A lower later volume ratio is neutral, while
  a renewed current volume gate can support an older signal.
- Background theme: it must remain eligible when it formed the original
  treatment.

## BUY action and UI

`can BUY` now requires both current evidence eligibility and signal state
`Fresh` or `On-going`; `Weakening` and `Invalidated` become `expired BUY` with
the `signal_weakening` block reason. Existing OPEN-position SELL/HOLD logic is
unchanged. Validate Signals displays the state beside Monitoring and exposes
the causal facts in its already-collapsed JSON.

## Verification

Unit coverage proves Fresh, short and long On-going, early Weakening, hard
Invalidated, and an On-going consumed RSI event that remains BUY-eligible. A
live DPM CSV replay gives `Weakening`: event `2026-09-03`, age `2`, and price
change `-1.8151812105770395` signal ATR.
