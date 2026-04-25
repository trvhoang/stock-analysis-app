# AGENTS.md — Stock Analysis App
# This file is read by Codex at the start of every task.
# It is the single source of truth for all AI coding rules.

---

## 1. MANDATORY ONBOARDING — READ BEFORE ANYTHING ELSE

When starting any task in this project, read these files
in this exact order before writing a single line of code:

1. `FOCUS.md`                        — current task and active context
2. `ai-context/README.md`            — project overview and reading order
3. `ai-context/conventions.md`       — coding standards (non-negotiable)
4. `ai-context/boundaries.md`        — what must never be touched
5. `ai-context/current-status.md`    — WIP tasks and known issues

Read the following ONLY when the task directly involves them:
- `ai-context/architecture.md`       — module structure and data flow
- `ai-context/business-logic.md`     — delta formulas, indicator rules
- `ai-context/decisions.md`          — past ADRs (why things are the way they are)
- `ai-context/glossary.md`           — domain terms
- `ai-context/workflows.md`          — build and deploy process

---

## 2. PROJECT SNAPSHOT

Python 3.12 · Streamlit · PostgreSQL · SQLAlchemy · pandas-ta · Plotly · Docker
Vietnamese stock market analysis app.
All prices stored as BIGINT (value × 1000) in `trading_data` table.
SQL standard: `sqlalchemy.text()` + `engine.raw_connection()` + `%(param)s` bindings.

---

## 3. NON-NEGOTIABLE RULES

### SQL & Database
- `sqlalchemy.text()` for ALL SQL — never raw strings or f-strings
- `%(param)s` binding for ALL dynamic SQL values — never concatenation
- `get_engine_with_retry()` + `engine.raw_connection()` for all DB connections
- `BASE_DELTA_CALC_CTE` from `common_queries.py` for ALL delta queries
  — never rewrite or duplicate this CTE inline anywhere
- `os.getenv()` for ALL credentials — never hardcode

### Data Integrity
- BIGINT prices = raw DB value — ALWAYS divide by 1000 before display or Plotly
- NEVER alter price storage format or BIGINT × 1000 scaling logic
- `pytz.timezone('Asia/Ho_Chi_Minh')` for ALL datetime logic
- All percentage deltas rounded to 2 decimal places

### Workflow
- NEVER write code without proposing approach first and receiving APPROVED
- NEVER apply file changes until human replies APPROVED
- NEVER skip self-criticism after writing code
- NEVER modify `common_queries.py` without explicit instruction
- NEVER introduce new dependencies without approval

---

## 4. CRITICAL BOUNDARIES — NEVER TOUCH WITHOUT EXPLICIT INSTRUCTION

| File / Area | Rule |
|-------------|------|
| `app/common_queries.py` — `BASE_DELTA_CALC_CTE` | Never modify |
| `app/common_queries.py` — `COMMON_DELTA_FILTER_WHERE_CLAUSE` | Never modify |
| `app/data_preparation.py` — BIGINT scaling | Never alter price × 1000 logic |
| `app/data_preparation.py` — `get_engine_with_retry()` | Never remove or alter |
| `.env` + `app/main.py` — credentials | Never hardcode, never change load pattern |
| `docker-compose.yml` + `Dockerfile` | Modify only with explicit instruction |

---

## 5. ACTIVE SKILLS — LOAD ON DEMAND ONLY

Skills are focused execution guides in `/ai-skills/`. Load only the
skill relevant to the current action — never preload all at once.

| Skill File | Load When |
|------------|-----------|
| `ai-skills/skill-analyze-wip.md` | Analyzing WIP tasks at session start |
| `ai-skills/skill-implementation-review.md` | After writing any code |
| `ai-skills/skill-bug-diagnosis.md` | When a bug or error is reported |

INACTIVE — never load or reference:
- `skill-context-drift.md`
- `skill-chart-implementation.md`

---

## 6. TASK WORKFLOW — FOLLOW EVERY SESSION

### Session Start
1. Read `FOCUS.md` — understand the active task
2. Read `ai-context/current-status.md` — understand WIP state
3. Load `ai-skills/skill-analyze-wip.md` and execute it
4. Propose today's approach — no code yet
5. Wait for APPROVED before any implementation

### Implementation
1. Propose approach in plain English — no code
2. Wait for APPROVED
3. Write code with meaningful inline comments
4. Run self-criticism using `ai-skills/skill-implementation-review.md`
5. Revise all flagged issues
6. Present final code — wait for APPROVED before applying

### After Implementation
1. Update `FOCUS.md` — mark task progress and stopping point
2. Note any new issues discovered in `ai-context/current-status.md`

---

## 7. FOCUS.md — MANDATORY RULES

- Read `FOCUS.md` at the start of every task — it defines scope
- Update `FOCUS.md` immediately when task changes or new bug is reported
- Never work outside the scope defined in `FOCUS.md`
- `FOCUS.md` template and update rules are in `ai-context/ai-command.md`

---

## 8. OUT-OF-CONTEXT RECOVERY

If context is lost mid-task:
1. Re-read `FOCUS.md` — fastest recovery path
2. Re-read `ai-context/conventions.md`
3. Re-read `ai-context/boundaries.md`
4. State: "Context recovered. Current task: [task from FOCUS.md]"
5. Continue from exact stopping point

Do NOT re-read all ai-context files — FOCUS.md + conventions + boundaries
is sufficient for safe recovery.