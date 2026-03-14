# System Instruction — Stock Analysis App
# This file is automatically injected by Gemini Code Assist on every request.
# Keep this file concise — every line costs tokens on every prompt.
# Full documentation lives in /ai-context. Skills live in /ai-skills.

---

## 1. PROJECT SNAPSHOT

Python 3.12 · Streamlit · PostgreSQL · SQLAlchemy · pandas-ta · Plotly · Docker
Vietnamese stock market analysis app — backtests price signals, scans market for opportunities.
All prices stored as BIGINT (value × 1000) in PostgreSQL `trading_data` table.

---

## 2. NON-NEGOTIABLE RULES — ALWAYS FOLLOW

### Code & SQL
- `sqlalchemy.text()` required for ALL SQL — never raw strings or f-strings
- `:param` binding required for ALL dynamic SQL values — never concatenation
- `get_engine_with_retry()` required for ALL database connections
- `BASE_DELTA_CALC_CTE` from `common_queries.py` required for ALL delta queries — never rewrite inline
- `os.getenv()` required for ALL credentials — never hardcode

### Data
- BIGINT prices = raw DB value — ALWAYS divide by 1000 before display or Plotly
- NEVER change price storage format or BIGINT scaling logic
- `pytz.timezone('Asia/Ho_Chi_Minh')` required for ALL current date/time logic
- All percentage deltas rounded to 2 decimal places

### Workflow
- NEVER write code without proposing approach first and receiving APPROVED
- NEVER apply changes to files until human replies APPROVED
- NEVER skip self-criticism after writing code
- NEVER modify `common_queries.py` without explicit instruction
- NEVER introduce new external dependencies without approval

---

## 3. CRITICAL BOUNDARIES — DO NOT TOUCH

| File / Area | Rule |
|-------------|------|
| `app/common_queries.py` | Never modify BASE_DELTA_CALC_CTE or COMMON_DELTA_FILTER_WHERE_CLAUSE |
| `app/data_preparation.py` — BIGINT logic | Never change price × 1000 scaling |
| `app/data_preparation.py` — get_engine_with_retry() | Never remove or alter retry logic |
| `.env` + `app/main.py` — credentials | Never hardcode, never change load pattern |
| `docker-compose.yml` + `Dockerfile` | Modify only with explicit instruction |

---

## 4. ACTIVE SKILLS — LOAD AT THE RIGHT MOMENT

| Skill | When to Load |
|-------|-------------|
| `@ai-skills/skill-analyze-wip.md` | Session start — WIP analysis |
| `@ai-skills/skill-coding-logic-review.md` | After writing any code |
| `@ai-skills/skill-performance-review.md` | After writing any code |
| `@ai-skills/skill-db-query-review.md` | Only when SQL is added or changed |
| `@ai-skills/skill-bug-diagnosis.md` | Only when a bug is reported |

**INACTIVE — Never load:**
`skill-context-drift.md` · `skill-chart-implementation.md`

Load ONLY the skill needed for the current action.
Do NOT preload all skills at once.

---

## 5. FOCUS.md — MANDATORY UPDATE RULE

`FOCUS.md` exists at the project root and defines the current working task.

**You MUST update FOCUS.md when ANY of the following happen:**

- Human states a new task, feature, or requirement
- A WIP item is confirmed as the target for this session
- The current task changes mid-session for any reason
- A new bug is assigned for diagnosis and fixing

**When updating FOCUS.md, follow this exact process:**

STEP 1 — Read `@ai-context/current-status.md` to understand the full WIP context
STEP 2 — Read existing `@FOCUS.md` to see what was previously active
STEP 3 — Write the updated FOCUS.md using the template below
STEP 4 — Present the updated FOCUS.md content to the human for confirmation
STEP 5 — Only after human confirms, treat FOCUS.md as the active task context

**FOCUS.md template:**

```markdown
# FOCUS.md — Active Task Context
# Updated: [date]
# Reference this file with @FOCUS.md in every prompt this session

## Current Task
[One sentence — exactly what is being worked on right now]

## Task Type
[ ] New feature  [ ] Bug fix  [ ] Refactor  [ ] New requirement

## Target Files
[List every file that will be read or modified — paths only]

## Out of Scope — Do Not Touch
[List files or areas explicitly excluded from this task]

## Key Rules for This Task
[3-5 rules from conventions.md or business-logic.md most relevant to THIS task]

## Technical Notes
[Any decisions already made, parameters confirmed, patterns agreed upon]

## Acceptance Criteria
[What does "done" look like — how will we know this task is complete]

## Blocking Rules (from boundaries.md)
[Any boundary that this task operates near — extra caution required]
```

---

## 6. SESSION STARTUP SEQUENCE

When a new session starts, execute in this exact order:

1. Read `@ai-context/current-status.md`
2. Load `@ai-skills/skill-analyze-wip.md` and execute it
3. If WIP exists → update `@FOCUS.md` for the priority task → confirm with human
4. If no WIP → ask human for new task → update `@FOCUS.md` → confirm with human
5. Propose approach using `@FOCUS.md` as scope — no code yet
6. Wait for APPROVED before any implementation

---

## 7. OUT-OF-CONTEXT RECOVERY

If context is lost mid-session, immediately:

1. Read `@FOCUS.md` — this is the fastest recovery path
2. Read `@ai-context/conventions.md` — re-anchor on rules
3. Read `@ai-context/boundaries.md` — re-anchor on what not to touch
4. State out loud: "Context recovered. Current task is: [task from FOCUS.md]"
5. Continue from where work stopped

Do NOT reload all /ai-context files — FOCUS.md + conventions + boundaries
is sufficient to resume safely in under 500 tokens.

---

## 8. FULL CONTEXT REFERENCE

Read these only when FOCUS.md + rules above are insufficient:

- Architecture & modules: `@ai-context/architecture.md`
- Business rules & formulas: `@ai-context/business-logic.md`
- Past decisions (ADRs): `@ai-context/decisions.md`
- Glossary: `@ai-context/glossary.md`
- Build & deploy: `@ai-context/workflows.md`
- Project purpose: `@ai-context/project-overview.md`
- Full session workflow: `@ai-context/ai-command.md`