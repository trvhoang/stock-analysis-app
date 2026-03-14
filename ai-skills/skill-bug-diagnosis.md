# skill-bug-diagnosis.md
# SKILL: Bug Diagnosis
#
# PURPOSE: Systematically diagnose a reported bug by tracing the error
#          through this project's specific stack and data flow
# TRIGGER: When a bug, error, or unexpected behavior is reported
#          at any point during a session
# READS FROM: architecture.md, business-logic.md, boundaries.md
# PRODUCES: Root cause analysis with exact fix proposal
# TOKEN SCOPE: Medium — reads 3 /ai-context files
# LAST UPDATED: 2024-05-24

---

## SKILL OVERVIEW

This skill diagnoses bugs by tracing errors through the specific layers
of this project: Streamlit UI → Python logic → SQLAlchemy → PostgreSQL,
and the reverse for data display. It applies knowledge of this project's
known fragile points (BIGINT prices, CTE queries, session state, Docker
networking, pandas/SQLAlchemy compatibility) to quickly identify root cause.

Scope IN: Error messages, unexpected outputs, broken UI behavior,
          data integrity issues, Docker/DB connection failures.
Scope OUT: Performance issues (skill-performance-review),
           logic rule violations (skill-coding-logic-review).

---

## PRE-CONDITIONS

Before executing this skill, verify:
- [ ] A specific error message, traceback, or unexpected behavior
      has been described or pasted by the human
- [ ] `architecture.md` has been read (from Task 1 Step 1)

If the bug report is too vague, ask ONE clarifying question before proceeding:
> "Can you share the exact error message or describe what you expected
> vs what actually happened?"

---

## EXECUTION STEPS

### STEP 1 — CLASSIFY THE BUG TYPE

Classify the reported issue into one of these categories:

| Type | Description | Common Causes in This Project |
|------|-------------|-------------------------------|
| **Import Error** | Module not found or circular import | Relative imports, refactoring side effects |
| **SQL Error** | ProgrammingError, syntax error, type mismatch | Missing `text()`, f-string SQL, BIGINT type mismatch |
| **Data Error** | Wrong numbers, NaN, empty results | BIGINT not divided by 1000, wrong lag value, missing dropna() |
| **DB Connection** | Connection refused, timeout | Docker startup order, `get_engine_with_retry()` not used |
| **Streamlit Error** | AttributeError, KeyError on session_state | Stale session state, missing key check before access |
| **pandas Error** | AttributeError, IndexError, KeyError on DataFrame | Empty DataFrame not handled, deprecated method used |
| **Concurrency Error** | Thread errors, partial results | Worker exception not caught, shared state accessed unsafely |
| **Chart Error** | Blank chart, missing traces, render error | Wrong column name from pandas-ta, mismatched subplot rows |

---

### STEP 2 — TRACE THE ERROR THROUGH THE STACK

Using `architecture.md` as the map, trace the error from its
reported location back to its root cause layer:

**Layer trace order (follow the data flow):**
1. Streamlit UI (main.py, *_visualization.py)
2. Analysis logic (common_functions.py, analyze_visualization.py, etc.)
3. SQL construction (common_queries.py)
4. Database execution (SQLAlchemy + PostgreSQL)
5. Data ingestion (data_preparation.py) — only for data integrity bugs

For each layer, check:
- Is this where the error is REPORTED? (symptom)
- Is this where the error ORIGINATES? (root cause)
- These are often different layers — find the root, not the symptom

---

### STEP 3 — APPLY PROJECT-SPECIFIC KNOWN FRAGILE POINTS

Check the reported bug against these known fragile points
documented in this project's history:

**Fragile Point 1 — BIGINT Price Display**
- Symptom: Prices appear 1000x too large in UI or calculations
- Root: `/ 1000` conversion missing when displaying or computing
- Check: Is the code reading raw BIGINT and treating it as a float?

**Fragile Point 2 — pandas/SQLAlchemy Compatibility**
- Symptom: `AttributeError` when calling `pd.read_sql()` or similar
- Root: `engine.raw_connection()` not used (see architecture.md fix history)
- Check: Is `pd.read_sql()` being called with a SQLAlchemy engine directly?

**Fragile Point 3 — Trading Day Lag Off-By-One**
- Symptom: Delta calculations return wrong period or empty results
- Root: Using `N` as lag instead of `N-1` for an N-day window
- Check: Is `LAG(close, validation_days)` used instead of `LAG(close, validation_days - 1)`?

**Fragile Point 4 — Relative Import Errors After Refactoring**
- Symptom: `ImportError` or `ModuleNotFoundError` after moving functions
- Root: Relative vs absolute import paths not updated
- Check: Are imports using relative paths (`from . import`) after a move?

