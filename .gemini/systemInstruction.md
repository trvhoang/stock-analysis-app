# System Instruction — Stock Analysis App
# This file is automatically injected by Gemini Code Assist on every request.
# Keep this file concise — every line costs tokens on every prompt.
# Full documentation lives in /ai-context. Skills live in /ai-skills.

---

## 1. PROJECT SNAPSHOT

Python 3.12 · Streamlit · PostgreSQL · SQLAlchemy · pandas-ta · Plotly · Docker
Vietnamese stock market analysis app — backtests price signals, scans market for opportunities.
All prices stored as BIGINT (value × 1000) in PostgreSQL `trading_data` table.
SQL standard: `sqlalchemy.text()` + `engine.raw_connection()` + `%(param)s` bindings.
---

## 2. NON-NEGOTIABLE RULES — ALWAYS FOLLOW

### Code & SQL
- `sqlalchemy.text()` required for ALL SQL — never raw strings or f-strings
- `:param` binding required for ALL dynamic SQL values — never concatenation
- `get_engine_with_retry()` and `engine.raw_connection()` for pandas SQL reads
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
| `@ai-skills/skill-implementation-review.md` | After writing any code (Logic+Perf+SQL) |
| `@ai-skills/skill-bug-diagnosis.md` | Only when a bug/error is reported |

**INACTIVE — Never load:**
`skill-context-drift.md` · `skill-chart-implementation.md`

Load ONLY the skill needed for the current action.
Do NOT preload all skills at once.

---

## 5. FOCUS.md — MANDATORY UPDATE RULE

`FOCUS.md` exists at the project root and defines the current working task.

- **MANDATORY:** Update `@FOCUS.md` immediately if the task changes or a new bug is reported.
- Follow the detailed update process and template defined in `@ai-context/ai-command.md`.

---

## 6. SESSION STARTUP SEQUENCE

Follow the **TASK 1 — Daily Startup** sequence in `@ai-context/ai-command.md`.

---

## 7. OUT-OF-CONTEXT RECOVERY

If lost, read `@FOCUS.md` and follow the recovery steps in `@ai-context/ai-command.md`.
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