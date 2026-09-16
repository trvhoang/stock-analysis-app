# Validate Signals signal date and win-rate implementation plan

> **For agentic workers:** Use test-first implementation. No Git action.

**Goal:** Carry one causal latest-entry-event date through live validation and
saved-signal position context, then display it with preferred training/test win
rates.

**Architecture:** The existing fresh replay owns the date. Validation only
projects replay facts and immutable preferred-treatment metrics; the Streamlit
page only formats them. Position risk consumes the optional saved date and
retains the historical context fallback.

**Tech stack:** Python 3.12, pandas, Streamlit, unittest, Docker Compose.

## Global constraints

- Use calendar-filtered native bars and only observed false-to-true entry edges.
- Keep manual `buy_date` unchanged.
- Do not change artifacts, SQL, BIGINT scaling, dependencies, Docker, or Git.
- Missing dates/metrics display `—`; legacy positions fall back to `as_of_date`.

### Task 1: Prove and add live replay facts

**Files:**
- Modify: `tests/test_backtest_early_warning.py`
- Modify: `app/backtest_engine/early_warning.py`

- [ ] Add an assertion that a known observed entry edge returns its ISO date,
  and that an all-false entry series returns `None`.
- [ ] Run the focused test and observe failure because current replay lacks
  `signal_date`.
- [ ] Use existing `rulebook_entry_events()` against replay's existing frame
  and missing-input observation mask; add only `signal_date` to `current`.
- [ ] Re-run the focused test successfully.

### Task 2: Project and display validation evidence

**Files:**
- Modify: `tests/test_backtest_validation_advice.py`
- Modify: `tests/test_backtest_page.py`
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `app/pages/backtest_lab.py`

- [ ] Add failing tests for preferred treatment training/test win rates and
  exact `Monitoring: ... - ... | ... | signal date: ... | win rate training /
  test: ...` copy.
- [ ] Project optional `signal_date` plus both preferred-treatment values from
  existing candidate fields. Never change ranking or eligibility.
- [ ] Render DD/MM/YYYY values and `—` for invalid/missing values.
- [ ] Re-run focused validation and rendered-page tests successfully.

### Task 3: Preserve position timing correctly

**Files:**
- Modify: `tests/test_backtest_lab_helpers.py`
- Modify: `tests/test_backtest_position_risk.py`
- Modify: `app/pages/backtest_lab.py`
- Modify: `app/backtest_engine/position_risk.py`

- [ ] Add failing tests that a saved-signal form writes `entry_context.signal_date`,
  retains manual Buy date, and risk uses that date before legacy `as_of_date`.
- [ ] Add read-only saved-set Signal date in New Position and persist the
  validation result's date. Use `signal_date` for risk timing with fallback.
- [ ] Re-run the focused tests successfully.

### Task 4: Verify and record state

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`

- [ ] Run focused Backtest tests, compilation, then full Backtest discovery in
  Docker.
- [ ] Review logic, SQL safety, and Streamlit performance against
  `ai-skills/skill-implementation-review.md`.
- [ ] Record final behavior and exact verification results. No runtime-data or
  Git mutation.
