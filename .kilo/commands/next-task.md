---
description: Implement the next unchecked task in the current phase
---

# Next task

1. Read `docs/PROGRESS.md` and the current `docs/tasks/phase-N.md`.
2. Pick the first unchecked task. Read only its referenced SPEC sections.
3. Post a short plan (files, approach, tests). If the task touches validation/verdict rules, money or date parsing, export formats, deletion, network or AI code, or the profile schema, wait for approval.
4. Implement. Run `python scripts/check.py --quick` after significant steps.
5. Write the required tests.
6. Run `python scripts/check.py`. Fix failures by reading real errors.
7. Check the task off, update `docs/PROGRESS.md` (files changed, how to verify manually, issues).
8. Commit with a conventional commit message.
9. Stop. Summarize what was done and what's next.
