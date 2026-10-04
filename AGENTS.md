# AGENTS.md — Statement Converter (`stmtconv`)

Local Windows CLI the owner uses to run a done-for-you service: client bank/credit-card statements (digital PDFs, scans, photos) → validated Excel, QuickBooks CSV, Xero CSV and OFX, with a balance-verification report, human review loop, delivery package and deletion certificate. Local-first; cloud AI optional, consent-gated, paid tier only.

## Document map (read only what the task needs)
| File | Use it for | Authority |
|---|---|---|
| `docs/SPEC.md` | All requirements, business rules, phases (Section 17) | **Source of truth** |
| `docs/EXPLORATION_REPORT.md` | Phase 0 findings: how Docling really behaves on this laptop | Decides changes to Phases 1+ |
| `docs/DECISIONS.md` | Why architectural choices were made (ADRs) | Binding unless superseded |
| `docs/TECH_ARCHITECTURE.md` | Module structure, dependency direction, data flows, engine details | Must follow |
| `docs/USER_FLOWS.md` | Operator journeys and edge cases (build + e2e tests) | Derived from SPEC |
| `docs/ENVIRONMENT.md` | Tooling, env variables, config files, local setup | Must follow |
| `docs/RESEARCH.md` | Market, format and provider facts behind the SPEC | Background only |
| `docs/PROGRESS.md` | Current phase, task log, known issues, verification reports | Update every task |
| `docs/tasks/phase-N.md` | Task breakdown for the current phase | Current work |
| `docs/ASSUMPTIONS.md` | Choices made where SPEC was silent | Owner reviews |

**Conflict order:** SPEC > DECISIONS > TECH_ARCHITECTURE > other docs. If a derived doc disagrees with SPEC, follow SPEC and log the mismatch in PROGRESS.md "Known issues".

## Session start (every task)
1. Read `docs/PROGRESS.md` and the current `docs/tasks/phase-N.md`.
2. Read only the SPEC sections and doc sections referenced by the task.
3. State in one line: current phase, current task, files you expect to touch.

## Golden rules
- **Phase 0 = explore only** (`/explore`): clone Docling into `vendor/docling`, run it the free way, fill `docs/EXPLORATION_REPORT.md`, stop for review. No product code before the owner approves the plan. Never modify files in `vendor/`.
- ONE task at a time from the current phase. Never jump ahead.
- If SPEC is silent or ambiguous: choose the simplest option consistent with SPEC Section 3, record it in `docs/ASSUMPTIONS.md`, continue.
- Never invent library APIs (Docling, pdfplumber, openpyxl, google-genai change often): check the installed version's source/types or docs first.
- Never mark a task done unless `python scripts/check.py` passes (and `python -m stmtconv selftest` from Phase 4).
- **No silent errors:** a wrong number must always be flagged. Money is `Decimal`, never `float`.
- **Client data never leaves the laptop** except through the AI gate (SPEC 11.2). Never read real statements; use `tools/synth` fixtures.
- Never hardcode secrets, bank layouts, category keywords, prices, or client-facing text — they live in `.env`, `profiles/`, `config/`, `templates/`.
- Never remove or weaken a test (or edit a golden file) to make it pass without explaining why in PROGRESS and the commit.
- Don't edit `docs/SPEC.md`, this file, `kilo.jsonc`, or `.kilo/` without explicit approval.
- Stop and ask before: adding a dependency not in SPEC Section 4 or an ADR, changing verdict/validation rules, changing export formats, touching deletion or network code, deleting files outside the task.

## Stack (do not substitute)
Python 3.12 · src-layout package `stmtconv` · Typer + Rich · pydantic v2 + pydantic-settings · PyYAML · pdfplumber + pypdfium2 · Docling (RapidOCR, CPU) · Pillow · openpyxl · hand-written OFX writer · google-genai (optional AI) · pytest + hypothesis + reportlab (synthetic PDFs) · ruff · mypy. Windows 10/11, i5-8250U, 12 GB RAM, no GPU.

## Repo layout
- `src/stmtconv/cli` — Typer commands (thin)
- `src/stmtconv/core` — pure models, money, dates, assembly, validation, verdicts, merge, categorization
- `src/stmtconv/orders` — manifests, state machine, workspace paths, ledger
- `src/stmtconv/intake` — sniffing, hashing, page analysis, passwords, photos, quote
- `src/stmtconv/profiles` — profile schema, loader, detector, scaffold
- `src/stmtconv/extract` — Extractor protocol, text/docling/ai engines, router, summary
- `src/stmtconv/review` — review workbook, apply-review, spot-check
- `src/stmtconv/export` — Excel, QB CSV, Xero CSV, generic CSV, OFX, templates, delivery package
- `src/stmtconv/privacy` — redaction, masking, AI gate, deletion
- `config/`, `profiles/`, `templates/` — data files (no client data)
- `vendor/docling` — cloned Docling repo for exploration/reference (git-ignored); `explore/` — throwaway Phase 0 scripts (git-ignored)
- `tools/synth` — synthetic statement generator; `tests/` — unit, golden, e2e
- `scripts/check.py` — quality gate; `docs/` — documentation above

## Commands
`python scripts/check.py` · `python scripts/check.py --quick` · `python -m stmtconv --help` · `python -m stmtconv doctor` · `python -m stmtconv selftest` · `python -m stmtconv models download` · `pip install -e ".[dev]"`

## End of every task
Update `docs/PROGRESS.md` (status, files changed, manual verification, issues). New architectural choice → ADR in `docs/DECISIONS.md`. Commit with a conventional commit message.
