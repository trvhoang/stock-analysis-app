# ai-command.md
# ⚠️ READ THIS FILE FIRST BEFORE ANYTHING ELSE ⚠️
#
# PURPOSE: This file contains the master command sequence for any AI tool
# working on this project. It must be executed at the start of every work
# session without exception.
#
# LOCATION: /ai-context/ai-command.md
# MAINTAINED BY: Project Owner — do not modify unless instructed
# LAST UPDATED: [update this date when file changes]

---

## 📌 HOW TO USE THIS FILE

This file contains three tasks:

| Task | When to Run | Purpose |
|------|-------------|---------|
| **TASK 1 — Daily Startup** | Every new session, always first | Load context, understand WIP, propose approach |
| **TASK 2 — Implementation** | After Task 1 is approved | Write code, self-criticize, revise, present |
| **TASK 3 — Context Sync** | After Task 2 is approved and applied | Review all /ai-context files and propose updates to keep them accurate |

You MUST complete Task 1 fully before starting Task 2.
You MUST complete Task 2 fully before starting Task 3.
You MUST wait for explicit human approval at every gate marked 🟡.
You MUST NOT skip, combine, or reorder any steps.

---

## 🧰 ACTIVE SKILL REGISTRY

This project uses an `/ai-skills` folder containing focused execution guides.
Skills reduce token usage by scoping each action precisely.
Read `/ai-skills/README.md` for the full index.

The following skills are **ACTIVE** and must be loaded at the step indicated:

| Skill File | Load At | Purpose |
|------------|---------|---------|
| `skill-analyze-wip.md` | Task 1 Step 3 | Structured WIP extraction and prioritization |
| `skill-implementation-review.md` | Task 2 Step 7 | Comprehensive Logic, Perf, and SQL review |
| `skill-bug-diagnosis.md` | Any time a bug is reported | Root cause analysis and fix proposal |

**Rules for skill usage:**
- Load ONLY the skill(s) relevant to the current step — do not pre-load all skills
- Inactive skills must never be referenced, loaded, or suggested as alternatives
- If a task falls outside all active skills, proceed using /ai-context files directly
- Skills extend this command file — they do not replace any step in it

---

---

# 🌅 TASK 1 — DAILY STARTUP COMMAND

*Run this at the beginning of every work session without exception.*

---

## STEP 1 — READ ALL CONTEXT FILES

Read every file inside the `/ai-context` folder in this exact order:

1. `README.md`
2. `project-overview.md` ... [through] ... 10. `current-status.md`

**Action:** Sequential reading required. Note patterns and constraints. Flag ambiguities.

When done, confirm with exactly this message:
> "✅ STEP 1 COMPLETE — I have read all /ai-context files."

---

## STEP 2 — ASK YOUR QUESTIONS

Before proceeding, surface every question, uncertainty, or ambiguity
you encountered while reading all context files.

Format your questions exactly like this:

---

**❓ Questions Before We Begin**

`[filename where confusion arose]` — [your question]

> Example:
> `architecture.md` — The diagram shows Module A calls Module B,
> but the code suggests the reverse. Which is correct?

---

Rules for this step:
- Ask ALL questions now — do not ask questions mid-session later
- Number every question clearly starting from 1
- Group questions by file or topic for clarity
- Be specific — vague questions are not acceptable
- If you have zero questions, state:
  > "No questions — all context files are fully clear."
  and briefly explain what gave you full confidence.

🟡 **GATE — Wait for human answers before moving to Step 3.**

---

## STEP 3 — ANALYZE WORK IN PROGRESS

**📌 SKILL INSTRUCTION:**
Load and execute `@ai-skills/skill-analyze-wip.md` for this step.
That skill defines the exact execution process, output format, and
early exit condition. Follow it completely.

Do NOT proceed using a generic WIP analysis — the skill is mandatory here.

---

## STEP 4 — PROPOSE TODAY'S APPROACH (NO CODE, NO CHANGES)

Based on everything you have read and the WIP analysis, propose a
clear approach for today's work session.

Present your proposal in this exact structure:

---

**📋 TODAY'S WORK PROPOSAL**

**Objective:**
One sentence — what we are trying to achieve today.

**Scope:**
What is included in today's work.
What is explicitly out of scope for today.

**Proposed Approach:**
Step-by-step explanation of HOW you plan to tackle the work.
Explain the logic and reasoning behind each step.
Reference specific files, modules, or functions by name.
Do not write any code — describe the approach in plain English only.

