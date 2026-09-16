# Backtest Validation Calendar and Trajectory Design

**Date:** 2026-09-03  
**Status:** Approved design; implementation pending

## Problem

Validate Signals currently reports monitoring from the percentage of a saved
candidate's selected gates that pass on the latest bar. It is not a ratio of
indicator value to threshold. This is nevertheless level-only monitoring: it
does not show whether a condition is improving or decaying, and it does not
retain the first bar on which a sustained entry mask became true.

For example, a declining ticker can remain `Closely Match` when the candidate
does not select the gates that would reject its decline. The existing
`literal_entry` value also means the entry mask is true on the latest bar; it
does not mean a new entry event occurred on that bar.

## Goals

1. Make VN-Index prints the sole canonical market-session calendar.
2. Investigate TCX from 2026-08-25 and every current saved schema-5 candidate
   without changing artifacts, jobs, positions, or database rows.
3. Measure whether entry-event age and causal trajectory evidence improve BUY
   quality, using training to select a fixed policy and untouched test data as
   evidence.
4. Make a failed chosen policy produce `expired BUY` for no position and
   `HOLD` for an OPEN position unless an existing SELL condition fires.
5. Preserve honest evidence labels and regenerate any canonical artifact whose
   historical entry semantics change.

## Non-Goals

- No external holiday API, maintained holiday list, or weekday-derived market
  calendar.
- No automated order, position mutation, or SELL caused solely by a declining
  trajectory.
- No alteration of raw BIGINT prices, source data, Backtest rulebook inputs,
  or the legacy Analyze/API technical snapshot.
- No claim that a missing VN-Index print proves a real exchange holiday. The
  product policy treats it as a non-session; diagnostic output makes that
  assumption visible.

## Canonical Session Policy

The existing schema-5 evidence code already does the desired core work:
expected sessions are the actual, bounded VN-Index row dates. Therefore:

- a weekday missing from VN-Index is an **assumed non-session**;
- it is excluded from ticker coverage and entry-age session counts;
- a ticker missing while VN-Index prints is a ticker data gap;
- a ticker row on a date without a valid VN-Index session is outside the
  canonical calendar: it is excluded before indicator calculation and is
  reported as a source anomaly rather than silently changing a rulebook;
- weekends never become sessions;
- the latest common completed bar remains the minimum latest source bar;
- Mid-term continues to aggregate only completed `W-FRI` bars.

Swing entry age is measured at `0`, `1`, `2`, `3`, and `5` canonical
VN-Index sessions. Mid-term entry age is measured at `0`, `1`, `2`, `3`, and
`5` completed `W-FRI` bars. The existing `W-FRI` period label remains the
calculation identity. When Friday is an assumed non-session, its weekly bar's
age anchor is the last actual VN-Index session in that completed week (for
example Thursday), never an artificial Friday date. A weekly bar may be used
only after its complete `W-FRI` period is available under the current
completed-bar clock.

The completed-bar clock is deliberately conservative. A Friday with no
VN-Index print is not guessed closed during that Friday. Its W-FRI bar becomes
available only once a later actual VN-Index session proves the period has
ended (normally the following Monday). The bar retains its W-FRI calculation
label but its age anchor remains that week's last actual VN-Index session.
This avoids treating an intraday/late-ingestion Friday as a holiday.

No second weekday/holiday calendar may be introduced. The implementation will
extract or expose this existing policy as one reusable evidence helper, then
apply it before every **Backtest** rulebook indicator frame: Collect Signals,
fresh Validate Signals replay, Position/Research callers that already receive
VN-Index history, and the read-only diagnostic. The unrelated Technical
Analysis snapshot is outside this Backtest rulebook contract. The calendar is
also used for entry-event age. A diagnostic will list every
absent weekday in the bounded VN-Index interval as `assumed_non_session`.
This preserves product policy while making an ingestion outage distinguishable
to an operator.

## Read-Only Investigation Contract

The diagnostic runner reads current schema-5 signal documents and raw ticker/
VN-Index history. It must not call the normal `check_current_situation()` path,
because that path can overwrite an artifact with `requires_regeneration` when
source evidence changes.

For each available Top-3 candidate, the runner builds the same causal
rulebook frame and selected-gate entry mask through the latest common completed
bar. It returns data only; persistence requires a separate, explicit later
request.

Each record contains:

- ticker, horizon, rulebook ID, selected gates, preferred treatment, and
  current evidence status;
- common-as-of date and current native bar date;
- current monitoring gate facts and existing classification;
- entry-mask history, `entry_event` history, latest entry-event date, and its
  age in canonical VN-Index sessions;
- trailing causal values for close, MA/Alligator state, RSI, ADX, volume gate,
  and selected gates; and
- diagnostic-only trajectory candidates and explicit reasons.

`entry_event` is strictly a causal false-to-true transition:

```text
entry_event[t] = entry_mask[t] AND NOT entry_mask[t - 1]
```

The first available valid mask bar is not an event unless a prior observed
false mask exists. An unknown prior state remains unknown/no event. This
prevents an already-true level gate from being relabeled as a new signal on
every bar.

