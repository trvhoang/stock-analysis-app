# skill-performance-review.md
# SKILL: Performance Review
#
# PURPOSE: Identify performance bottlenecks, inefficient data handling,
#          and scalability risks specific to this project's stack
# TRIGGER: Task 2 Step 7 — after implementation draft is written,
#          run after skill-coding-logic-review.md
# READS FROM: architecture.md, business-logic.md
# PRODUCES: Performance review report with severity-rated findings
# TOKEN SCOPE: Medium — reads 2 /ai-context files
# LAST UPDATED: 2024-05-24

---

## SKILL OVERVIEW

This skill reviews newly written code for performance risks specific to
this project's stack: Python, Streamlit, PostgreSQL, SQLAlchemy, pandas,
pandas-ta, Plotly, and Docker.

It targets the most common performance anti-patterns seen in Streamlit
data apps: N+1 DB queries, missing session state caching, inefficient
DataFrame operations, blocking concurrent calls, and oversized data fetches.

Scope IN: DB query efficiency, Streamlit state management, DataFrame
          operations, concurrency patterns, memory usage, data fetch scope.
Scope OUT: Logic correctness (skill-coding-logic-review), naming style,
           comment quality, Docker build performance.

---

## PRE-CONDITIONS

Before executing this skill, verify:
- [ ] Task 2 Step 6 implementation draft exists
- [ ] `architecture.md` has been read (from Task 1 Step 1)
- [ ] `business-logic.md` has been read (from Task 1 Step 1)

If any pre-condition is not met, state which one and stop.

---

## EXECUTION STEPS

### STEP 1 — IDENTIFY THE EXECUTION CONTEXT

Determine which module(s) and page(s) the implementation touches,
then apply the relevant checks for that context.

Contexts and their risk profiles:
- **Suggestion page** — runs `analyze_ticker` for ALL liquid tickers
  in parallel via `ThreadPoolExecutor`. Highest risk: N+1 queries.
- **Portfolio Analyze tab** — runs `analyze_ticker` for a user-defined
  list. Medium risk: concurrency and per-ticker DB calls.
- **Ticker Analyze tab** — single ticker analysis. Lower risk.
- **Technical Analyze page** — fetches OHLCV + computes indicators.
  Risk: redundant DB fetches, missing `st.session_state` caching.
- **Data page** — bulk insert pipeline. Risk: memory from large chunks.
- **Result page** — aggregate SQL queries. Risk: missing DB index usage.

---

### STEP 2 — APPLY PERFORMANCE CHECKS

#### 2A. Database Query Efficiency
- [ ] No DB query executed inside a Python loop over tickers or rows
      (this creates N+1 queries — batching or SQL aggregation required)
- [ ] `pd.read_sql()` not called with unbounded queries (no LIMIT when
      full table scan is unnecessary)
- [ ] Queries use `(ticker, date DESC)` index — WHERE clause includes
      `ticker` to leverage `idx_ticker_date`
- [ ] Aggregate operations (COUNT, AVG, SUM) done in SQL not in pandas
      where possible — move work to the database
- [ ] No repeated identical queries in the same function execution path

#### 2B. Streamlit Session State
- [ ] Any expensive computation (indicator calculation, DB fetch for
      technical data) result is stored in `st.session_state`
- [ ] Session state key is specific enough to avoid stale cache
      (e.g. `st.session_state[f"{ticker}_{timeframe}_indicators"]`)
- [ ] UI toggles (checkboxes, tab switches) do NOT re-trigger DB queries
      if data is already in session state
- [ ] `st.session_state` is cleared or invalidated when ticker or
      timeframe input changes — stale state is not served

#### 2C. pandas / pandas-ta Operations
- [ ] `df.append()` not used in loops — use `pd.concat([list])` once
      after building a list
- [ ] `iterrows()` not used for row-by-row computation — use vectorized
      operations or `apply()` with axis=1 only if unavoidable
- [ ] `pandas-ta` indicator functions called once per indicator, not
      recalculated on every Streamlit rerun
- [ ] `resample()` output has `dropna()` applied to remove empty periods
- [ ] DataFrames are not held in memory beyond their needed scope —
      local to function unless caching is intentional

#### 2D. Concurrency (ThreadPoolExecutor)
- [ ] `ThreadPoolExecutor` `max_workers` is bounded — not unlimited
      (unbounded workers can exhaust DB connection pool)
- [ ] Each worker creates its own DB connection via `get_engine_with_retry()`
      rather than sharing one engine object across threads unsafely
- [ ] Exceptions inside worker threads are caught and returned as
      error results — not swallowed silently causing missing rows
