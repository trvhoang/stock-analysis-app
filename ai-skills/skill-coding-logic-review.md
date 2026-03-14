# skill-coding-logic-review.md
# SKILL: Coding Logic Review
#
# PURPOSE: Critically review implemented code for logic correctness,
#          correctness against business rules, and edge case coverage
#          specific to this project's domain
# TRIGGER: Task 2 Step 7 — after implementation draft is written
# READS FROM: business-logic.md, conventions.md, boundaries.md
# PRODUCES: Structured logic review report with severity-rated findings
# TOKEN SCOPE: Medium — reads 3 /ai-context files
# LAST UPDATED: 2024-05-24

---

## SKILL OVERVIEW

This skill performs a deep logic review of newly written code, evaluated
specifically against this project's business rules, domain constraints,
and established conventions. It is NOT a generic code review — every
check is anchored to rules documented in the /ai-context files.

It covers: correctness of delta calculations, BIGINT price handling,
SQL parameter binding, timezone logic, trading day arithmetic, and
control flow correctness. It does NOT cover performance or style —
those are handled by separate skills.

Scope IN: Logic correctness, business rule compliance, edge cases,
          silent failure conditions, data type handling.
Scope OUT: Performance bottlenecks, naming conventions, comment quality,
           Docker/environment concerns.

---

## PRE-CONDITIONS

Before executing this skill, verify:
- [ ] Task 2 Step 6 implementation draft exists and has been presented
- [ ] `business-logic.md` has been read (from Task 1 Step 1)
- [ ] `conventions.md` has been read (from Task 1 Step 1)
- [ ] `boundaries.md` has been read (from Task 1 Step 1)

If any pre-condition is not met, state which one and stop.

---

## EXECUTION STEPS

### STEP 1 — MAP CODE TO BUSINESS RULES

For each function or block in the implementation, silently map it to
the relevant rule in `business-logic.md` or `conventions.md`.

Build a mental checklist:
- Which delta formula does this code implement?
- Which price format does it read from or write to?
- Which pages or modules does it affect?
- Does it touch any boundary defined in `boundaries.md`?

Do NOT output yet.

---

### STEP 2 — APPLY PROJECT-SPECIFIC LOGIC CHECKS

Run the following checks against the implementation.
These are non-negotiable for this project:

#### 2A. Delta Calculation Checks
- [ ] If calculating `exact_delta`: uses formula
      `(close_current - close_prev) / close_prev * 100`
- [ ] If using `validation_days` as a lag: lag value is `N - 1`, not `N`
      (a 5-day range = lag of 4, per business-logic.md §2.1)
- [ ] Gap check present: day rank gap equals `validation_days` exactly
      to ensure data continuity — no missing trading days allowed
- [ ] If calculating `result_delta`: uses forward-looking formula
      `(close_next - close_current) / close_current * 100`

#### 2B. Price / BIGINT Checks
- [ ] If reading prices from DB: raw value is `BIGINT` (Price * 1000)
- [ ] If displaying prices to user: divided back by 1000 before display
- [ ] No float conversion applied during storage or delta calculation
      (delta calculation on integers is intentional — do not "fix" this)
- [ ] No direct float arithmetic on raw DB price columns

#### 2C. SQL Safety Checks
- [ ] All SQL uses `sqlalchemy.text()` wrapper — never raw strings
- [ ] All dynamic values use `:param` binding — never f-string or concat
- [ ] If CTE is needed: uses `BASE_DELTA_CALC_CTE` from `common_queries.py`
      rather than reimplementing the CTE manually
- [ ] `get_engine_with_retry()` used for DB connections — never bare `create_engine()`

#### 2D. Ticker Filtering Checks (if Suggestion page or market scan)
- [ ] 'VNINDEX' explicitly excluded
- [ ] Active status filter: last record within 365 days
- [ ] Average volume threshold applied
- [ ] Zero-volume day filter applied
  If any filter is missing for market-wide scans: flag as HIGH severity

#### 2E. Timezone and Date Checks
- [ ] `datetime.now()` without timezone is NOT used for report dates
- [ ] Uses `pytz.timezone('Asia/Ho_Chi_Minh')` for current date logic
- [ ] 8 PM GMT+7 cutoff logic applied where "today's data" is referenced
- [ ] All percentage deltas rounded to 2 decimal places

#### 2F. Statistical Classification Checks
- [ ] Up threshold: `result_delta > 0.1` (not >= 0.1)
- [ ] Down threshold: `result_delta < -0.1` (not <= -0.1)
- [ ] No Change: `-0.1 <= result_delta <= 0.1` (inclusive both ends)
- [ ] Probability formula: count / total * 100 (not count / total alone)

#### 2G. Technical Indicator Checks (if applicable)
- [ ] MA sideways threshold: `abs(FastMA - SlowMA) / Price < 0.02` (2%)
- [ ] RSI sideways: 70% of 30-period lookback between 40–60, OR
      range over last 20 periods < 20 points
