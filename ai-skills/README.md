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
| `skill-coding-logic-review.md` | Review code for business rule compliance and logic correctness | Task 2 Step 7 — after implementation | Medium |
| `skill-performance-review.md` | Identify DB, Streamlit, and pandas performance issues | Task 2 Step 7 — after implementation | Medium |
| `skill-context-drift.md` | Detect and propose updates to drifted /ai-context files | Task 3 Step 10 — end of session | Full |
| `skill-bug-diagnosis.md` | Diagnose and trace bugs through the project stack | Any time a bug is reported | Medium |
| `skill-chart-implementation.md` | Implement Plotly charts with correct session state and indicator patterns | Any Technical Analyze chart task | Medium |
| `skill-db-query-review.md` | Review SQL queries for safety, correctness, and convention compliance | Any task involving SQL or DB changes | Minimal |

---

## Integration with ai-command.md

Skills plug into the task workflow at specific steps:

```
TASK 1 — Daily Startup
  Step 3 → load @ai-skills/skill-analyze-wip.md

TASK 2 — Implementation
  Step 7 → load @ai-skills/skill-coding-logic-review.md
         → load @ai-skills/skill-performance-review.md
  Step 7 (SQL tasks only) → also load @ai-skills/skill-db-query-review.md
  Step 7 (chart tasks only) → also load @ai-skills/skill-chart-implementation.md

TASK 3 — Context Sync
  Step 10 → load @ai-skills/skill-context-drift.md

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