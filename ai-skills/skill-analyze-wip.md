# skill-analyze-wip.md
# SKILL: Analyze Work In Progress Tasks
#
# PURPOSE: Extract, structure, and prioritize all WIP tasks from
#          current-status.md aligned with project goals
# TRIGGER: Task 1 Step 3 — every session startup after context files are read
# READS FROM: current-status.md, project-overview.md
# PRODUCES: Structured WIP summary with priority assessment
# TOKEN SCOPE: Minimal — reads only 2 files
# LAST UPDATED: 2024-05-24

---

## SKILL OVERVIEW

This skill performs a focused, structured extraction of all work items from
`current-status.md` and maps them against the project goals in
`project-overview.md` to produce a prioritized, actionable WIP summary.

It does NOT propose solutions, write code, or make decisions — it only
reads, structures, and prioritizes what already exists in the status file.

Scope IN: Active tasks, pending tasks, known issues, last session context,
          priority ordering.
Scope OUT: Architecture decisions, convention rules, implementation details.

---

## PRE-CONDITIONS

Before executing this skill, verify:
- [ ] Task 1 Step 1 is complete — all /ai-context files have been read
- [ ] Task 1 Step 2 is complete — all questions have been asked and answered
- [ ] `current-status.md` exists and is accessible

If any pre-condition is not met, report which one is missing and stop.

---

## EXECUTION STEPS

### STEP 1 — EXTRACT RAW WORK ITEMS

Re-read `current-status.md` with full focus.

Silently extract every item found under:
- Section 2: Work In Progress (WIP)
- Section 3: Known Issues & Technical Debt
- Section 4: Next Steps & Priorities

Do NOT extract from "Recently Completed Tasks" — those are done and
are irrelevant to today's session.

Do NOT output anything yet.

---

### STEP 2 — CLASSIFY EACH ITEM

For each item extracted in Step 1, silently classify it as:

- **ACTIVE** — currently in progress, has been started
- **PENDING** — queued but not yet started
- **BLOCKED** — cannot proceed due to a dependency or issue
- **ISSUE** — a known bug, gap, or technical debt item

Use only the information present in `current-status.md`.
Do NOT infer or assume status not explicitly stated.

---

### STEP 3 — ASSESS PRIORITY

Cross-reference each item against `project-overview.md` Section 4
(Core Functionality & Flow) to assess business priority.

Priority rules for this project:
1. Items that block other items rank highest
2. Items that affect core pages (Analyze, Suggestion, Technical Analyze)
   rank above cosmetic or minor items
3. Technical Analyze page indicators (Stochastic, Bollinger, Ichimoku)
   are high-value features currently in progress
4. Chart rendering fixes (non-trading day gaps) are UX improvements —
   medium priority unless blocking a feature
5. Known issues rank by severity: HIGH > MEDIUM > LOW

---

### STEP 4 — PRESENT THE WIP SUMMARY

Present the full structured output using this exact format:

---

**🔄 WORK IN PROGRESS SUMMARY**

**1. Active Tasks**

| # | Task Name | Current State | Blocker (if any) |
|---|-----------|---------------|------------------|
| 1 | [name]    | [state]       | [blocker or —]   |

**2. Pending Tasks**

| # | Task Name | Depends On |
|---|-----------|------------|
| 1 | [name]    | [dep or —] |

**3. Known Issues**

| # | Issue | Severity | Affected File / Function |
|---|-------|----------|--------------------------|
| 1 | [issue] | HIGH/MED/LOW | [file or —] |

If none: "No known issues at this time."

**4. Last Session Context**
[One paragraph — what was last completed, where work stopped,
what file or function was last touched. Be specific.]

**5. Priority Assessment for Today**

| Priority | Task | Reason |
|----------|------|--------|
| 1st | [task name] | [why this is most important today] |
| 2nd | [task name] | [why] |
| 3rd | [task name] | [why] |

**What would be blocked if Priority 1 is not done:**
[Specific answer — not "nothing" unless that is genuinely true]

---

### STEP 5 — EARLY EXIT CHECK

After presenting the WIP summary, apply this check:

**IF** all of the following are true:
- Active Tasks table is empty
- Pending Tasks table is empty
- Known Issues table is empty

**THEN** output exactly:

> "⚪ NO ACTIVE WORK DETECTED — current-status.md shows no tasks or issues.
> Please assign a new task, correct the status file, or close the session."

🟡 GATE — If early exit triggered, wait for human instruction.
         Do NOT proceed to Step 4 of ai-command.md.

**IF** any work exists, confirm with:
> "✅ SKILL COMPLETE — WIP analysis ready. Proceeding to Step 4."

🟡 GATE — Wait for human acknowledgement before Step 4.

---

## OUTPUT FORMAT

The complete output of this skill is the table-structured WIP Summary
from Step 4 above, followed by the Early Exit check result.

No prose summaries. No recommendations. No code. Tables and
specific references only.

---

## QUALITY CHECKLIST

Before presenting output, verify:
- [ ] Every task name is copied verbatim from `current-status.md`
- [ ] No tasks have been invented that do not appear in the file
- [ ] Priority assessment references specific project pages or goals
- [ ] "Last Session Context" names at least one specific file or function
- [ ] Blocked tasks have their blocker explicitly stated
- [ ] If Known Issues section is empty in the file, the table reflects that

---

## HARD RULES FOR THIS SKILL

- NEVER invent tasks not found in `current-status.md`
- NEVER skip the early exit check
- NEVER propose solutions or write code in this skill
- NEVER read architecture.md, conventions.md, or other files —
  this skill is scoped to current-status.md and project-overview.md only
- NEVER classify a completed task as WIP — check "Recently Completed" section
  and exclude everything in it
- ALWAYS quote task names exactly as written in the source file

---

## INTEGRATION WITH OTHER SKILLS

**Feeds into:**
- `ai-command.md` Task 1 Step 4 — Today's Work Proposal uses this output
- `skill-implementation-review.md` — target task comes from this output

**Should NOT be combined with:**
- `skill-coding-logic-review.md` — that runs after implementation, not before
- `skill-context-drift.md` — that runs at end of session, not start

**Can be chained with:**
- `skill-bug-diagnosis.md` — if a known issue needs immediate triage

---

## TOKEN BUDGET GUIDANCE

Token Scope: **Minimal**

Files read: `current-status.md` + `project-overview.md` only.

To stay within budget:
- Do NOT re-read architecture.md, conventions.md, or business-logic.md
  for this skill — they are already loaded from Task 1 Step 1
- Reference project-overview.md Section 4 only — do not re-read the full file
- This skill should complete in a single response with no back-and-forth