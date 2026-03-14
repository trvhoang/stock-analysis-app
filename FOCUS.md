# FOCUS.md — Active Task Context
# LOCATION: project root (same level as docker-compose.yml)
# PURPOSE: Single source of truth for the current working task.
#          Reference with @FOCUS.md in every Gemini prompt.
#          Updated at session start and whenever task changes. 
# MAINTAINED BY: AI tool — updated per systemInstruction.md Section 5 rules
# Last Updated: 2026-03-11

---

## Current Task
Refactor: Analyze Page > Final Advice message

## Task Type
[ ] New feature
[] Bug fix
[X] Refactor
[ ] New requirement
[ ] Review code logic

## Task Source
[ ] From current-status.md WIP section
[ ] New requirement from human this session
[ ] Bug reported this session
[ ] Business logic in business-logic.md and implementation logic in code
[X] Refactor requirement from human this session
---

## Target Files
i:\VscProjects\stock-analysis-app\app\analyze_visualization.py

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
- provide_advice currently returns a string, but caller expects tuple (display, trend)
- generate_technical_advice already returns tuple

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