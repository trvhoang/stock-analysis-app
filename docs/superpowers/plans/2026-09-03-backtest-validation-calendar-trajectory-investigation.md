# Backtest Validation Calendar and Trajectory Investigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Backtest rulebook indicator frame use the shared VN-Index session calendar, then produce a read-only, causally correct audit of calendar, signal-age, and trajectory policies for every saved Backtest candidate and present untouched-test evidence for one separately approved Validate Signals policy.

**Architecture:** Keep VN-Index row availability as the one session calendar and expose it through pure evidence helpers. Build entry-event, age, and trajectory facts in a read-only diagnostic service that never enters the regeneration-capable replay path. Reuse the existing schema-5 split, executor, and partition metrics to compare a fixed grid of policy candidates on training, then reveal test evidence without changing live BUY/SELL behavior.

**Tech Stack:** Python 3.12, pandas, Streamlit-adjacent Backtest engine, PostgreSQL through existing loaders, pytest/unittest, Docker Compose.

## Global Constraints

- Do not perform any Git action or create a commit.
- Do not modify `app/common_queries.py`, BIGINT price scaling, credential loading, Docker files, or introduce dependencies.
- Use the actual bounded VN-Index rows as the canonical session calendar; a missing weekday is `assumed_non_session`, not an invented trading day.
- A VN-Index weekend row is invalid session evidence; a ticker row outside the calendar is excluded from calculation and reported as a source anomaly.
- Swing candidate ages are exactly `0, 1, 2, 3, 5` canonical VN-Index sessions. Mid-term candidate ages are exactly `0, 1, 2, 3, 5` completed W-FRI bars, each anchored to the last real VN-Index session in its week.
- Friday without a VN-Index row is not treated complete until a later real VN-Index session proves that week ended; never synthesize an intraday holiday.
- Diagnostics and policy evaluation are read-only: never call `check_current_situation()`, `write_regeneration_marker()`, or any artifact/job/position writer.
- Training selects; untouched test only reports. All report copy is `Exploratory — gross`; never say profitable, tradable, or statistically certified.
- This plan does **not** change live Validate Signals. A new plan begins only after the user selects one evidenced policy.

---

## File Structure

- Modify `app/backtest_engine/evidence.py`: reusable bounded VN-Index calendar, ticker-frame intersection, native session ages, and source-anomaly evidence.
- Modify `app/backtest_engine/indicators.py`, `pipeline.py`, `early_warning.py`, `position_risk.py`, and `research_optimizer.py`: require and pass the shared calendar before every Backtest rulebook indicator frame.
- Modify `app/backtest_engine/timeframes.py`: map completed W-FRI labels to real VN-Index session anchors without changing W-FRI OHLCV labels.
- Modify `app/backtest_engine/signal_combos.py`: pure observed false-to-true entry-event helper; preserve existing level-entry function.
- Modify `app/backtest_engine/early_warning.py`: expose a read-only fresh-source loader and pure full-frame facts used by diagnostics; retain the existing regeneration path unchanged.
- Create `app/backtest_engine/validation_diagnostics.py`: saved-candidate inspection and training/test fixed-policy comparison, with no persistence.
- Create `tests/test_backtest_validation_diagnostics.py`: all diagnostic, policy, and read-only contracts.
- Modify `tests/test_backtest_evidence.py`, `tests/test_backtest_indicators.py`, `tests/test_backtest_signal_combos.py`, and `tests/test_backtest_early_warning.py`: calendar, weekly-anchor, event, and replay-separation regression coverage.
- Modify `FOCUS.md` and `ai-context/current-status.md`: record the investigation result and explicit live-policy decision gate after the live audit runs.

## Task 1: Canonical VN-Index Session and Weekly-Anchor Primitives

**Files:**
- Modify: `app/backtest_engine/evidence.py`
- Modify: `app/backtest_engine/timeframes.py`
- Test: `tests/test_backtest_evidence.py`
- Test: `tests/test_backtest_indicators.py`

**Consumes:** canonical raw OHLCV frames and existing `_canonical_rows()`.

