# /ai-skills — AI Skill Library
#
# PURPOSE: Focused, self-contained execution guides for specific task types.
#          Each skill tells an AI tool exactly HOW to perform one action
#          without re-reading the entire /ai-context folder.
#
# RELATIONSHIP TO /ai-context:
#   /ai-context = what the project IS (knowledge)
#   /ai-skills  = how to DO a specific action (execution)
#
# HOW TO USE:
#   Reference a skill file using @ in your AI tool at the exact moment
#   that skill type is needed. Load only the skill relevant to the current action.
#
# MAINTAINED BY: Project Owner — do not modify unless instructed
# LAST UPDATED: 2024-05-24

---

## Skill Index

| Skill File | Purpose | Trigger | Token Scope |
|------------|---------|---------|-------------|
| `skill-analyze-wip.md` | Extract and prioritize WIP tasks from current-status.md | Task 1 Step 3 — every session | Minimal |
| `skill-implementation-review.md` | Unified review of Logic, Performance, and SQL Safety | Task 2 Step 7 — after implementation | Medium |
| `skill-bug-diagnosis.md` | Diagnose and trace bugs through the project stack | Any time a bug is reported | Medium |

**INACTIVE:** `skill-context-drift.md`, `skill-chart-implementation.md`

---

## Integration with ai-command.md

Skills plug into the task workflow at specific steps:
# skill-implementation-review.md
# SKILL: Comprehensive Implementation Review (Logic, Performance, SQL)
#
# PURPOSE: Unified review of newly written code for business logic correctness,
#          performance bottlenecks, and SQL convention compliance.
# TRIGGER: Task 2 Step 7 — after implementation draft is written.

---

## 1. LOGIC & BUSINESS RULES

- [ ] **BIGINT handling:** Raw DB values (*1000) are divided by 1000 before display/UI.
- [ ] **Delta Formula:** `(current - prev) / prev * 100`. 
- [ ] **Lag Logic:** N-day window uses `LAG(offset=N-1)`.
- [ ] **Timezone:** Uses `pytz.timezone('Asia/Ho_Chi_Minh')`. Naive `now()` forbidden.
- [ ] **Statistical Thresholds:** Up > 0.1, Down < -0.1, No Change [-0.1, 0.1].

## 2. SQL & DATABASE SAFETY

- [ ] **Bindings:** Uses `:param` (standard) or `%(param)s` (raw_connection) - NO f-strings or concatenation.
- [ ] **Wrappers:** Every query wrapped in `sqlalchemy.text()`.
- [ ] **Connections:** Uses `get_engine_with_retry()`. For `pd.read_sql`, uses `engine.raw_connection()`.
- [ ] **CTE Reuse:** `BASE_DELTA_CALC_CTE` is imported/concatenated, not rewritten.
- [ ] **Market Scans:** Filters out 'VNINDEX', enforces min volume, and filters inactive tickers (>365 days).

## 3. PERFORMANCE & STREAMLIT

- [ ] **N+1 Queries:** DB queries are NEVER inside loops. Use batching/SQL aggregates.
- [ ] **Caching:** Expensive results (indicators/large fetches) stored in `st.session_state` with specific keys.
- [ ] **vectorization:** Uses pandas vectorized operations. `iterrows()` is avoided.
- [ ] **Fetch Scope:** Queries bounded by date/ticker; no full table scans unless required.
- [ ] **Concurrency:** `ThreadPoolExecutor` workers create their own DB connections.

---

## OUTPUT FORMAT

### 🔍 IMPLEMENTATION REVIEW REPORT

| Category | Findings | Severity |
|----------|----------|----------|
| Logic    | [Pass/Fail + Note] | [High/Med/Low] |
| SQL      | [Pass/Fail + Note] | [High/Med/Low] |
| Perf     | [Pass/Fail + Note] | [High/Med/Low] |

**Critical Findings (Severity HIGH):**
[List exact code fragment + fix for any High severity issue]

**Verdict:** [✅ PASS | ⚠️ PASS WITH WARNINGS | ❌ FAIL]
---
**Note on SQL Standard:** This project prefers the `engine.raw_connection()` + `%(param)s` pattern for pandas reads to ensure compatibility.
```

```
TASK 1 — Daily Startup
  Step 3 → load @ai-skills/skill-analyze-wip.md

TASK 2 — Implementation
  Step 7 → load @ai-skills/skill-implementation-review.md

TASK 3 — Context Sync
  Step 10 → [Manual process per ai-command.md]

ANY TIME — Bug reported:
  → load @ai-skills/skill-bug-diagnosis.md
```

---

## Token Scope Guide

| Scope | Files Read | Use When |
|-------|-----------|----------|
| Minimal | 1–2 /ai-context files | Fast, focused tasks |
| Medium | 3 /ai-context files | Standard implementation review |
| Full | All 9 /ai-context files | End-of-session context sync only |

Load the minimum skill set needed for the task.
Do NOT load all skills at once — that defeats the token optimization purpose.

---

## Rules for Using Skills

1. Load only the skill(s) relevant to the current action
2. Skills extend ai-command.md — they do not replace any of its steps
3. Skills are read-only for AI tools — never modify a skill file during execution
4. If a skill's pre-conditions are not met, stop and state which one is missing
5. If a skill does not cover an edge case, fall back to /ai-context files
   and flag the gap for a future skill update

---

*Skills are owned by the project owner.*
*AI tools execute skills but never modify them unless explicitly instructed.*