---
name: planandexecute
description: |
  Solve multi-step tasks with the Plan & Execute method: write an explicit
  plan first, then carry it out step by step, verifying and replanning as you go.
  Use when a task needs 3+ steps, touches several files, has unclear scope,
  or the user asks to "plan first", "make a plan", or "plan and execute".
---

# Plan & Execute

Separate **thinking about the whole task** from **doing one step at a time**.
A written plan keeps long tasks on track; verification after each step catches
mistakes while they are still cheap.

```
PLAN     understand the goal -> explore -> write PLAN.md
EXECUTE  for each step: do it -> verify it -> mark it in PLAN.md
REPLAN   a step fails or the facts change -> update PLAN.md, continue
REPORT   summarize what was done, what was verified, what is left
```

## When NOT to use

Single-command or single-edit tasks. Just do them - a plan adds nothing.

## Phase 1 - Plan

1. **Restate the goal** in one sentence and list the done-criteria
   (how you will know the task is finished).
2. **Explore before planning.** Read the relevant files, list directories,
   check versions. Plans built on guesses fall apart in step 2.
3. **Write `PLAN.md` in the working directory** using the template in
   `references/plan-template.md`. Each step must be:
   - small enough to finish and verify on its own
   - concrete: names the files, commands, or outputs involved
   - paired with a **verify** check (a command, a test, a file to inspect)
4. Order steps by dependency. Put risky or uncertain steps early.
5. If something blocks planning (missing requirement, conflicting
   instructions), stop and ask the user instead of guessing.

## Phase 2 - Execute

Work through `PLAN.md` top to bottom, **one step at a time**:

1. Mark the step `[>]` (in progress) in `PLAN.md`.
2. Do only that step.
3. Run its verify check and read the actual output.
4. Passed -> mark `[x]` and add a one-line note of the evidence.
   Failed -> do not move on; go to Phase 3.

Never mark a step done without running its check.

## Phase 3 - Replan

Replan when a check fails, a step turns out to be wrong or unnecessary,
or you learn something that changes later steps. Read
`references/replanning.md` for the decision rules. In short:

- Fix-and-retry a failed step at most twice, then rethink the approach.
- Edit `PLAN.md` instead of keeping the new plan in your head; record
  *why* it changed under `## Changes`.
- If the goal itself is no longer achievable, stop and tell the user.

## Phase 4 - Report

When all steps are `[x]`, re-check the done-criteria from Phase 1, then
reply with: what was done, how it was verified, anything skipped or left
open. Keep `PLAN.md` as the record unless the user asks to remove it.

## References

Read these with `read_file` when you need them (paths are relative to this
skill's directory):

- `references/plan-template.md` - the PLAN.md format to copy (read in Phase 1)
- `references/replanning.md` - when and how to change the plan (read on the first failure)
- `references/example.md` - a complete worked example of the whole cycle
