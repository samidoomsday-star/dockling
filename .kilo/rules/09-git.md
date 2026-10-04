# Git rules

- Commit after each completed task, never mid-broken-state.
- Conventional commits: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`, `test: ...`, `docs: ...`.
- Branch per phase: `phase-N-name`. Merge to `main` only after phase acceptance criteria pass.
- Never commit `.env`, secrets, local data, uploads, backups, or large binary/model files.
- Before large refactors or risky changes, ensure the working tree is committed so it can be reverted.