TCX is a required detailed trace, from 2026-08-25 through the current common
bar. If its current artifact is unavailable, output a precise unavailable
record rather than inventing a conclusion. The wider audit processes all
current artifacts independently and retains per-ticker failures.

## What the Investigation Tests

The runner compares current behavior with candidate policies. It evaluates
entry-event age thresholds of `0`, `1`, `2`, `3`, and `5` canonical sessions.
It also evaluates causal trajectory candidates using only information through
each assessed bar:

- entry mask as level versus false-to-true entry event;
- recent close direction over candidate native-bar windows;
- current MA/Alligator joint trend state;
- RSI direction/upcross recency when RSI is relevant; and
- ADX threshold plus change as **trend-strength only**, never price direction
  by itself.

The predeclared trajectory candidates are:

- `A`: close declines over three native bars **and** MA/Alligator joint trend
  fails;
- `B`: `A` plus RSI is below its rulebook upcross level after an entry event,
  when the candidate selected RSI; and
- `C`: `A` plus ADX is below its horizon minimum and falling, when the
  candidate selected ADX.

ADX falling cannot alone prove a declining price, and rising ADX cannot alone
prove a rising price. Each candidate policy must therefore pair ADX evidence
with price/trend-direction evidence. A policy may not silently add an
unselected indicator as a live hard entry gate; if it does, it becomes a new
rulebook behavior and requires full historical regeneration.

For every historical assessment point, the diagnostic reports the policy's
decision without future bars. Threshold/policy choice uses only the frozen
training partition. The untouched historical test partition reports:

- candidates blocked and candidates retained;
- completed-trade count;
- gross win rate, gross profit percentage, Sharpe; and
- false-BUY removals and valid-BUY losses relative to current behavior.

No policy is adopted if test evidence is inadequate or materially worse. The
report must say `Exploratory — gross` and never call a result profitable,
tradable, or statistically certified.

## Chosen-Policy Runtime Semantics

After investigation and a separately approved fixed policy:

1. A new BUY is eligible only when the most recent observed entry event is at
   or inside the chosen horizon-native age window, evidence is eligible, and
   chosen trajectory policy passes. A chosen age of `0` requires a current
   entry event.
2. Without a matching OPEN saved position, a failed policy returns
   `expired BUY`, with structured reason(s), such as
   `no_observed_entry_event`, `entry_event_age_exceeds_3`, or
   `trajectory_deteriorated`.
3. With a matching OPEN saved position, a failed policy returns `HOLD` unless
   an existing technical-exit, deterioration, stop-loss, or take-profit SELL
   condition independently fires.
4. With a matching OPEN saved position and any existing SELL condition,
   `can SELL` wins.

Monitoring classification may display trajectory health and entry-event age,
but must become `No Match` whenever the chosen entry-age or trajectory policy
fails. The result retains structured reason(s), so `No Match` never hides
whether age, trajectory, evidence, or selected gates caused rejection.

## Versioning and Regeneration

Changing entry from a persistent level mask to an entry event changes historic
trade generation, ranking, and evidence. If selected after investigation, it
is a rulebook-semantic change, not a UI-only fix. Canonical schema-5 artifacts
and sidecars must be atomically replaced by terminal
`requires_regeneration` documents before new logic becomes BUY-eligible.
Existing saved positions stay frozen historical records. No migration may
reinterpret their saved references.

If the investigation selects only a display diagnostic and no execution-policy
change, no regeneration occurs.

## Verification

- VN-Index absent weekday does not enter expected sessions or entry-event age;
  ticker absent on a VN-Index session does enter its coverage gap.
- Session count respects bounds, weekends, and completed W-FRI conversion.
- A ticker row on a VN-Index-absent weekday never reaches an indicator frame;
  an unexpected VN-Index weekend row fails canonical-session validation.
- A Friday with no VN-Index row does not close its weekly bar until a later
  VN-Index session exists; its age anchor is the final real session of that
  week, not the synthetic W-FRI label.
- Entry event fires once for a continuous entry mask, never fabricated after
  unknown warm-up, and is causal.
- TCX fixture proves exact selected gates, gate facts, entry events, age, and
  trajectory values for its supplied raw history.
- All-candidate runner remains read-only, isolates malformed/missing artifacts,
  and never invokes regeneration persistence.
- Training selection cannot read test metrics. Test report labels remain
  `Exploratory — gross`.
- Chosen-policy tests prove `expired BUY`, `HOLD`, and `can SELL` precedence.
- Schema-version/regeneration tests prove old canonical artifacts cannot be
  used for BUY after an entry-semantic change.

## Main Risks

| Risk | Control |
|---|---|
| Missing VN-Index data masks ingestion failure as a holiday | List absent weekdays as assumed non-sessions; retain exact source fingerprints and raw audit. |
| Trajectory filter becomes hindsight fitting | Fixed candidate grid, training-only selection, untouched test evidence. |
| ADX slope is misread as price direction | Require separate causal price/trend evidence. |
| Live validation mutates artifacts during investigation | Dedicated diagnostic never calls regeneration-capable replay. |
| Rulebook behavior changes without requalification | Atomic requires-regeneration replacement before BUY eligibility. |
