# FOCUS.md — Active Task Context
# LOCATION: project root (same level as docker-compose.yml)
# PURPOSE: Single source of truth for the current working task.
#          Reference with @FOCUS.md in every Gemini prompt.
#          Updated at session start and whenever task changes. 
# MAINTAINED BY: AI tool — updated per systemInstruction.md Section 5 rules
# Last Updated: 2026-04-11

---

## Current Task
Implement: Bollinger Bands logic and visualization

## Task Type
[X] New feature
[] Bug fix
[ ] New requirement
[ ] Review code logic

## Task Source
[ ] From current-status.md WIP section
[ ] New requirement from human this session
[ ] Bug reported this session
[ ] Business logic in business-logic.md and implementation logic in code
[X] WIP item from current-status.md
---

## Target Files
i:\VscProjects\stock-analysis-app\app\apis\routes.py

## Out of Scope — Do Not Touch
app/common_queries.py
app/data_preparation.py

---

## Key Rules for This Task
- Propose approach before code
- Wait for APPROVED
- Self-criticism after

---

## Technical Notes
- API should allow triggering the ZIP download and DB ingestion process.
- Need to ensure thread-safety or prevent multiple simultaneous data prep tasks.

---

## Acceptance Criteria
- [ ] Analyze page loads without traceback
- [ ] Final Advice section works correctly

---

## Blocking Rules (from boundaries.md)

---

## Skills to Load for This Task
@ai-skills/skill-bug-diagnosis.md

---

## Session Progress
- Implemented `POST /api/prepare-data` endpoint with `BackgroundTasks` support.
- Refactored `data_preparation.py` to support headless ingestion via a shared `threading.Lock`.
- Fixed Streamlit threading warnings by making `log_progress` context-aware.