**Dependencies:**
Anything that must be true or completed before this work can proceed.
Flag any dependency that is currently unmet.

**Risk Areas:**
Parts of the codebase or logic that need extra caution.
Explain why each area is risky.

**What I Will NOT Do:**
Explicitly state what you are avoiding.
Reference specific rules from `boundaries.md` and `conventions.md`
that guided these exclusions.

**Open Questions for Human:**
Anything still unclear that would affect the approach.
If none, state: "No open questions — approach is fully defined."

---

⛔ HARD RULES FOR THIS STEP:
- Do NOT write any code
- Do NOT modify any files
- Do NOT make implementation decisions without approval
- This step is a proposal only

End your proposal with exactly this message:
> "🟡 AWAITING YOUR APPROVAL — Please review the approach above.
> Reply APPROVED to proceed to Task 2, or give feedback to adjust."

🟡 **GATE — Task 1 is complete only after human replies APPROVED.**

---

---

# 🛠️ TASK 2 — IMPLEMENTATION COMMAND

*Begin this task only after Task 1 is fully complete and approach is approved.*

---

## STEP 5 — SELECT AND CONFIRM TARGET TASK

From the WIP analysis in Step 3, identify the single highest priority task
that aligns with the approved approach from Step 4.

Present it in this exact structure:

---

**🎯 TARGET TASK FOR IMPLEMENTATION**

**Task Name:** [exact name from current-status.md]
**Priority Reason:** [why this task is first based on project goals]
**Affected Files:** [list every file that will be touched]
**Affected Modules / Functions:** [list specific functions or classes]
**Expected Outcome:** [what "done" looks like for this task]
**Out of Scope:** [what will NOT be touched even if related]

---

End with:
> "Is this the correct task to implement?
> Reply YES to proceed or tell me which task to focus on instead."

🟡 **GATE — Wait for confirmation before moving to Step 6.**

---

## STEP 6 — DETAILED IMPLEMENTATION WITH CODE AND COMMENTS

Write the full proposed implementation for the confirmed task.

Follow this exact structure for every file you touch:

---

**📦 IMPLEMENTATION PROPOSAL**

**Overview:**
2-3 sentences explaining what this implementation does and why
it is structured this way. Reference the relevant rule from
`conventions.md` or pattern from `architecture.md` that guided
the approach.

---

For each file that needs to be changed, present it like this:

#### 📄 File: `path/to/filename.py`

**What changes and why:**
Explain the change in plain English before showing any code.
State which existing function/class is affected and how.

**Proposed Code:**

```python
# [write full proposed code block here with full context]
# not just changed lines — include enough surrounding code
# so the change is fully understandable in isolation
```

---

**Inline Comment Standard — STRICTLY ENFORCED:**

Every non-trivial line or block MUST have a comment that explains:
- WHAT it does (brief)
- WHY it does it this way (the reasoning, not just the action)
- Any edge case or assumption being made

❌ BAD comment — states the obvious, adds no value:
```python
# increment counter
count += 1
```

✅ GOOD comment — explains the why and the edge case:
```python
# Increment only after validation passes to avoid counting
# failed attempts toward the rate limit threshold (see business-logic.md §3.2)
count += 1
```

Apply the GOOD standard to every comment in your implementation.
If a line is truly self-explanatory, no comment is needed — but
err on the side of over-explaining rather than under-explaining.

---

## STEP 7 — SELF-CRITICISM REPORT

After writing the implementation, you MUST critically evaluate
your own code before presenting anything to the human.

Do NOT skip this step.
Do NOT be lenient with yourself.
Treat this as a senior engineer doing a rigorous code review
of a junior developer's pull request.

**📌 SKILL INSTRUCTION — Load the following active skills for this step:**

**Always load (every implementation):**
- `@ai-skills/skill-implementation-review.md` — Unified Logic, Performance, and SQL review.

**Do NOT load:**
- `skill-context-drift.md` — INACTIVE, disabled by project owner
- `skill-chart-implementation.md` — INACTIVE, disabled by project owner

Execute each loaded skill fully and in order.
Combine their outputs into a single unified self-criticism report.

Present your self-criticism in this exact format:

---

**🔍 SELF-CRITICISM REPORT**

#### 1. Logic & Business Rule Review
*[Output from skill-coding-logic-review.md — full compliance table and findings]*

#### 2. Performance Review
*[Output from skill-performance-review.md — full findings table]*

#### 3. SQL / Database Review *(skip if no SQL in this implementation)*
*[Output from skill-db-query-review.md — full compliance table and findings]*

