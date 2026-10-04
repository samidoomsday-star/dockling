# Progress

## Current status
- **Current phase:** Phase 9 — optional BYOK configuration and AI gate in progress.
- **Current task:** implement Phases 2–10 in order, as newly authorized; no approval pauses.
- **Last updated:** 2026-10-04 UTC (5 October in the client's timezone).
- **Owner decisions:** “Start Phase 1” accepted Phase 0 findings and authorized the foundation. Continue original phases 0–10, with GitHub versions, beginner guidance and optional OpenAI-compatible BYOK model/effort selection up to supported Max.

## Phases

| Phase | Name | Status | Verified |
|---|---|---|---|
| 0 | Import, setup and explore Docling | Complete; owner approved proceeding | Offline experiments and limitations recorded |
| 1 | Foundation | Cloud milestone complete; Windows acceptance pending | 32 tests, strict typing, lint/format, build, model setup and installed-wheel doctor |
| 2 | Orders, intake and synthetic corpus | Cloud milestone complete | 120 total tests passed, strict typing, lint/format; encrypted intake and scanned quote |
| 3 | Core normalization and validation | Cloud milestone complete | 250 total tests; Decimal round trips and all 50 corrupted-row positions for asset/liability |
| 4 | Text engine and profiles | Cloud milestone complete | 252 total tests; nine exact selftest cases, profile data checks, changed PDF digit flagged |
| 5 | Docling/OCR and router | Cloud implementation verified; borderless rescue acceptance limited | 257 total tests; 15/15 scanned rows exact offline; source warnings retained |
| 6 | Exports and review | Cloud milestone complete | 269 total tests; four CSV goldens, numeric Excel, review atomicity/staleness and gates |
| 7 | Merge, categories and OFX | Cloud milestone complete | 278 tests; twelve-month workbook, exact gaps, account identity, category precedence, OFX goldens/parse |
| 8 | Delivery, retention and metrics | Cloud milestone complete | 284 tests; full delivery/close, versioned spot-checks, tamper refusal, partial deletion/retry and anonymous stats |
| 9 | Optional BYOK AI | Not started | — |
| 10 | Windows/field readiness | Not started | — |

## Phase 1 result

- Added a Python 3.12 package, all module folders, thin Typer CLI and explicit nonzero placeholders for later commands. Help, version, doctor and model download work. No order/conversion/AI feature is claimed implemented.
- Validated YAML and optional personal settings with environment > .env > YAML > defaults priority. Money uses Decimal; configuration errors hide values. Pricing/category/export stubs retain the original specification.
- Rotating JSON and console logs mask account-like digit runs and structured descriptions/keys, including nested fields; exception content is suppressed. Reinitialization avoids duplicate handlers. This does not justify logging arbitrary raw statements.
- Model setup verifies the recorded artifact hashes, uses a writable cache in the ignored models folder, and restores offline settings after success or failure. Hashes were not changed to pass verification.
- Created a hash-locked Linux CPU dependency set, repeatable installer and beginner Windows handoff guide. Packaging includes YAML defaults and the model manifest.

## Phase 1 verification

- `.venv/bin/python scripts/check.py`: **32 passed, 0 failed, 0 skipped**; ruff lint, format (42 files) and strict mypy (20 source files) passed. Two upstream Docling deprecation warnings remain. The slow integration test converts a synthetic two-row PDF with Python network connections blocked and verifies both rows.
- Privacy tests prove a 12-digit number, description, nested raw text/key and exception content do not reach captured console/file logs. Configuration, model tampering/path escapes, safe error handling and placeholder behavior are also tested.
- `bash scripts/install-linux.sh`: exit 0; hash-locked dependency install, editable installation and pip check passed. CPU torch 2.14.1+cpu / torchvision 0.29.1+cpu confirmed. Installer debugging identified the required editable-build dependency; it is now pinned.
- `.venv/bin/python -m stmtconv models download`: exit 0; all pinned model hashes matched. Repeated download works; read-only home-cache warnings were resolved.
- `.venv/bin/python -m build --no-isolation`: source archive and wheel built successfully.
- Fresh `/tmp/dockling-wheelcheck` virtual environment: hash-locked dependencies installed, wheel installed, `python -m stmtconv doctor` ran successfully from unrelated `/tmp`. Bundled defaults/manifest were used, workspace/model/offline checks passed; disk encryption remains explicitly unverified. This checks packaging portability on Linux, not Windows.
- Logs and installed/generated files are ignored or outside the repository. Only synthetic data was used; no client documents, secrets or paid API calls.

## Known limits

- Windows PowerShell installation/tests have not run. The SPEC's Windows Phase 1 acceptance remains pending; the owner approved doing device checks later. Do not count the Linux lock as a validated Windows lock.
- Docling produced zero structured tables for the Phase 0 borderless and two-page borderless examples despite excellent grades. Keep text-first extraction and independent validation; do not promise every layout is rescued by OCR.
- Eight-row Phase 0 examples and the two-row foundation smoke test are not general accuracy evidence. Broader corpus, camera samples, license audit, hardware timings and accounting imports remain later work.
- Optional BYOK fields are reserved only. The actual custom endpoint/model/effort picker and consent gates come in Phase 9. No LLM key is needed now.
- Encryption cannot be established by this cloud doctor. Confirm Windows device encryption before real client work.

## Phase 0 evidence retained

- Main run a6db92287d9f4481bf0b39640c045614: required digital/scanned/photo-like examples preserve 8/8 rows.
- Borderless/multi-page examples preserve 0/8 and 0/12 structured rows; text remains. Native PDF has text but no structured tables. DOCX/XLSX/HTML preserve 8/8 rows.
- Alternate integrated Tesseract scan preserves 8/8 rows; standalone OCR checks only date tokens.
- Evidence files: PHASE0-EVIDENCE.json, PHASE0-ALTERNATE-OCR.json, PHASE0-MODEL-MANIFEST.json and EXPLORATION_REPORT.md.

## GitHub and reusable environment

- Phase 1 work lives on `phase-1-foundation`, based on `phase-0-exploration`. `main` remains the original starter. No merge has been authorized or performed.
- Git push works. Previous GitHub API access blocked automatic PR creation; no PR exists and no token is needed for normal Git operations.
- Reusable setup uses scripts/install-linux.sh and the Phase 1 command-line checks. The environment draft must select this milestone commit. Saving instructions is distinct from publishing; only the owner can publish the updated snapshot. New-task restoration is not yet verified.

## Next step

Review Phase 1. Then Phase 2 implements order records, safe status changes, file intake/quotes and a broader synthetic test corpus. Continue cloud development while retaining Windows checks for the other device, as agreed. See ENVIRONMENT.md for exact clone/update instructions.

## Phase 2 milestone
Owner authorized remaining phases in sequence. Typed manifests, atomic writes/exclusive edits, checked transitions, confined paths, file-content intake, password-safe copies, image combination and YAML quotes implemented. All 81 state pairs tested; 120 total tests passed with none skipped. Three layouts have text/scanned, wrapped and multipage synthetic variants. Combined images use numbered filename order; closed/failed are terminal. Windows execution remains pending.

## Phase 3 milestone
Strict Decimal parser covers locales, signs and suffixes; dates retain ambiguity and missing-year flags; wrapped/inherited rows preserve source provenance. Validation checks running balances, printed totals, closing movement, duplicates and page coverage. 250 total tests pass with none skipped, including 100 single-digit corruption positions. Verified verdicts describe financial reconciliation, not source-date/description certainty.

## Phase 4 milestone
Text extraction uses word geometry and validated YAML profiles; summaries, wrapped rows and page provenance are persisted. CLI extract/validate/profile scaffold/test/selftest work. Nine three-layout statements (including multipage) match every row/date/amount/description; corrupted PDF produces one mismatch. Full gate: 252 passed, none skipped. Unknown layouts need review rather than being claimed supported.

## Phase 5 milestone
Pinned Docling CPU converters are lazy and reused per OCR mode, with ACCURATE tables and selective default OCR. Whole-statement candidates are normalized and validated before selection; reasons/confidence/timings retained. All 15 rows across three real scanned layouts match ground truth offline, and all OCR rows carry SOURCE_CHECK_REQUIRED. Full gate: 257 passed, none skipped; upstream deprecation/runtime warnings recorded. Selftest passes. The draft acceptance requiring Docling to rescue any borderless wrapped layout remains limited by observed Phase 0 behavior; text handles our borderless fixture. This limitation is not hidden by weakening a test or promising universal rescue.

## Phase 6 milestone
Client Excel and four deterministic CSV formats, configurable dates/headers, QB splitting, formula-like text escaping and staged output publication implemented. Review fix/delete/insert is batch-validated, provenance/fix history retained, stale workbooks rejected, signed balances supported, and partial fixes cannot hide unreadable amounts. Exports enforce verdict and spot-check gates with explicit disclosures/overrides. Full gate: 269 passed, no skips; selftest passes. CSV golden files were manually authored from a two-row synthetic statement; Excel reload checks numeric/date cells and highlighting.

## Phase 7 milestone
Twelve monthly sheets plus All Transactions/Summary/Issues; exact Decimal continuity/gap/overlap checks; category precedence/direction/regex with local overrides; deterministic bank/card OFX and occurrence-aware FITIDs implemented. Same last-four display masks alone cannot authorize merging or identify OFX transactions: private full-account hashes or operator-confirmed account groups are required. Manual bank/card golden fixtures use the private account key in the FITID hash; SGML round-trip parses totals/dates/amounts. Full gate: 278 passed, none skipped; selftest passes. Actual accounting imports remain device checks.

## Phase 8 milestone
Delivery validates export hashes and statement revision, then archives outputs and factual template disclosures. Pipeline pauses for review/spot-check instead of bypassing them. Spot checks are versioned. Close confines paths, refuses symlinks, inventories hashes, preserves retryable partial failures, re-scans before certification and scrubs all client fields. Anonymous typed ledger writes are atomic/idempotent; stats/quote medians use measured timings. Full gate: 284 passed, no skips; selftest passes. Tests confirm closed folder contains only order.json, no sample alias/description/file names/amounts in retained manifest/ledger, and a partial deletion issues no certificate.
