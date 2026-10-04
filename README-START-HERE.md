# Dockling — start here

Dockling is being developed here in Codex, following the original phases 0–10. Phase 1 provides the working foundation: command-line help, setup checks, configuration, private logs and model downloads. Statement conversion and order handling arrive in later phases.

## What you need to do now

Review the Phase 1 result. You can keep developing here without installing anything on your other device yet. No LLM API key is needed. The optional custom OpenAI-compatible BYOK model picker and supported effort settings remain planned for Phase 9.

## Where the work is

The current code is on GitHub branch `phase-1-foundation`. `main` still contains the original starter; these branches have not been merged. Think of this branch as the saved project version you would open in a local IDE. GitHub carries code and instructions; each device separately installs Python, dependencies and local models.

- [Progress and evidence](docs/PROGRESS.md)
- [Installation and update guide](docs/ENVIRONMENT.md)
- [Phase 1 scope](docs/tasks/phase-1.md)
- [Original specification](docs/SPEC.md)
- [Cloud/GitHub/device workflow and BYOK plan](docs/CODEX-PROJECT-PLAN.md)
- [Exploration findings](docs/EXPLORATION_REPORT.md)

For cloud setup, run `bash scripts/install-linux.sh`, then `.venv/bin/python -m stmtconv models download`. Check setup with `.venv/bin/python -m stmtconv doctor` and development with `.venv/bin/python scripts/check.py`.

Windows instructions are provided in the guide; they have not yet been executed on a Windows device. Use synthetic documents during development. Keys, real statements, installed dependencies and model binaries stay outside GitHub.

The `.kilo/` files are historical reference. You do not need Kilo Code. Active development instructions are in `AGENTS.md`.