#### 4. Comment Quality Review

Checklist:
- [ ] Are all comments meaningful and explain the WHY not just the WHAT?
- [ ] Are there obvious or redundant comments that add no value?
- [ ] Are there complex blocks with no explanation at all?
- [ ] Do comments stay in sync with what the code actually does?
- [ ] Are there any misleading or outdated comments carried over from existing code?

**Comment Issues Found:**
List any comment quality problems with the line or block affected.
If none found, write:
> "All comments meet the required standard."

---

#### 5. Overall Self-Assessment

Rate your implementation honestly. Do not inflate scores:

| Category        | Score (1–5) | Reason                         |
|-----------------|-------------|--------------------------------|
| Logic           | X / 5       | [brief honest reason]          |
| Performance     | X / 5       | [brief honest reason]          |
| SQL Quality     | X / 5       | [or N/A if no SQL]             |
| Comment Quality | X / 5       | [brief honest reason]          |
| **Overall**     | **X / 5**   | [one sentence honest summary]  |

A score of 5/5 overall requires zero issues found across all categories.
Be honest — a 3/5 with clear reasoning is more valuable than a false 5/5.

---

## STEP 8 — REVISED IMPLEMENTATION (IF NEEDED)

If the Self-Criticism Report found ANY of the following, you MUST
revise the implementation before presenting it to the human:

- Any logic issue regardless of severity
- Any performance issue rated MEDIUM or HIGH
- Any convention violation
- Any comment rated as poor quality

Rules for revision:
- Fix every item flagged in Step 7
- Do NOT introduce new changes beyond what was flagged
- Do NOT change code that was not identified as problematic
- After fixing, re-run the Step 7 checklist mentally to confirm fixes hold

Present the revised code in the same format as Step 6, then add:

---

**✅ REVISION SUMMARY**

| Issue Found in Step 7 | How It Was Resolved |
|-----------------------|---------------------|
| [issue description]   | [fix applied]       |
| [issue description]   | [fix applied]       |

**Net change from first draft to final:**
[Clearly state what improved so the human can verify each fix]

---

If Step 7 found no issues requiring revision, skip this step and state:
> "No revision needed — implementation passed all self-criticism checks."

---

## STEP 9 — FINAL IMPLEMENTATION PRESENTATION

Present the final, clean, fully commented implementation ready
for human review and approval.

Structure the final presentation exactly like this:

---

**🚀 FINAL IMPLEMENTATION — READY FOR REVIEW**

**Task Completed:** [exact task name from current-status.md]
**Files Modified:** [list every file with its path]
**Self-Criticism Score:** [overall score from Step 7]
**Revisions Made:** [yes/no — if yes, summarize in one line]

**Summary of Changes:**
3-5 sentences explaining what was built, why it was built this way,
and how it connects to the broader project architecture.

---

[Final clean code blocks for each file, fully commented]

---

**How to Test This:**
Step-by-step instructions to manually verify the implementation works.
Include: what to run, what input to use, what output to expect.

**What to Watch For:**
Any behavior, side effects, or edge cases the human should pay
attention to during testing that might not be immediately obvious.

**Follow-up Recommendations:**
Optional — any related improvements noticed during implementation
that are out of scope today but worth noting for the backlog.

---

End with exactly this message:
> "🟡 AWAITING YOUR APPROVAL — Please review the implementation above.
> Reply APPROVED to apply changes, REQUEST CHANGES to revise,
> or REJECT to discard and re-approach the task entirely."

🟡 **GATE — Do not apply any changes to actual files until human replies APPROVED.**

---

---

# 📚 TASK 3 — CONTEXT SYNC COMMAND

*Begin this task only after Task 2 is fully complete and the implementation
has been applied to the codebase with human approval.*

---

## STEP 10 — RE-READ ALL CONTEXT FILES FOR DRIFT DETECTION

Re-read every file inside the `/ai-context` folder in this exact order.
**Skip `ai-command.md` — this file is never reviewed or modified in this task.**

1. `README.md`
2. `project-overview.md`
3. `architecture.md`
4. `business-logic.md`
5. `conventions.md`
6. `decisions.md`
7. `boundaries.md`
8. `glossary.md`
9. `workflows.md`
10. `current-status.md`

**📌 SKILL NOTE:**
`skill-context-drift.md` is INACTIVE for this project.
Execute this step manually using the instructions below —
do NOT attempt to load or reference that skill file.

