---
description: Break the next spec phase into small tasks and create its task file
---

# Start a phase

1. Read `docs/PROGRESS.md` to find the next phase not yet completed.
2. Read that phase in `docs/SPEC.md` (Section 17) and every SPEC section it depends on.
3. Create `docs/tasks/phase-N.md` using the format in `docs/tasks/_TEMPLATE.md`:
   - 5–15 small tasks, each completable in one session
   - For each task: goal, spec references, files likely touched, acceptance checks, tests required
   - Order tasks so every task leaves the app runnable
4. List any spec ambiguities for this phase as questions at the top of the file.
5. Do NOT write application code. Stop and ask the user to review the task file.
