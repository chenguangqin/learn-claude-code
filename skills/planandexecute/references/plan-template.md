# PLAN.md template

Copy this into `PLAN.md` in the working directory and fill it in.

```markdown
# Plan: <one-line task title>

## Goal
<one sentence: what the user wants>

## Done when
- <observable criterion 1>
- <observable criterion 2>

## Context
- <facts found while exploring: files, versions, constraints>

## Steps
- [ ] 1. <action>
      verify: <command or check that proves it worked>
- [ ] 2. <action>
      verify: <check>
- [ ] 3. <action>
      verify: <check>

## Changes
<!-- append when the plan changes: what changed and why -->
```

## Step markers

| Marker | Meaning                       |
|--------|-------------------------------|
| `[ ]`  | not started                   |
| `[>]`  | in progress (only one at a time) |
| `[x]`  | done and verified             |
| `[-]`  | dropped (say why in Changes)  |
| `[!]`  | blocked (say on what)         |

After finishing a step, append the evidence on the same item, e.g.
`- [x] 2. Add parse_args()  verify: python app.py --help  -> prints usage ✓`

## Good vs bad steps

| Bad                     | Good                                                         |
|-------------------------|--------------------------------------------------------------|
| "Fix the bug"           | "Change off-by-one in `utils.py:paginate()` (`<=` -> `<`)"   |
| "Write tests"           | "Add `tests/test_paginate.py` covering empty, 1 page, 3 pages" |
| "Make sure it works"    | verify: `python -m pytest tests/test_paginate.py -q` passes  |
| One step doing 5 things | Five steps, each with its own check                          |

Aim for 3-8 steps. More than ~10 usually means the task should be split,
or steps are too fine-grained.