**Produces:**

```python
@dataclass(frozen=True)
class CanonicalSessionCalendar:
    sessions: tuple[date, ...]
    assumed_non_sessions: tuple[date, ...]

def canonical_vnindex_calendar(
    vnindex_frame: pd.DataFrame,
    common_as_of: date,
    *,
    start: date,
) -> CanonicalSessionCalendar: ...

def restrict_to_canonical_sessions(
    ticker_frame: pd.DataFrame,
    calendar: CanonicalSessionCalendar,
) -> tuple[pd.DataFrame, tuple[date, ...]]: ...

def native_session_age(
    calendar: CanonicalSessionCalendar,
    event_date: date,
    as_of_date: date,
) -> int | None: ...

def completed_weekly_session_anchors(
    weekly_labels: pd.Series,
    calendar: CanonicalSessionCalendar,
) -> pd.Series: ...
```

- [ ] **Step 1: Write failing calendar and source-anomaly tests**

```python
def test_absent_vnindex_weekday_is_not_a_session_but_ticker_absence_is_a_gap(self):
    vnindex = _session_frame(5).drop(index=[2]).reset_index(drop=True)
    ticker = vnindex.copy(deep=True)
    calendar = canonical_vnindex_calendar(
        vnindex, vnindex["date"].iloc[-1].date(),
        start=date(2020, 1, 1),
    )
    self.assertEqual(4, len(calendar.sessions))
    self.assertEqual((date(2020, 1, 3),), calendar.assumed_non_sessions)
    self.assertNotIn(date(2020, 1, 3), calendar.sessions)

    gap = ticker.iloc[[0, 1, 3]].copy()
    evidence = assess_evidence(gap, vnindex, vnindex["date"].iloc[-1].date())
    self.assertIn("coverage_ratio_below_0.95", evidence.reasons)

def test_ticker_row_outside_vnindex_calendar_is_excluded_and_reported(self):
    vnindex = _session_frame(4).drop(index=[2]).reset_index(drop=True)
    ticker = pd.concat([vnindex, _session_frame(3).iloc[[-1]]], ignore_index=True)
    calendar = canonical_vnindex_calendar(
        vnindex, vnindex["date"].iloc[-1].date(), start=date(2020, 1, 1)
    )
    filtered, outside = restrict_to_canonical_sessions(ticker, calendar)
    self.assertEqual(3, len(filtered))
    self.assertEqual((date(2020, 1, 3),), outside)

def test_vnindex_weekend_row_is_rejected(self):
    vnindex = pd.concat([_session_frame(2), _session_frame(3).iloc[[-1]]])
    vnindex.loc[vnindex.index[-1], "date"] = pd.Timestamp("2020-01-04")
    with self.assertRaisesRegex(ValueError, "weekend"):
        canonical_vnindex_calendar(vnindex, date(2020, 1, 4), start=date(2020, 1, 1))
```

- [ ] **Step 2: Run the targeted test file to verify missing interfaces fail**

Run: `docker compose exec -T app pytest tests/test_backtest_evidence.py -q`  
Expected: FAIL with missing `canonical_vnindex_calendar` / `restrict_to_canonical_sessions` imports.

- [ ] **Step 3: Implement the smallest shared calendar API in `evidence.py` and make calendar input mandatory for Backtest frames**

```python
@dataclass(frozen=True)
class CanonicalSessionCalendar:
    sessions: tuple[date, ...]
    assumed_non_sessions: tuple[date, ...]

def canonical_vnindex_calendar(vnindex_frame, common_as_of, *, start):
    rows = _canonical_rows(vnindex_frame, common_as_of)
    rows = rows.loc[rows["date"].ge(pd.Timestamp(start))].copy()
    if rows["date"].dt.weekday.ge(5).any():
        raise ValueError("VN-Index source contains a weekend row")
    sessions = tuple(pd.Timestamp(day).date() for day in rows["date"])
    expected = pd.bdate_range(start, common_as_of)
    observed = {pd.Timestamp(day) for day in rows["date"]}
    missing = tuple(day.date() for day in expected if day not in observed)
    return CanonicalSessionCalendar(sessions, missing)

def restrict_to_canonical_sessions(ticker_frame, calendar):
    working = ticker_frame.copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    allowed = pd.DatetimeIndex(calendar.sessions)
    bounded = working.loc[working["date"].le(allowed.max())]
    outside = tuple(day.date() for day in bounded.loc[~bounded["date"].isin(allowed), "date"])
    return bounded.loc[bounded["date"].isin(allowed)].reset_index(drop=True), outside
```

