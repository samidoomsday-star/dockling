# Start here

1. Open this folder in VS Code with the Kilo Code extension.
2. Make sure Python 3.12, Git and VS Code + Kilo Code are installed (`docs/ENVIRONMENT.md` Section 1). Phase 0 (`/explore`) creates the venv and installs Docling; the project package itself comes in Phase 1.
3. Run one at a time (PowerShell): `git init` · `git add -A` · `git commit -m "chore: project docs and agent rules"`
4. In Kilo chat: `/explore` → Kilo clones Docling into `vendor/docling`, runs it the free way, tries every feature and fills `docs/EXPLORATION_REPORT.md`.
4b. Review the report (share it with Claude for suggestions), decide what to build, and confirm/adjust Phases 1+ in `docs/SPEC.md`. Then `/start-phase` for Phase 1.
5. Repeat `/next-task` → review → test manually.
6. End of phase: `/verify-phase` then `/security-review` → fix → merge.
7. New session or lost track: `/resume`.

Docs: see the document map in `AGENTS.md`. `docs/SPEC.md` is the source of truth.
Phase 1 must scaffold inside existing folders without overwriting AGENTS.md files.

Before Phase 1: read `docs/SPEC.md` Appendix A (what research changed) and answer Appendix B (open questions).
Never put real client statements in this repo; tests use synthetic statements from `tools/synth`.
