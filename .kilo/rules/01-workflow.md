# Workflow rules

## Task loop
1. Plan: list files to create/modify and the approach (max ~10 bullets). Wait for approval if the task touches validation/verdict rules, money or date parsing, export formats, deletion, network or AI code, or the profile schema.
2. Implement in small steps. After each meaningful step, run `python scripts/check.py --quick`.
3. Verify: `python scripts/check.py`, plus the manual check described in the task file.
4. Record: update `docs/PROGRESS.md`; add an ADR to `docs/DECISIONS.md` if an architectural choice was made.

## Scope control
- Only work on the current task in `docs/tasks/phase-N.md`.
- If you notice a bug outside scope, log it in PROGRESS.md "Known issues". Don't fix it silently.
- Features marked V2/Future in the spec: do not implement. Only keep the data model/interfaces ready.

## Anti-hallucination
- Before using a library function, confirm it exists in the installed version (read the installed package's types/source or the official docs for that version).
- Before calling an internal function, search the codebase to confirm its name and signature. Don't assume.
- Don't claim something works unless you ran it. Say "not verified" otherwise.
- If a command fails, read the actual error output before changing code. Don't guess-and-retry repeatedly; after 3 failed attempts, stop and report.

## Context hygiene
- When the conversation gets long, update PROGRESS.md with exact next steps and recommend starting a new task.
- Keep files under ~300 lines; split by responsibility.
