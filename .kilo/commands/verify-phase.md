---
description: Check the current phase against spec acceptance criteria
---

# Verify phase

1. Read the current phase acceptance criteria in `docs/SPEC.md` (Section 17) and `docs/tasks/phase-N.md`.
2. Run `python scripts/check.py` and `python -m stmtconv selftest`.
3. For each acceptance criterion: state PASS / FAIL / NOT VERIFIED with evidence (test name, command output, or manual steps).
4. Compare implemented features against every SPEC section referenced by the phase. List anything missing or implemented differently.
5. Check for leftovers: TODOs, print() outside cli, float used for money, bare except, bank names/keywords/prices in Python instead of profiles/config, network imports outside extract/ai_engine.py, client-like data in fixtures or logs, golden files changed without explanation.
6. Write the report into `docs/PROGRESS.md` under the phase. Don't fix anything yet; ask the user which issues to fix.
