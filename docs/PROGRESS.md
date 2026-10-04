# Progress

## Current status
- **Current phase:** Phase 0 — import, setup and Docling exploration.
- **Current task:** required model downloads blocked by runtime network policy; independent experiments complete.
- **Last updated:** 2026-10-04.
- **Owner decisions:** Codex development; original phases 0–10; GitHub versions; other-device installation; plain-language guidance; optional OpenAI-compatible BYOK model/effort picker up to supported Max.

## Phases
| Phase | Name | Status | Verified |
|---|---|---|---|
| 0 | Import, set up and explore Docling | Blocked on models | 9 independent checks succeed; ML digital failed prerequisite; 4 ML targets unrun |
| 1 | Foundation | Not started | — |
| 2 | Orders, intake and synthetic corpus | Not started | — |
| 3 | Core normalization and validation | Not started | — |
| 4 | Text engine and profiles | Not started | — |
| 5 | Docling/OCR and router | Not started | — |
| 6 | Exports and review | Not started | — |
| 7 | Merge, categories and OFX | Not started | — |
| 8 | Delivery, retention and metrics | Not started | — |
| 9 | Optional BYOK AI | Not started | — |
| 10 | Windows/field readiness | Not started | — |

## Task log
- 2026-10-04: imported 45-file starter and project plan into existing checkout; active Codex instructions and ADR-013/014 record approved changes. No product implementation, key, paid API call or real document.

## Known issues
- Requirements needing precise tests/decisions before implementation are listed in CODEX-PROJECT-PLAN (verification limits, signs, identity, revision gating, dates, state transitions, deletion).
- Historical Kilo rules/research and Gemini variables are reference; current SPEC/ADRs supersede conflicting provider/workflow details.
- Cloud Linux checks do not establish Windows behavior or laptop speed.

## Phase verification reports
- Current evidence: docs/PHASE0-EVIDENCE.json and docs/EXPLORATION_REPORT.md.
- 3 text-access checks passed; 3 Docling office/web conversions succeeded with 8/8 exact expected rows; native PDF converted but yielded no tables; 2 alternate OCR commands succeeded with 8/8 date tokens. These are distinct capabilities, not 9 tests of bank-statement correctness.
- Main Docling PDF attempt failed with missing layout artifacts; required scans/photo and additional ML layouts remain unrun. Runner exit 1 preserved.
- Research ruff lint/format passed; pip check and repeat Linux installation passed. scripts/check.py and stmtconv selftest do not exist yet.
- Domain additions saved in environment draft, not applied/published. Owner must review/save and publish before retry.
- Phase 1 remains unstarted pending completed exploration and owner review.

- 2026-10-04: pinned CPU dependency pair, generated synthetic research inputs, recorded actual partial results, and prepared reproducible setup. No client data/model binaries/installed dependencies in commits.