Make `assess_evidence()` derive expected sessions from this helper, retain the existing reason names, and append exactly `ticker_rows_outside_vnindex_sessions` when `outside` is non-empty. Do not add a schema field; the existing `reasons` field is sufficient.

Extend `build_rulebook_frame()` and `build_indicator_frame()` with required
`session_calendar: CanonicalSessionCalendar` input. Before any daily or weekly
indicator computation, use `restrict_to_canonical_sessions()`. Update every
Backtest call site that already has VN-Index history (`pipeline`,
`early_warning`, `diagnostics`, `research_optimizer`, and `position_risk`) to
construct/pass the same calendar. A path without supplied VN-Index history
must return its existing unavailable result rather than computing uncalendared
indicators. The Technical Analysis page is not a Backtest rulebook caller and
is deliberately untouched.

- [ ] **Step 4: Add W-FRI-anchor failing tests, then implement the pure mapping**

```python
def test_holiday_friday_uses_thursday_anchor_only_after_next_session(self):
    calendar = CanonicalSessionCalendar(
        sessions=(date(2024, 5, 13), date(2024, 5, 14), date(2024, 5, 15), date(2024, 5, 16), date(2024, 5, 20)),
        assumed_non_sessions=(date(2024, 5, 17),),
    )
    labels = pd.Series(pd.to_datetime(["2024-05-17"]))
    anchors = completed_weekly_session_anchors(labels, calendar)
    self.assertEqual(pd.Timestamp("2024-05-16"), anchors.iloc[0])
```

```python
def completed_weekly_session_anchors(weekly_labels, calendar):
    sessions = pd.Series(pd.to_datetime(calendar.sessions))
    anchors = []
    for label in pd.to_datetime(weekly_labels):
        same_week = sessions.loc[sessions.dt.to_period("W-FRI") == label.to_period("W-FRI")]
        anchors.append(pd.NaT if same_week.empty else same_week.max())
    return pd.Series(anchors, index=weekly_labels.index, dtype="datetime64[ns]")
```

Keep `to_weekly_ohlcv()` output labels byte-for-byte unchanged. The caller must only pass an already completed W-FRI label; this function must not decide that Friday has completed.

- [ ] **Step 5: Run focused verification**

Run: `docker compose exec -T app pytest tests/test_backtest_evidence.py tests/test_backtest_indicators.py -q`  
Expected: PASS; the existing short-holiday-week W-FRI label test still passes.

### Task 2: Causal Entry Events and Trajectory Facts

**Files:**
- Modify: `app/backtest_engine/signal_combos.py`
- Create: `tests/test_backtest_validation_diagnostics.py`
- Test: `tests/test_backtest_signal_combos.py`

**Consumes:** level `rulebook_entry_signal()` and the frame's explicit missing-input column.

**Produces:**

```python
def rulebook_entry_events(
    entry_mask: pd.Series,
    observed_mask: pd.Series,
) -> pd.Series: ...
```

- [ ] **Step 1: Write failing entry-event tests**

```python
def test_entry_event_fires_once_and_never_after_unknown_warmup(self):
    entry = pd.Series([True, True, False, True, True])
    observed = pd.Series([False, True, True, True, True])
    self.assertEqual(
        rulebook_entry_events(entry, observed).tolist(),
        [False, False, False, True, False],
    )

def test_entry_event_requires_immediate_observed_false_predecessor(self):
    self.assertEqual(
        rulebook_entry_events(pd.Series([False, True]), pd.Series([True, True])).tolist(),
        [False, True],
    )
```

