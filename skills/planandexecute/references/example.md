# Worked example

**User:** "Write a script `wordfreq.py` that prints the 5 most common words
in a text file, and add a test for it."

## 1. Plan

Explore first:

```
$ ls            -> (empty directory)
$ python3 --version  -> Python 3.12.4
$ python3 -m pytest --version  -> No module named pytest
```

Then write `PLAN.md`:

```markdown
# Plan: wordfreq.py with test

## Goal
CLI script printing the top 5 words of a text file, plus a test.

## Done when
- `python3 wordfreq.py sample.txt` prints 5 "word count" lines
- the test passes

## Context
- Empty dir, Python 3.12, no pytest -> use unittest (stdlib)

## Steps
- [ ] 1. Create sample.txt with known word counts
      verify: cat sample.txt
- [ ] 2. Write wordfreq.py: top_words(text, n) + CLI using sys.argv
      verify: python3 wordfreq.py sample.txt
- [ ] 3. Write test_wordfreq.py (unittest) for top_words
      verify: python3 -m unittest test_wordfreq -v
- [ ] 4. Check edge case: empty file
      verify: python3 wordfreq.py empty.txt  (no crash, no output)

## Changes
```

## 2. Execute

Step 1 -> mark `[>]`, write the file, run `cat sample.txt`, mark:
`- [x] 1. ... verify: cat sample.txt -> "the" x4, "cat" x3 ✓`

Step 2 -> write the script, run it:

```
$ python3 wordfreq.py sample.txt
the 4
cat 3
The 1      <- wrong: "The" and "the" counted separately
```

The check **failed**, so the step is not done.

## 3. Replan

Local cause (missing lowercase) -> fix and re-run the same step, no plan rewrite:

```
$ python3 wordfreq.py sample.txt
the 5
cat 3
...
```

Mark `[x]`. The fix also implies punctuation (`cat.` vs `cat`) matters, which
affects later steps, so record it:

```markdown
## Changes
- Step 2: counts were case-sensitive; now lowercases and strips punctuation.
  Step 3 test now also covers "The"/"the" and "cat."/"cat".
```

Steps 3 and 4 run and pass their checks -> all `[x]`.

## 4. Report

> Created `wordfreq.py` and `test_wordfreq.py`.
> Verified: script prints the top 5 for `sample.txt`; `python3 -m unittest`
> passes 3 tests; empty file prints nothing without crashing.
> Note: pytest isn't installed, so the test uses unittest. Plan kept in `PLAN.md`.