**Fragile Point 5 — SQL String Not Wrapped in `text()`**
- Symptom: `ProgrammingError: Textual SQL expression` from SQLAlchemy
- Root: Raw string passed to execute() instead of `text()`
- Check: Every `pd.read_sql()` or `conn.execute()` call uses `text()`?

**Fragile Point 6 — Docker DB Not Ready on App Start**
- Symptom: Connection refused error on first page load
- Root: App container starts before DB container is ready
- Check: Is `get_engine_with_retry()` used? Is `depends_on: db` in docker-compose?

**Fragile Point 7 — Empty DataFrame Access**
- Symptom: `IndexError` or `KeyError` when ticker has no matching history
- Root: `.iloc[0]` or column access on empty result DataFrame
- Check: Is `if df.empty: return` guard present before data access?

**Fragile Point 8 — Stale Streamlit Session State**
- Symptom: Old data shown after changing ticker or timeframe
- Root: Session state cache key not parameterized by ticker/timeframe
- Check: Does the cache key include all input parameters?

---

### STEP 4 — PRESENT THE DIAGNOSIS REPORT

Present findings using this exact format:

---

**🐛 BUG DIAGNOSIS REPORT**

**Bug Reported:** [one-line description of the symptom]
**Error Message / Traceback:** [quote the error if provided]

#### Classification
**Bug Type:** [from Step 1 classification table]
**Symptom Layer:** [where the error appears]
**Root Cause Layer:** [where the error originates]

#### Root Cause Analysis
[2-4 sentences explaining exactly what is causing the bug,
referencing the specific file, function, and line if determinable.
Reference the fragile point number if applicable.]

#### Fragile Point Match
**Matches Known Fragile Point:** [# and name, or "No — novel bug"]

#### Proposed Fix

**File:** `path/to/file.py`
**Function:** `function_name()`
**Change Required:**

```python
# BEFORE (buggy)
[exact current code causing the issue]

# AFTER (fixed)
[exact corrected code with comment explaining why this fixes it]
```

#### Confidence Level
- ✅ HIGH — Root cause is certain based on error and code pattern
- ⚠️ MEDIUM — Most likely cause, but confirmation needed
- ❓ LOW — Hypothesis only — need more information

**If MEDIUM or LOW confidence, ask:**
[One specific question that would confirm or rule out the hypothesis]

#### Regression Check
**Other areas that could be affected by this fix:**
[List any other functions, pages, or queries that might be impacted]
If none: "Fix is isolated — no regression risk identified."

---

🟡 GATE:
> "Root cause identified. Reply CONFIRMED to proceed with the fix,
> or provide additional context if the diagnosis seems incorrect."

---

## QUALITY CHECKLIST

Before presenting the diagnosis:
- [ ] The symptom layer and root cause layer are distinguished —
      not conflated into the same location
- [ ] The proposed fix references the exact file and function
- [ ] The regression check was actually considered — not left blank
- [ ] Confidence level is honest — do not claim HIGH if uncertain
- [ ] If a known fragile point matches, it is explicitly referenced

---

## HARD RULES FOR THIS SKILL

- NEVER propose a fix that touches `common_queries.py` without flagging
  the HIGH impact boundary (see boundaries.md §Core Delta Calculation Logic)
- NEVER propose removing `get_engine_with_retry()` as a fix —
  it is always the correct connection method
- NEVER suggest changing BIGINT storage format as a fix —
  the conversion is intentional (ADR 002)
- ALWAYS check for the pandas/SQLAlchemy compatibility fragile point
  for any `AttributeError` involving DataFrames and DB reads
- If the bug is not reproducible from the information given,
  ask for the full traceback before proposing any fix

---

## INTEGRATION WITH OTHER SKILLS

**Can be triggered at any point** — this skill is not phase-locked
to Task 1, 2, or 3. A bug report interrupts normal flow.

**After diagnosis and fix, resume:**
- If bug found during Task 2: re-run `skill-coding-logic-review.md`
  on the fix before presenting it
- If bug found during Task 3: apply fix then re-run `skill-context-drift.md`
  to capture the fix in documentation

**Feeds into:**
- `current-status.md` — resolved bugs move from Known Issues to Completed

---

## TOKEN BUDGET GUIDANCE

Token Scope: **Medium**

Files referenced: `architecture.md` (data flow and module map),
`business-logic.md` (domain rules for data error diagnosis),
`boundaries.md` (fragile areas to protect during fix)

All three are already in memory from Task 1 Step 1.
Do not re-fetch — reference from memory only.

This skill should diagnose and propose a fix in a single response
unless confidence is LOW and a clarifying question is needed first.