- [ ] RSI Up: current between 40–80 AND current >= previous
- [ ] RSI Down: current between 20–60 AND current <= previous
- [ ] Resampling aggregation: open=first, high=max, low=min,
      close=last, volume=sum — no other aggregation
- [ ] `dropna()` applied after resampling

#### 2H. Boundary Violation Checks
- [ ] `common_queries.py` not modified unless task explicitly requires it
- [ ] Price storage format (BIGINT * 1000) not altered
- [ ] DB credentials not hardcoded — `os.getenv()` used
- [ ] No new external dependencies introduced without noting it

---

### STEP 3 — ASSESS CONTROL FLOW

For each function in the implementation:
- [ ] Is there a code path that returns `None` silently when it should raise?
- [ ] Are empty DataFrames handled before calling `.iloc[0]` or similar?
- [ ] Are database errors caught and surfaced — not swallowed?
- [ ] Does the function handle the case where the ticker has no data?
- [ ] Are concurrent operations (ThreadPoolExecutor) safely structured?

---

### STEP 4 — PRESENT THE LOGIC REVIEW REPORT

Present findings using this exact format:

---

**🔍 CODING LOGIC REVIEW REPORT**

**Implementation Reviewed:** [task name]
**Files Reviewed:** [list]

#### Business Rule Compliance

| Rule Area | Check | Status | Severity |
|-----------|-------|--------|----------|
| Delta formula | [specific check] | ✅ Pass / ❌ Fail | — / LOW/MED/HIGH |
| BIGINT handling | [specific check] | ✅ / ❌ | — / severity |
| SQL safety | [specific check] | ✅ / ❌ | — / severity |
| Ticker filtering | [specific check] | ✅ / ❌ | — / severity |
| Timezone logic | [specific check] | ✅ / ❌ | — / severity |
| Statistical classification | [specific check] | ✅ / ❌ | — / severity |
| Technical indicators | [specific check or N/A] | ✅ / ❌ / N/A | — |
| Boundary violations | [specific check] | ✅ / ❌ | — / severity |

#### Control Flow Issues

| Issue | Location (file:function) | Severity | Recommended Fix |
|-------|--------------------------|----------|-----------------|
| [description] | [location] | HIGH/MED/LOW | [fix] |

If none: "No control flow issues found."

#### Critical Findings (Severity HIGH — Must Fix Before Proceeding)

[List every HIGH severity finding with:
- What the issue is
- Exact location (file + function + line if known)
- What business rule it violates (reference business-logic.md section)
- Exact fix required]

If none: "No critical findings — implementation is logically sound."

#### Summary

| Category | Issues Found | Highest Severity |
|----------|--------------|------------------|
| Business Rule Compliance | X | HIGH/MED/LOW/None |
| Control Flow | X | HIGH/MED/LOW/None |
| **Total** | **X** | **[overall]** |

**Verdict:**
- ✅ PASS — No issues found. Logic is correct and compliant.
- ⚠️ PASS WITH WARNINGS — Minor issues found, can proceed with notes.
- ❌ FAIL — HIGH severity issues found. Must revise before proceeding.

---

## QUALITY CHECKLIST

Before presenting the report, verify:
- [ ] Every failed check references the specific rule from business-logic.md
      or conventions.md that was violated — not a generic statement
- [ ] Every HIGH severity finding has a concrete fix proposed
- [ ] N/A is only used for checks genuinely irrelevant to this implementation
- [ ] No issues have been softened — if it violates a rule, it fails
- [ ] The verdict accurately reflects the findings

---

## HARD RULES FOR THIS SKILL

- NEVER pass a check that has a genuine violation — accuracy over comfort
- NEVER mark a BIGINT price handling issue as LOW — it is always HIGH
- NEVER mark a `common_queries.py` boundary violation as LOW — always HIGH
- NEVER suggest rewriting the delta formula — it is defined and fixed
- NEVER flag the intentional integer arithmetic for prices as a bug
- ALWAYS check for empty DataFrame access — this is the #1 silent failure
  pattern in this codebase
- If this skill finds zero issues, justify each major check area briefly
  to confirm it was actually evaluated, not skipped

---

## INTEGRATION WITH OTHER SKILLS

**Feeds into:**
- `ai-command.md` Task 2 Step 8 — Revised Implementation uses findings
- `skill-performance-review.md` — run in parallel or sequentially after this

**Should NOT be combined with:**
- `skill-analyze-wip.md` — that is a planning skill, this is review

**Can be chained with:**
- `skill-performance-review.md` — run immediately after this skill
  to complete the full Step 7 self-criticism report

---

## TOKEN BUDGET GUIDANCE

Token Scope: **Medium**

Files referenced: `business-logic.md`, `conventions.md`, `boundaries.md`

These files are already loaded from Task 1 Step 1 — do NOT re-fetch them.
Reference them from memory. Only re-read a specific section if a check
requires quoting an exact rule for the report.

This skill should produce its full report in a single response.