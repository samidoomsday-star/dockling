# Phase 0 — import, setup and Docling exploration

## Scope
Owner authorized starter migration and cloud exploration. No product code. Original phases 0–10 retained; stop for exploration review before Phase 1.

## Tasks
- Import starter, make Codex instructions active, record BYOK/effort requirement and owner guidance.
- Clone/pin upstream Docling, create Python 3.12 environment, install CPU prerequisites and download models with verification intact.
- Generate synthetic digital, scanned and photo-like inputs, plus borderless/multi-page tables.
- Run conversion to Markdown/JSON/HTML, inspect extracted tables, confidence and tables-to-Excel output; compare known rows and record timing/memory.
- Exercise feasible optional format/OCR features; label unrun checks explicitly.
- Record findings, reusable setup instructions, cloud/Windows distinctions and remaining risks.
- Commit and push reviewable GitHub version; owner review then confirms Phase 1.

## Gate
Current-run exploration results must identify inputs, versions, successful/failed checks and known-truth comparisons. Phase 1 checks/selftest do not yet exist. Required conversions cannot be marked passed until actually run.

## Current outcome
Required model downloads and repeated downloads succeed. Digital/scanned/photo-like conversions run offline and preserve 8/8 expected rows. Borderless and multi-page conversions run but detect zero tables; this diagnosed limitation is recorded honestly. Supplemental Docling/Tesseract works. Evidence/report/setup are saved. Exploration is complete, pending owner review before Phase 1; Windows and actual-camera checks are later device acceptance.