- [ ] **Step 2: Run to prove the helper is absent**

Run: `docker compose exec -T app pytest tests/test_backtest_signal_combos.py tests/test_backtest_validation_diagnostics.py -q`  
Expected: FAIL with `rulebook_entry_events` import error.

- [ ] **Step 3: Implement only the causal event primitive**

```python
def rulebook_entry_events(entry_mask, observed_mask):
    entry = pd.Series(entry_mask, index=entry_mask.index).fillna(False).astype(bool)
    observed = pd.Series(observed_mask, index=entry.index).fillna(False).astype(bool)
    prior_observed = observed.shift(1, fill_value=False)
    prior_entry = entry.shift(1, fill_value=False)
    return (observed & entry & prior_observed & ~prior_entry).astype(bool)
```

Do not alter `rulebook_entry_signal()` or the backtest executor in this task.

- [ ] **Step 4: Run entry-event tests**

Run: `docker compose exec -T app pytest tests/test_backtest_signal_combos.py tests/test_backtest_validation_diagnostics.py -q`  
Expected: PASS.

### Task 3: Read-Only Saved-Candidate Diagnostic Service

**Files:**
- Modify: `app/backtest_engine/early_warning.py`
- Create: `app/backtest_engine/validation_diagnostics.py`
- Modify: `tests/test_backtest_early_warning.py`
- Test: `tests/test_backtest_validation_diagnostics.py`

**Consumes:** Tasks 1–2, `load_current_rulebook_document()`, raw existing loaders, `build_rulebook_frame()`, and schema-5 saved documents.

**Produces:**

```python
def load_fresh_rulebook_sources(
    document: Mapping[str, object], ticker: str, engine,
) -> tuple[pd.DataFrame, pd.DataFrame, EvidenceEligibility]: ...

def build_rulebook_replay_series(
    ticker: str, horizon: str, selected_gates: tuple[str, ...],
    preferred_variant: str, *, ticker_raw: pd.DataFrame,
    vnindex_raw: pd.DataFrame, common_as_of: date,
) -> dict[str, object]: ...

def trajectory_facts(
    frame: pd.DataFrame,
    selected_gates: tuple[str, ...],
    horizon: str,
) -> dict[str, bool | None]: ...

def inspect_saved_candidate(
    ticker: str, *, horizon: str, rulebook_id: str, engine,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    trace_start: date | None = None,
) -> dict[str, object]: ...

def audit_saved_candidates(
    tickers: Sequence[str], engine, *, signal_dir: str = DEFAULT_SIGNAL_DIR,
    trace_overrides: Mapping[str, date] | None = None,
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write the hard read-only contract test**

```python
def test_diagnostic_never_calls_regeneration_replay_or_writer(self):
    with patch("backtest_engine.validation_diagnostics.check_current_situation") as replay, \
         patch("backtest_engine.early_warning.write_regeneration_marker") as marker:
        result = inspect_saved_candidate("FPT", horizon="swing", rulebook_id=RULE_ID, engine=object())
    replay.assert_not_called()
    marker.assert_not_called()
    self.assertIn(result["availability"], {"available", "unavailable"})
```

- [ ] **Step 2: Expose the non-mutating fresh-source loader and refactor the existing replay to use it**

```python
def load_fresh_rulebook_sources(document, ticker, engine):
    start, _ = _replay_bounds(document)
    ticker_raw = _load_raw(ticker, engine, start=start, end=_fresh_bounds()[1])
    vnindex_raw = _load_raw("VNINDEX", engine, start=start, end=_fresh_bounds()[1])
    evidence = validate_current_evidence(document, ticker_raw, vnindex_raw)
    return ticker_raw, vnindex_raw, evidence