While reading, compare each file's content against everything that happened
during today's session — the questions answered in Step 2, the implementation
built in Task 2, any discoveries made, any decisions taken, any new patterns
introduced.

Silently flag every place where the file content is:
- **Outdated** — describes something that has changed
- **Incomplete** — missing something new that now exists
- **Inaccurate** — contradicts the current state of the codebase
- **Stale** — references a task, issue, or status that is no longer true
- **Missing** — a new concept, term, pattern, or decision not documented anywhere

Do NOT output anything yet. Collect all findings first.

When done, confirm with:
> "✅ STEP 10 COMPLETE — All /ai-context files reviewed for drift."

---

## STEP 11 — PRESENT THE DRIFT REPORT

Present a structured report of everything found in Step 10.

Format the report exactly like this:

---

**📊 CONTEXT DRIFT REPORT**

**Session Reference:**
[One sentence summarizing what was implemented in Task 2 that
forms the basis for this review]

---

For each file that has drift, present it like this:

#### 📄 File: `filename.md`

**Drift Type:** [Outdated / Incomplete / Inaccurate / Stale / Missing]

**Current Content (what it says now):**
> [Quote or describe the specific section, line, or entry that is affected]

**What Changed:**
[Explain clearly what happened during today's session that makes
this content no longer accurate or complete]

**Proposed New Content:**
[Write the exact replacement or addition you are proposing.
Be precise — show the exact wording, not a vague description of it]

**Impact if Not Updated:**
[What would happen if a future AI tool read this file as-is —
what would it misunderstand, do wrong, or be confused about]

---

Repeat this block for every drifted section found across all files.

If a file has no drift at all, state:
> "`filename.md` — No drift detected. Content accurately reflects current state."

After presenting all files, add a summary:

---

**📋 DRIFT SUMMARY**

| File | Drift Found | Sections Affected |
|------|-------------|-------------------|
| `README.md` | Yes / No | [section names or "—"] |
| `project-overview.md` | Yes / No | [section names or "—"] |
| `architecture.md` | Yes / No | [section names or "—"] |
| `business-logic.md` | Yes / No | [section names or "—"] |
| `conventions.md` | Yes / No | [section names or "—"] |
| `decisions.md` | Yes / No | [section names or "—"] |
| `boundaries.md` | Yes / No | [section names or "—"] |
| `glossary.md` | Yes / No | [section names or "—"] |
| `workflows.md` | Yes / No | [section names or "—"] |
| `current-status.md` | Yes / No | [section names or "—"] |

**Total files with drift:** X / 10
**Total sections requiring update:** X

---

End with:
> "🟡 AWAITING YOUR REVIEW — Please review the drift report above.
> Reply APPROVED to proceed with applying all proposed changes,
> SELECTIVE to choose which changes to apply,
> or REJECT to discard all proposed changes."

🟡 **GATE — Wait for human response before moving to Step 12.**

---

## STEP 12 — APPLY APPROVED CONTEXT UPDATES

Apply only the changes the human has approved from Step 11.

Rules for this step:
- Apply changes **file by file** — do not batch all files into one action
- For each file, show the exact before and after of every changed section
- Do NOT rewrite entire files — make surgical, targeted edits only
- Do NOT change the tone, structure, or style of the file beyond what was proposed
- Do NOT modify `ai-command.md` under any circumstance
- Preserve all existing content that was not flagged for change
- If approved changes in one file affect another file, flag it before applying

For each file being updated, present it like this:

---

#### ✏️ Updating: `filename.md`

**Change 1 of X — [brief label for this change]**

**Before:**
```
[exact current content being replaced]
```

**After:**
```
[exact new content replacing it]
```

**Reason:** [one sentence why this change was needed]

---

After all changes are applied, confirm:
> "✅ File `filename.md` updated — X change(s) applied."

Repeat for every approved file.

---

## STEP 13 — MANDATORY CURRENT-STATUS UPDATE

Regardless of what else was or was not updated, `current-status.md`
MUST always be updated at the end of every session.

Update `current-status.md` to reflect the following with precision:

---

**✅ Completed This Session:**
[List every task fully completed today with outcome]

**🔄 Still In Progress:**
[List any tasks started but not finished, with exact stopping point
and what remains — be specific enough that a new AI can resume
without asking questions]

**⏳ Pending — Not Started:**
[List tasks queued for future sessions in priority order]

**🐛 New Issues Discovered:**
[List any bugs, design flaws, or technical debt uncovered during
today's session that need future attention — include file and
function references where relevant]

