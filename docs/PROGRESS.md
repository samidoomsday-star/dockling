# Progress

## Current status
- **Current phase:** Phase 0 — exploration complete; awaiting owner review before Phase 1.
- **Current task:** review findings and confirm the Phase 1 foundation task.
- **Last updated:** 2026-10-04.
- **Owner decisions:** Codex development; original phases 0–10; GitHub versions; other-device installation; beginner guidance; optional OpenAI-compatible BYOK model/effort picker up to supported Max.

## Phases
| Phase | Name | Status | Verified |
|---|---|---|---|
| 0 | Import, setup and explore Docling | Experiments complete; review pending | Required offline conversions ran; limitations documented |
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
- 2026-10-04: downloaded required models after publication; ran offline ML and supplemental alternate OCR; saved current evidence, observed model hashes and complete exploration report. No product code, client data or paid API call.
- 2026-10-04: diagnosed Hugging Face's redirected artifact host us.aws.cdn.hf.co; saved domain addition and owner published it. Metadata and actual file downloads now work.
- 2026-10-04: imported starter; recorded Codex/BYOK decisions; installed pinned CPU dependencies and ran independent experiments while downloads were blocked.

## Known issues and limits
- Docling detects zero tables in our borderless and two-page borderless examples despite excellent mean grades; this is a diagnosed extraction limitation, not an environment blocker. Keep the text-first engine and independent validation.
- Eight-row ruled digital/scan/photo-like examples are exact, but the corpus is not broad accuracy evidence.
- Windows/device performance, real-camera input, full dependency/OCR-weight license audit and actual accounting imports are unverified.
- CODEX-PROJECT-PLAN records remaining requirement clarifications for later phases.

## Phase 0 verification
- Main run: a6db92287d9f4481bf0b39640c045614; research runner exit 0. Required digital/scanned/photo-like conversions each preserve 8/8 expected rows.
- Borderless and multi-page conversions execute successfully but preserve 0 structured rows (0/8, 0/12); text remains. Do not mark table-quality checks passed for those targets.
- DOCX/XLSX/HTML preserve 8/8 expected rows. Native PDF emits text without tables.
- Alternate integrated Docling/Tesseract scan preserves 8/8 rows; standalone OCR checks date-token accessibility only.
- Research lint/format, pip check, repeated Linux install, repeated model download, parsed JSON exports and workbook reopening pass.
- Current evidence: PHASE0-EVIDENCE.json, PHASE0-ALTERNATE-OCR.json, PHASE0-MODEL-MANIFEST.json, EXPLORATION_REPORT.md.
- scripts/check.py and stmtconv selftest do not exist; no product tests executed.

## GitHub and environment
- Original starter on main; latest development work on phase-0-exploration. No merge into main has been authorized/performed.
- Git pushes work. Automatic draft PR creation was previously blocked by GitHub API access; no PR created or token requested.
- Network settings have been published and required model downloads work in this instance. Refreshed install/start instructions are saved for review; a new snapshot/publication of the prepared models is not yet verified.

## Next step
Owner reviews EXPLORATION_REPORT and confirms Phase 1. Then create docs/tasks/phase-1.md and implement foundation acceptance criteria. Do not treat missing Windows checks or unresolved synthetic coverage as passed.