```

`check_current_situation()` may call this loader, then retain its present fingerprint comparison and write behavior. The new diagnostic calls the loader only and never checks or writes a regeneration marker.

- [ ] **Step 3: Implement the diagnostic record and TCX trace**

For an available record return the fixed shape:

```python
{
    "availability": "available",
    "ticker": "TCX",
    "horizon": "swing",
    "rulebook_id": RULE_ID,
    "selected_gates": ["..."],
    "preferred_variant": "no-background-theme",
    "evidence_eligibility": {"...": "..."},
    "common_as_of": "YYYY-MM-DD",
    "native_as_of": "YYYY-MM-DD",
    "monitoring": {"match_level": 0.0, "match_classification": "..."},
    "entry_events": {"latest_date": "YYYY-MM-DD" | None, "age": 0 | None},
    "trajectory": {"trajectory_a": False, "trajectory_b": False, "trajectory_c": False},
    "trace": [{"date": "...", "close": 0.0, "gate_facts": {}}],
    "assumed_non_sessions": ["YYYY-MM-DD"],
    "source_anomalies": ["ticker_rows_outside_vnindex_sessions"],
}
```

For unavailable documents/sources return `availability: "unavailable"`, ticker/horizon/rulebook identity when known, and a concrete `reason`; do not fabricate a trace. `audit_saved_candidates()` must continue after one candidate failure and include an error record for that candidate.

Filter raw ticker history with `restrict_to_canonical_sessions()` **before** `build_rulebook_frame()`. Build the observed mask from non-missing rulebook inputs plus usable theme inputs, then derive `rulebook_entry_events()`. For Mid-term, convert completed W-FRI labels to anchors with Task 1 before calculating age.

`build_rulebook_replay_series()` owns the shared frame, aligned theme series,
entry mask, and observed mask construction. Refactor `_current_rulebook_facts()`
to read its final row from that helper, so diagnostics cannot drift from live
facts while still avoiding `check_current_situation()`.

- [ ] **Step 4: Write and implement trajectory-fact coverage**

```python
def test_trajectory_a_requires_both_falling_close_and_failed_joint_trend(self):
    facts = trajectory_facts(_declining_frame(joint_trend=False), ("rulebook_adx_gate",), "swing")
    self.assertTrue(facts["trajectory_a"])
    self.assertFalse(facts["trajectory_b"])
    self.assertFalse(facts["trajectory_c"])

def test_adx_fall_alone_never_sets_trajectory_failure(self):
    facts = trajectory_facts(_rising_price_frame(adx_falling=True, joint_trend=True), ("rulebook_adx_gate",), "swing")
    self.assertFalse(facts["trajectory_a"])
    self.assertFalse(facts["trajectory_c"])
```

Implement the fixed keys below. `rsi_recedes` is `None` unless RSI is selected;
`adx_recedes` is `None` unless ADX is selected. Read thresholds from
`rulebook_for(horizon)`, never duplicate numeric thresholds. A missing native
lookback produces `False`, never a guessed decline.

```python
{
    "close_declines_3_native_bars": bool,
    "joint_trend_fails": bool,
    "rsi_below_selected_upcross_level": bool | None,
    "adx_below_horizon_min_and_falling": bool | None,
    "trajectory_a": close_declines and joint_trend_fails,
    "trajectory_b": trajectory_a and bool(rsi_recedes),
    "trajectory_c": trajectory_a and bool(adx_recedes),
}
```

- [ ] **Step 5: Add deterministic diagnostic coverage**

```python
def test_midterm_age_counts_completed_w_fri_labels_but_reports_real_anchor(self):
    result = inspect_saved_candidate(...)
    self.assertEqual(1, result["entry_events"]["age"])
    self.assertEqual("2024-05-16", result["entry_events"]["latest_anchor_date"])

def test_missing_tcx_artifact_is_an_explicit_unavailable_record(self):
    result = audit_saved_candidates(("TCX",), object(), signal_dir=self.empty_dir,
                                    trace_overrides={"TCX": date(2026, 8, 25)})
    self.assertEqual("unavailable", result["records"][0]["availability"])
    self.assertIn("schema-5", result["records"][0]["reason"])
