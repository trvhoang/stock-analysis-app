# skill-db-query-review.md
# SKILL: Database Query Review
#
# PURPOSE: Review any new or modified SQL query for correctness,
#          safety, performance, and compliance with this project's
#          strict SQL conventions and CTE architecture
# TRIGGER: Any task that adds or modifies a SQL query, CTE, or
#          database interaction function
# READS FROM: conventions.md, business-logic.md, boundaries.md
# PRODUCES: SQL review report with pass/fail per rule and fix proposals
# TOKEN SCOPE: Minimal — reads 3 /ai-context files (already in memory)
# LAST UPDATED: 2024-05-24

---

## SKILL OVERVIEW

This skill applies a focused, rule-based review to any SQL query written
for this project. It enforces the strict SQL conventions defined in
`conventions.md`, validates correct use of the shared CTE architecture
in `common_queries.py`, and checks for security, correctness, and
efficiency specific to this project's PostgreSQL schema.

Scope IN: SQL string correctness, `text()` wrapping, parameter binding,
          CTE reuse vs duplication, BIGINT handling, index alignment,
          ticker filtering completeness, timezone correctness.
Scope OUT: Python logic around the query (skill-coding-logic-review),
           query performance profiling (skill-performance-review).

---

## PRE-CONDITIONS

Before executing this skill, verify:
- [ ] The SQL query or DB interaction code has been written
- [ ] `conventions.md` has been read (from Task 1 Step 1)
- [ ] `business-logic.md` has been read (from Task 1 Step 1)
- [ ] `boundaries.md` has been read (from Task 1 Step 1)

If any pre-condition is not met, state which and stop.

---

## EXECUTION STEPS

### STEP 1 — IDENTIFY QUERY TYPE AND SCOPE

Classify the query being reviewed:

| Type | Description | Key Checks to Apply |
|------|-------------|---------------------|
| **Delta Analysis** | Calculates exact_delta or result_delta | CTE reuse, lag formula, gap check |
| **Ticker Scan** | Queries multiple tickers (Suggestion page) | All 4 ticker filters present |
| **OHLCV Fetch** | Raw price data for a ticker | Date range scope, index usage |
| **Aggregate** | COUNT, AVG, SUM for statistics | GROUP BY correctness, FILTER clause |
| **Insert / Upsert** | Data ingestion queries | BIGINT scaling, duplicate handling |
| **Schema / DDL** | Table or index creation | Index coverage, constraint correctness |

---

### STEP 2 — APPLY SQL CONVENTION CHECKS

#### 2A. Safety and Injection Prevention
- [ ] Query wrapped in `sqlalchemy.text()` — never a raw string
- [ ] All dynamic values use `:param_name` binding syntax
- [ ] No f-string interpolation into SQL — `f"WHERE ticker = '{ticker}'"` is FORBIDDEN
- [ ] No string concatenation building SQL — `" WHERE id = " + str(id)` is FORBIDDEN
- [ ] `params` dict passed to `pd.read_sql()` or `conn.execute()` — not inline

#### 2B. CTE Architecture Compliance
- [ ] If calculating delta: uses `BASE_DELTA_CALC_CTE` from `common_queries.py`
- [ ] `BASE_DELTA_CALC_CTE` is NOT reimplemented inline — import and concatenate only
- [ ] If filtering deltas: uses `COMMON_DELTA_FILTER_WHERE_CLAUSE`
- [ ] New query-specific CTEs are appended AFTER `BASE_DELTA_CALC_CTE`,
      not replacing or modifying it
- [ ] CTE alias names do not conflict with existing aliases in
      `BASE_DELTA_CALC_CTE` (`trading_days`, `delta_calc`)

#### 2C. BIGINT Price Handling
- [ ] Price columns (open, high, low, close) are compared or stored as BIGINT
- [ ] If displaying prices: `price / 1000.0` applied in SQL SELECT or in Python
- [ ] Delta percentages are calculated correctly with BIGINT:
      `(close_current - close_prev) * 100.0 / close_prev` — the 100.0 forces
      float division in PostgreSQL
- [ ] No CAST to FLOAT on prices before delta calculation is needed —
      the formula handles it naturally with 100.0 multiplier

#### 2D. Trading Day Logic
- [ ] Uses `ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date)` for day ranking
- [ ] LAG function for N-day window uses `N-1` as the lag offset
- [ ] Gap check present: `(current_rank - prev_rank) = validation_days`
      to ensure no missing trading days in the window
- [ ] Date filtering uses `date` column (not `datetime`) — the schema stores DATE type

#### 2E. Ticker Filtering (for market-scan queries only)
- [ ] `ticker != 'VNINDEX'` filter present
- [ ] Active status: last record within 365 days filter present
- [ ] Average volume >= threshold filter present
- [ ] Zero-volume day exclusion filter present
- [ ] If any of the 4 filters is missing: flag as HIGH severity

