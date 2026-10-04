---
description: Diagnose and fix a bug methodically
---

# Fix bug

1. Ask for (or read) the exact error, steps to reproduce, and expected behavior.
2. Reproduce it: write a failing test first when possible.
3. Find the root cause by reading the relevant code and real logs. State the cause before changing code.
4. Apply the smallest fix that addresses the root cause. Don't refactor unrelated code.
5. Confirm the failing test now passes and the full suite passes (`python scripts/check.py`).
6. Log the fix in `docs/PROGRESS.md`.
