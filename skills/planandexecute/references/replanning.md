# Replanning rules

A plan is a hypothesis. Change it as soon as the evidence says it is wrong -
but change it deliberately, in `PLAN.md`, not silently.

## Decide what kind of problem it is

| Situation                                        | Action                                          |
|--------------------------------------------------|-------------------------------------------------|
| Step failed for a local reason (typo, wrong flag) | Fix and re-run the same step's check            |
| Same step failed twice                           | Stop retrying. Re-read the error, re-explore, rewrite this step (or split it) |
| Step succeeded but revealed new facts            | Update later steps that depended on old assumptions |
| A step is unnecessary                            | Mark `[-]`, note why in `## Changes`            |
| A missing step is discovered                     | Insert it where it belongs in the order         |
| Blocked on something outside your control (credentials, missing input, user decision) | Mark `[!]`, finish any independent steps, then ask the user |
| The goal itself can't be met as stated           | Stop. Explain what you found and offer options  |

## How to record a change

Append under `## Changes` in `PLAN.md`:

```markdown
## Changes
- Step 3: `pip install` fails on py3.9 (needs >=3.10). Added step 2a:
  create venv with python3.12. Steps 3-5 unchanged.
```

One line of *what* and *why* is enough. This keeps the user able to follow
how the work actually went.

## Anti-patterns

- **Retry loop**: running the same failing command again hoping for a different result.
- **Silent drift**: doing different work than the plan says without updating it.
- **Plan abandonment**: dropping `PLAN.md` halfway and continuing ad hoc.
- **Faking progress**: marking `[x]` because the code "looks right" without running the check.
- **Over-replanning**: rewriting the whole plan for a one-step fix. Change only what the new facts affect.