- [ ] `timeout` applied to futures where appropriate to prevent hangs

#### 2E. Data Fetch Scope
- [ ] Technical Analyze page fetches only the required date range —
      not the entire trading history for large lookback computations
- [ ] `result_days` and `validation_days` parameters are passed to SQL
      to constrain the date range — not fetched then filtered in pandas
- [ ] For resampling (Week/Month): only the minimum required daily rows
      are fetched, not the full ticker history

#### 2F. Plotly Chart Construction
- [ ] Plotly figures not rebuilt on every Streamlit rerun if underlying
      data has not changed — cache the figure in session state
- [ ] Large OHLCV datasets are not passed entirely to Plotly — slice to
      the display window if the dataset exceeds ~2000 rows

---

### STEP 3 — PRESENT THE PERFORMANCE REVIEW REPORT

Present findings using this exact format:

---

**⚡ PERFORMANCE REVIEW REPORT**

**Implementation Reviewed:** [task name]
**Execution Context:** [which page/module this runs in]
**Scale Assumption:** [e.g. "~500 liquid tickers, ~5 years daily data per ticker"]

#### Findings

| # | Issue | Location | Severity | Fix |
|---|-------|----------|----------|-----|
| 1 | [description] | [file:function] | HIGH/MED/LOW | [specific fix] |

Severity guide for this project:
- **HIGH** — N+1 DB queries in Suggestion/Portfolio page loops,
             missing session state causing full recalc on every UI toggle,
             unbounded ThreadPoolExecutor workers
- **MEDIUM** — Unnecessary full-table fetch, aggregate done in pandas
               instead of SQL, iterrows on large DataFrames
- **LOW** — Minor redundant operations, suboptimal but not impactful
            at current data scale

#### Critical Findings (HIGH Severity — Must Fix)

[For each HIGH finding:]
**Issue:** [description]
**Location:** [file + function]
**Impact:** [what happens at scale — be specific, e.g. "500 tickers × 1 query = 500 DB round-trips per page load"]
**Fix:** [exact change required]

If none: "No HIGH severity performance issues found."

#### Summary

| Category | Issues | Highest Severity |
|----------|--------|-----------------|
| DB Query Efficiency | X | — |
| Streamlit Session State | X | — |
| pandas / pandas-ta | X | — |
| Concurrency | X | — |
| Data Fetch Scope | X | — |
| Plotly | X | — |
| **Total** | **X** | **[overall]** |

**Verdict:**
- ✅ PASS — No issues. Implementation is efficient for current scale.
- ⚠️ PASS WITH WARNINGS — Medium issues noted, acceptable for now.
- ❌ FAIL — HIGH severity issues found. Must revise before proceeding.

---

## QUALITY CHECKLIST

Before presenting the report, verify:
- [ ] Every HIGH finding has a specific, actionable fix — not vague advice
- [ ] Scale assumption is stated explicitly so severity judgements are grounded
- [ ] Session state checks are only applied to Streamlit page code —
      not to utility functions like common_functions.py
- [ ] N/A is used correctly for checks not relevant to this implementation
- [ ] Each finding references the specific file and function affected

---

## HARD RULES FOR THIS SKILL

- NEVER rate a DB query inside a ticker loop as less than HIGH —
  this is the #1 performance killer in this app
- NEVER accept missing session state caching on the Technical Analyze
  page as LOW — UI re-computation is a known pain point
- NEVER suggest removing `get_engine_with_retry()` for performance —
  it is a boundary rule (see boundaries.md §Database Connection Retry Logic)
- ALWAYS state the scale assumption used for severity judgements —
  "500 liquid tickers" is the realistic Suggestion page load
- If zero issues are found, briefly confirm each major category was
  evaluated — do not just write "no issues"

---

## INTEGRATION WITH OTHER SKILLS

**Feeds into:**
- `ai-command.md` Task 2 Step 8 — Revised Implementation uses findings

**Typically runs after:**
- `skill-coding-logic-review.md` — logic correctness first, then performance

**Should NOT be combined with:**
- `skill-analyze-wip.md` — wrong phase
- `skill-context-drift.md` — wrong phase

---

## TOKEN BUDGET GUIDANCE

Token Scope: **Medium**

Files referenced: `architecture.md` (module responsibilities, data flow),
`business-logic.md` (scale context: ticker counts, data volumes)

Both files are already loaded from Task 1 Step 1.
Reference from memory — do not re-fetch.

Focus the performance checks on the execution context identified in Step 1.
A Suggestion page change needs full concurrency + DB query scrutiny.
A single-ticker Analyze page change needs only DB + session state checks.
Scale effort to context.