**💡 Decisions Made Today:**
[List any architectural, convention, or design decisions taken
during today's session that should be remembered]

**📅 Last Updated:**
[Today's date and brief session summary in one sentence]

---

After updating, confirm with:
> "✅ STEP 13 COMPLETE — current-status.md is fully up to date."

---

## STEP 14 — CONTEXT SYNC COMPLETION REPORT

Present a final summary of the entire Task 3 operation.

---

**🎉 CONTEXT SYNC COMPLETE**

**Files Reviewed:** 10 / 10
**Files Updated:** X
**Sections Changed:** X
**current-status.md:** Updated ✅

**What Was Synced:**
[Brief bullet summary of the most important changes made across all files]

**What Stayed the Same:**
[List files with no drift — confirms they were reviewed, not ignored]

**Recommended Follow-ups:**
[Any documentation gaps that could not be filled today because more
information is needed — flag these for the next session]

---

End with exactly this message:
> "✅ TASK 3 COMPLETE — All /ai-context files are now accurate and
> up to date. The project context is ready for the next session.
> This session is now fully closed."

---

⛔ HARD RULES FOR TASK 3:

- Never modify `ai-command.md` — it is explicitly excluded from this task
- Never rewrite a file entirely — only update what drifted
- Never invent new content not grounded in what actually happened this session
- Never remove documented decisions or history — only add to or correct them
- Never apply a change the human did not explicitly approve
- If unsure whether something drifted, flag it in the report and let the human decide
- `current-status.md` must always be updated — it is never optional

---

---

# 🔒 GLOBAL RULES — ALWAYS ACTIVE FOR THE ENTIRE SESSION

These rules are permanently active from the moment this file is read
until the session ends. They override any other instruction.

1. **Never implement anything not in the approved plan from Step 4**
2. **Never apply code to files until the human explicitly replies APPROVED**
3. **Never implement more scope than the confirmed task from Step 5**
4. **Never skip the self-criticism step even when confident in the output**
5. **Never modify any file inside `/ai-context` outside of Task 3 Step 12
   unless explicitly instructed by the human**
6. **Never remove existing comments without replacing them with better ones**
7. **If you discover an unexpected design flaw mid-implementation, STOP
   immediately, report it clearly, and wait for instruction before continuing**
8. **If a task is too large to implement safely in one step, STOP and propose
   breaking it into smaller subtasks before writing any code**
9. **If context becomes unclear mid-session, re-read the relevant
   `/ai-context` file before continuing — do not guess**
10. **Never close a session without completing Task 3 — context files
    must always reflect the current state of the project**
11. **`ai-command.md` is read-only for AI tools at all times —
    it may never be modified, rewritten, or suggested for changes
    under any circumstance**
12. **Never load, reference, or suggest any skill listed as INACTIVE
    in the Active Skill Registry — inactive skills do not exist for
    this session regardless of what the /ai-skills folder contains**
13. **Always load the correct active skill at the step it is registered
    for — never skip a skill load or substitute it with a generic approach**

---

# ✅ MASTER SESSION CHECKLIST

Use this to confirm all steps are complete before applying any code:

**Task 1 — Daily Startup**
- [ ] All `/ai-context` files read in full (Step 1)
- [ ] All questions asked and answered (Step 2)
- [ ] WIP analysis presented and acknowledged (Step 3)
- [ ] **IF no WIP detected → Early Exit triggered. Steps below are skipped.**
- [ ] Approach proposed and approved by human (Step 4) ← skipped if no WIP

**Task 2 — Implementation** ← skipped entirely if no WIP
- [ ] Target task confirmed by human (Step 5)
- [ ] Full implementation written with meaningful comments (Step 6)
- [ ] Self-criticism report completed honestly (Step 7)
- [ ] Revisions applied for all flagged issues (Step 8)
- [ ] Final implementation presented and approved by human (Step 9)

**Task 3 — Context Sync** ← skipped entirely if no WIP
- [ ] All /ai-context files re-read and compared against session activity (Step 10)
- [ ] Drift report presented to human for review (Step 11)
- [ ] Approved changes applied file by file (Step 12)
- [ ] current-status.md updated to reflect completed session (Step 13)
- [ ] Context sync completion report presented (Step 14)

**Only after all applicable boxes are checked is the session fully and correctly closed.**

---

*This file is the master command file for AI-assisted development on this project.*
*Do not modify this file unless explicitly instructed by the project owner.*
*Version this file in git — every change to it is a meaningful project decision.*