```

- [ ] **Step 6: Run read-only service verification**

Run: `docker compose exec -T app pytest tests/test_backtest_early_warning.py tests/test_backtest_validation_diagnostics.py -q`  
Expected: PASS; the mutation mock is never called.

### Task 4: Training-Selected, Untouched-Test Policy Evidence

**Files:**
- Modify: `app/backtest_engine/validation_diagnostics.py`
- Test: `tests/test_backtest_validation_diagnostics.py`

**Consumes:** Task 3 records, `split_native_frame()`, `run_rulebook_trade_sequence()`, `partition_completed_events()`, and `partition_metrics()`.

**Produces:**

```python
POLICY_GRID = (
    (0, "none"), (1, "none"), (2, "none"), (3, "none"), (5, "none"),
    (0, "a"), (1, "a"), (2, "a"), (3, "a"), (5, "a"),
    (0, "b"), (1, "b"), (2, "b"), (3, "b"), (5, "b"),
    (0, "c"), (1, "c"), (2, "c"), (3, "c"), (5, "c"),
)

def evaluate_validation_policy_grid(
    diagnostic: Mapping[str, object],
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write a test proving training selects and test is observation only**

```python
def test_training_ranked_policy_cannot_change_when_only_test_returns_change(self):
    first = evaluate_validation_policy_grid(_fixture_with_test_returns([30.0, -10.0]))
    second = evaluate_validation_policy_grid(_fixture_with_test_returns([-90.0, 90.0]))
    self.assertEqual(first["training_ranked_policy"], second["training_ranked_policy"])
    self.assertNotEqual(first["policies"], second["policies"])

def test_policy_grid_has_exactly_five_ages_for_each_of_four_trajectory_modes(self):
    report = evaluate_validation_policy_grid(_fixture_diagnostic())
    self.assertEqual(20, len(report["policies"]))
    self.assertEqual({0, 1, 2, 3, 5}, {item["max_age"] for item in report["policies"]})
```

- [ ] **Step 2: Run to establish the evaluator is missing**

Run: `docker compose exec -T app pytest tests/test_backtest_validation_diagnostics.py -q`  
Expected: FAIL with missing `evaluate_validation_policy_grid`.

- [ ] **Step 3: Implement the causal evaluator with existing partition semantics**

For each policy construct a Boolean signal at each native bar:

```python
eligible = (
    most_recent_entry_event_age.le(max_age)
    & ~trajectory_failure_for(mode)
    & evidence_eligible
)
```

Use `split_native_frame()` for the current artifact's requested range. Run the existing flat-to-flat executor separately inside its returned train and test windows, then call `partition_completed_events()` so signal, entry, and exit are all contained in their own partition. Derive gross metrics with `partition_metrics()` using the document's existing permutation settings only for informational p-value behavior.

For every native bar, `most_recent_entry_event_age` is the horizon-native age
of the last observed false-to-true event, or missing when no event has yet
occurred. This makes ages `1`, `2`, `3`, and `5` meaningful without ever
relabeling a persistent level as a new event.

Rank the evidence (but do not adopt a live policy) by this unrounded training key:

```python
(-training.win_rate, -training.profit_pct, -float(training.sharpe or 0.0), max_age, trajectory_mode)
```

The final two fields make an exact tie deterministic. Do not read test metrics during ranking. Preserve test metrics, false-BUY removals, and valid-BUY losses as evidence only. A removed current-behavior signal is false-BUY when its current-policy completed trade return is `<= 0`; it is a valid-BUY loss when that return is `> 0`.

- [ ] **Step 4: Add boundary and causality tests**

```python
def test_cross_boundary_trade_is_dropped_from_both_policy_partitions(self):
    report = evaluate_validation_policy_grid(_fixture_cross_boundary_trade())
    selected = report["training_ranked_policy"]
    self.assertEqual(0, selected["training"]["n"])
    self.assertEqual(0, selected["test"]["n"])

def test_midterm_uses_bar_age_not_calendar_days(self):
    report = evaluate_validation_policy_grid(_fixture_midterm_holiday_week())
    policy = next(item for item in report["policies"] if item["max_age"] == 1 and item["trajectory_mode"] == "none")
    self.assertTrue(policy["latest_signal_is_eligible"])
```

- [ ] **Step 5: Run evaluator verification**

Run: `docker compose exec -T app pytest tests/test_backtest_validation_diagnostics.py tests/test_backtest_exploratory.py tests/test_backtest_trade_execution.py -q`  
Expected: PASS; existing trade partition contracts remain unchanged.

### Task 5: Live Read-Only TCX/All-Candidate Audit and Decision Gate

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Test: all Task 1–4 test files

**Consumes:** completed diagnostic and policy-evidence APIs; Docker database that the user has confirmed is running.

**Produces:** a terminal-only read-only evidence report and an explicit recorded choice required before live behavior can change.

- [ ] **Step 1: Run the full targeted regression suite before live data**

Run: `docker compose exec -T app pytest tests/test_backtest_evidence.py tests/test_backtest_indicators.py tests/test_backtest_signal_combos.py tests/test_backtest_early_warning.py tests/test_backtest_validation_diagnostics.py tests/test_backtest_validation_advice.py -q`  
Expected: PASS.

- [ ] **Step 2: Run the TCX trace and all available saved candidates with no writes**

Run a one-shot Python invocation inside the app container that calls only `audit_saved_candidates()` with `trace_overrides={"TCX": date(2026, 8, 25)}` and serializes the returned Python value to stdout. Do not call `check_current_situation()`, `validate_saved_signals()`, or any persistence API.

Expected output: one TCX detailed trace (or explicit unavailable record), each saved candidate's gate facts/event age/trajectory facts, assumed non-sessions, source anomalies, and each policy's training/test gross evidence.

- [ ] **Step 3: Self-critique the evidence before recommending a policy**

Verify all of the following from output, and report any failure rather than selecting a policy:

```text
1. TCX claim is trace-supported by its actual selected gates, not by a generic RSI/ADX story.
2. No absent VN-Index weekday appears in a session-age denominator.
3. Mid-term holiday-week labels have real anchors and are not finalized on a merely absent Friday.
4. The selected key was calculated from training only.
5. Test results can be worse; that is evidence, not a selection rewrite.
6. No artifact, job sidecar, or saved position changed.
```

- [ ] **Step 4: Update context documents with only verified results**

In `FOCUS.md`, record the task as `investigation complete — live policy selection pending` and link this plan/design. In `ai-context/current-status.md`, record only observed TCX status, test commands/results, and the exact policy options. Do not claim an improvement or mark Validate Signals fixed.

- [ ] **Step 5: Stop for the user’s fixed-policy decision**

Present the training-ranked policy plus untouched test evidence and alternatives. It is a recommendation only, not a live behavior change. The next implementation plan begins only after the user approves exactly one age/trajectory mode and explicitly authorizes schema-5 terminal `requires_regeneration` replacement plus the live action/classification change.

## Plan Self-Review

**Spec coverage:** Task 1 covers sole VN-Index calendar, weekdays/weekends, ticker anomalies, and safe W-FRI anchors. Task 2 covers false-to-true events. Task 3 covers direction-aware trajectory facts plus TCX/all-candidate, causal/read-only diagnostics and error isolation. Task 4 covers the exact age/mode grid, training-only evidence ranking, untouched test, and completed-trade partition rule. Task 5 covers live evidence, self-critique, documentation, and the required separate live-policy approval.

**Deliberate boundary:** The spec requires a separately approved fixed policy before live `expired BUY`/`HOLD`/`can SELL`, `No Match`, and schema regeneration behavior changes. This plan therefore produces the evidence needed for that approval and does not silently change production semantics.

**Placeholder scan:** No TBD/TODO/"appropriate handling" placeholders. All new interfaces, policy values, output labels, tests, and verification commands are explicitly named.

**Type consistency:** Calendar values use `date`; frames use `pd.DataFrame`/`pd.Series`; `rulebook_entry_events()` returns a Boolean Series aligned to the input; diagnostic records use JSON-safe `dict[str, object]`; the evaluator reuses existing `EvaluationSplit`, `TradeEvent`, and `PartitionMetrics` rather than creating a parallel trade model.