#### 2F. Index Alignment
- [ ] WHERE clause includes `ticker` column to use `idx_ticker_date` index
- [ ] Date range filter present to bound the scan:
      avoids full table scan over all historical data
- [ ] ORDER BY uses `date` or `day_rank` — not unindexed columns

#### 2G. Statistical Classification
- [ ] Up: `result_delta > 0.1` (strict greater than)
- [ ] Down: `result_delta < -0.1` (strict less than)
- [ ] No Change: `result_delta BETWEEN -0.1 AND 0.1` (inclusive)
- [ ] Probability: `COUNT(*) FILTER (WHERE ...) * 100.0 / COUNT(*)` pattern used

---

### STEP 3 — PRESENT THE SQL REVIEW REPORT

Present findings using this exact format:

---

**🗄️ DATABASE QUERY REVIEW REPORT**

**Query Reviewed:** [function name or description]
**Query Type:** [from Step 1 classification]
**File:** `path/to/file.py`

#### Rule Compliance

| Rule | Check | Status | Severity |
|------|-------|--------|----------|
| `text()` wrapper | SQL uses sqlalchemy.text() | ✅/❌ | —/HIGH |
| Parameter binding | `:param` syntax used | ✅/❌ | —/HIGH |
| No f-string SQL | No f-string in query string | ✅/❌ | —/HIGH |
| CTE reuse | BASE_DELTA_CALC_CTE used (if delta) | ✅/❌/N/A | —/HIGH |
| BIGINT handling | Price arithmetic is correct | ✅/❌ | —/HIGH |
| Trading day lag | Uses N-1 lag for N-day window | ✅/❌/N/A | —/HIGH |
| Gap check | day_rank gap validation present | ✅/❌/N/A | —/MED |
| Ticker filters | All 4 filters present (if scan) | ✅/❌/N/A | —/HIGH |
| Index alignment | WHERE includes ticker + date range | ✅/❌ | —/MED |
| Classification | Up/Down/No Change thresholds correct | ✅/❌/N/A | —/HIGH |

#### Issues Found

| # | Issue | Location | Severity | Fix Required |
|---|-------|----------|----------|--------------|
| 1 | [desc] | [line/section] | HIGH/MED/LOW | [exact fix] |

If none: "No issues found — query is compliant and correct."

#### Critical Issues (HIGH — Must Fix Before Proceeding)

[For each HIGH finding, show:]
**Issue:** [what is wrong]
**Rule violated:** [which convention or business rule]
**Proposed fix:**
```sql
-- BEFORE
[current problematic SQL fragment]

-- AFTER
[corrected SQL fragment with brief comment]
```

#### Verdict
- ✅ PASS — All rules satisfied. Query is safe and compliant.
- ⚠️ PASS WITH NOTES — Medium issues, acceptable with awareness.
- ❌ FAIL — HIGH severity violations. Must fix before applying.

---

## QUALITY CHECKLIST

Before presenting the report:
- [ ] N/A is used correctly — only when the check genuinely does not apply
      (e.g., ticker filters N/A for a single-ticker query)
- [ ] Every HIGH finding has an exact SQL fix shown — not just a description
- [ ] `common_queries.py` boundary protection checked for any delta query
- [ ] Injection prevention checks applied to ALL dynamic values in the query

---

## HARD RULES FOR THIS SKILL

- NEVER pass an f-string SQL injection risk as LOW — it is always HIGH
- NEVER pass a missing `text()` wrapper as LOW — it is always HIGH
- NEVER approve reimplementing `BASE_DELTA_CALC_CTE` inline — always flag HIGH
- NEVER approve a market-scan query missing all 4 ticker filters — always HIGH
- NEVER suggest changing the BIGINT storage format as a fix — work within it
- If a query modifies `common_queries.py`, flag it as touching a
  critical boundary (boundaries.md §Core Delta Calculation Logic)
  and require explicit human confirmation before proceeding

---

## INTEGRATION WITH OTHER SKILLS

**Typically runs as part of:**
- `skill-coding-logic-review.md` — SQL checks complement Python logic checks

**Should run before:**
- `ai-command.md` Task 2 Step 8 (revision) — fix SQL issues before revising code

**Feeds into:**
- `skill-performance-review.md` — SQL correctness must be confirmed
  before assessing performance optimizations

---

## TOKEN BUDGET GUIDANCE

Token Scope: **Minimal**

All three reference files (`conventions.md`, `business-logic.md`,
`boundaries.md`) are already in memory from Task 1 Step 1.

This skill reviews SQL only — do not expand scope to Python logic
or performance in the same response. Those have their own skills.

This skill should complete in a single response.