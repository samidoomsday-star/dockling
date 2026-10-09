# Progress

## Current status
- **Current phase:** Phases 0–10 cloud development complete; Windows/field/provider acceptance pending.
- **Current task:** Stage B interactive frontend implemented/tested/reviewed on web-frontend; real API/worker/authentication and deployment remain pending.
- **Last updated:** 2026-10-09 UTC (10 October in the client's timezone).
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
| 9 | Optional BYOK AI | Cloud implementation verified with fakes | 302 tests; gate/no-network, private keys, capabilities/Max, chat/responses adapters, invalid/rejected output and budget binding |
| 10 | Launcher and handoff | Cloud milestone complete; device/field acceptance pending | 314 tests, full gate/selftest, 15 synthetic cases, build and installed-package delivery/cleanup |

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
- Phase 10 adds the broader synthetic corpus and a direct/model license inventory. Real camera/field samples, laptop timings, accounting imports and remaining transitive/model provenance obligations are pending. Synthetic examples do not establish general accuracy.
- Optional BYOK is implemented and tested with fake providers in Phase 9. Actual provider connection/inference, model-specific effort and terms remain owner/device checks; no paid inference call was made here.
- Encryption cannot be established by this cloud doctor. Confirm Windows device encryption before real client work.

## Phase 0 evidence retained

- Main run a6db92287d9f4481bf0b39640c045614: required digital/scanned/photo-like examples preserve 8/8 rows.
- Borderless/multi-page examples preserve 0/8 and 0/12 structured rows; text remains. Native PDF has text but no structured tables. DOCX/XLSX/HTML preserve 8/8 rows.
- Alternate integrated Tesseract scan preserves 8/8 rows; standalone OCR checks only date tokens.
- Evidence files: PHASE0-EVIDENCE.json, PHASE0-ALTERNATE-OCR.json, PHASE0-MODEL-MANIFEST.json and EXPLORATION_REPORT.md.

## GitHub and reusable environment

- All remaining phases are on `development-phases-2-10`, based on `phase-1-foundation`. `main` remains the starter; no merge has been authorized/performed.
- Git push works. Previous GitHub API access blocked automatic PR creation; no PR exists and no token is needed for ordinary Git operations.
- Setup uses the tested scripts/install-linux.sh and final command-line checks. The historical Phase 1 Linux hash lock contains all phase 2–10 dependencies; HTTPx was already pinned. It is not a validated Windows lock.
- Reusable environment instructions and repository HEAD are refreshed for final review/publication. Saving a draft does not publish; new-task snapshot restoration remains unverified.

## Next step

Use [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) for the first fake delivery and daily operations, [ENVIRONMENT.md](ENVIRONMENT.md) for clone/install/update, and [BYOK_GUIDE.md](BYOK_GUIDE.md) for your own provider. Complete the Windows/field checklist before real client work. Development phases do not need further approval pauses.

## Phase 2 milestone
Owner authorized remaining phases in sequence. Typed manifests, atomic writes/exclusive edits, checked transitions, confined paths, file-content intake, password-safe copies, image combination and YAML quotes implemented. All 81 state pairs tested; 120 total tests passed with none skipped. Three layouts have text/scanned, wrapped and multipage synthetic variants. Combined images use numbered filename order. Phase 10 later permits explicit abandoned cleanup from failed to closed; closed remains terminal. Windows execution remains pending.

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

## Phase 9 milestone
Private OpenAI-compatible provider setup, hidden keys, discovery/manual model entry, model-specific capability references, picker defaults to highest supported effort (Max only when documented), and explicit schema/effort/token/route adapters implemented. Processing requires activation, consent/note, terms, model/key and budget; requests/retries consume persisted pages before network access. Provider/model/effort changes require explicit renewed consent. Only minimized/masked table cells are sent; invalid JSON is bounded/rejected; AI output remains source-review-gated and financially revalidated. Source confirmation is distinct from changing amounts, so fix counts are not fabricated. Full gate: 302 passed, no skips; selftest passes. All provider tests use fakes/MockTransport; no real model connection or paid API call was made. Actual provider terms/model capabilities must be confirmed on the owner device.

## Phase 10 milestone

- Added `run.bat` and `inbox`: validates drop-folder content, moves files into a tracked order, pauses for source review/spot-check, then resumes delivery. Added synthetic PDF/workbook/before/after PNG demo generation and beginner operator/BYOK guides.
- Hardened leap-day year inference, rejected float financial fields, preserved zero CSV balances, accounted for known blank pages, required offline local extraction, rejected clear invoice headers, added per-order currency choice and explicit abandoned cleanup. Abandoned ledger records do not influence delivery-based quote medians.
- Full gate: **314 passed, 0 failed, 0 skipped**, strict mypy over 66 source files, lint and format passed; 13 upstream Docling/RapidOCR/PyTorch warnings remain. Nine exact selftest cases passed. Installer repeated successfully with pip check and CPU torch/torchvision confirmed. Model setup verifies all pinned hashes. Wheel and sdist 0.2.0 built successfully.
- Installed wheel tested in a separate virtual environment from unrelated `/tmp`: bundled defaults/profiles/templates, nine-case selftest, demo assets, intake/extraction, source-check pause, export, delivery ZIP and verified close all passed. Installed-package doctor passed with disk encryption explicitly unverified.
- **15/15 synthetic checklist cases passed** with network socket connections blocked. See PHASE10-SYNTHETIC-ACCEPTANCE.json for per-case rows, printed balances/totals, mismatches and seconds/page. Twelve statements preserve **437/437 exact rows**; three clear-header invoices reject as outside V1. Long statements preserve 176/176 rows over 22 pages and 168/168 over 21 pages. All statement mismatch counts are zero. Digital intake+extraction measured about 0.034–0.080 seconds/page; scans/simulated JPEG about 5.6–11.4 seconds/page, including cold model setup. Cloud measurements are not laptop estimates; the photo is a rendered simulation, not a real camera capture.
- LICENSES.md and PHASE10-DEPENDENCY-LICENSES.json record inspected direct/dev/native package metadata and model-card terms. Hypothesis is development-only MPL-2.0; RapidOCR artifact provenance/additional terms and full transitive redistribution notices remain limited. Models/dependency binaries are not distributed in Git/wheel.
- **Original field acceptance remains pending:** Windows installation/run.bat, Excel review and actual QuickBooks/Xero/OFX imports, 15 permitted owner/public documents including real photos, laptop performance, and actual BYOK service/terms/capability checks. Borderless Docling rescue and unknown-layout safe AI cells retain documented limitations. No real client documents or paid LLM inference calls were used.

## Fresh GitHub clone handoff verification

Cloned the pushed development-phases-2-10 branch into a separate `/tmp` checkout. Created a new Python environment and installed the hash-locked dependencies using UV's existing verified download cache, then ran the repository Linux installer successfully. Reused cached pinned model files; the documented model download command completed hash verification. Doctor and all nine selftest cases passed. Executed the operator guide using the actual CLI: demo -> order new -> intake -> extract -> interactive spotcheck -> run (delivery ZIP) -> interactive close. ZIP contents and scrubbed order.json-only folder were independently checked. This proves the Linux fresh-clone workflow with cached artifacts; Windows installation/imports and fresh-task cloud snapshot restoration are still unrun. No credentials or real client documents were used.

## Receiving-device setup guidance — 2026-10-05

Added DEVICE_SETUP.md with a copyable owner request and receiving-assistant protocol: OS/Python/branch inspection, preserving local settings/jobs, the documented CPU installer, model hash verification, doctor/full checks/selftest, actual synthetic CLI delivery/close, and truthful reporting of device checks. Root AGENTS.md and the start/install guides direct new-device setup there. Covers optional custom BYOK model/effort setup and explicitly records that there is no graphical UI server. Documentation links and whitespace checked; no application code changed or additional Windows checks claimed.

## Web-app proposal — 9 October 2026 (Asia/Dhaka)

Owner requested an audit and UI/frontend plan for review before implementation, and selected customer self-service plus owner/admin tools. WEB-APP-PLAN.md maps existing CLI/services/configuration to web screens, states, permissions, integration work and staged acceptance. Includes all six formats, Excel/browser review, merge/categories, BYOK/model/effort/consent/budget, operational profiles/models/stats, delivery and deletion. WEB-APP-WIREFRAME.html illustrates seven major screens with synthetic data and no processing/network/key storage; it is not a web application. No backend/frontend application dependencies or behavior were changed. Proposal acceptance, branding/style edits, commercial/payment scope and hosting selection remain open; no publication or application implementation authorized by this planning request.

Planning artifact checks: local links, HTML screen IDs/navigation targets/input labels, absence of remote assets, JavaScript syntax and git whitespace checks passed. Headless Chromium screenshot attempts timed out in this environment; no screenshot or completed browser/viewport validation is claimed. Full application gates were not rerun for this documentation/design-only change.

## Web visual refinement — 9 October 2026 (Asia/Dhaka)

Owner endorsed the plan direction and requested a more attractive, current UI while keeping the friendly basic layout and avoiding neon/disco styling. Refreshed the seven-screen design preview with forest-teal actions, mint/peach/dusty-blue/lavender surfaces, stronger typography, outline navigation icons, softer gradients, restrained shadows and clearer cards. Financial tables keep readable neutral surfaces and meaningful status colors. Updated WEB-APP-PLAN's color/design direction; functionality and feature coverage remain as planned. This is still a synthetic planning preview, not the working web application.

Refinement checks: seven-screen navigation targets, unique IDs, labels, absence of remote assets, local links, JavaScript syntax and git whitespace passed. Eight representative text/background color pairs exceed 4.5:1 after darkening the coral label; this is not a full accessibility audit. Browser screenshot capture still times out here, so visual/viewport inspection remains pending. No app processing code or dependency changes, no paid calls and no production deployment.


## Stage B frontend — 10 October 2026 (Asia/Dhaka)

Owner authorized an implementation checklist followed by building, testing and review. React/TypeScript/Vite frontend now covers public home/sample/help/pricing/access, customer dashboard/intake/jobs/review/checks/exports/AI/categories/settings and owner profiles/pricing/config/health/metrics. Approved forest-teal, peach, blue and lavender styling is implemented responsively. Exact monetary strings, staged atomic fixture edits, revision/source-check/export gates, consent/model-effort controls and removal/partial-retry flows are interactive in memory. Every original capability is mapped in FRONTEND-COVERAGE.md, including server-dependent controls and retained CLI equivalents.

Fresh `npm ci`, lint/format/strict typing/production build, 36 unit tests and 18 Chromium journeys passed; automated accessibility scans covered 14 routes at 1440 and 375 px plus review tabs/provider dialog. Final mobile-only scroll/edit polish passed both route/accessibility checks again. Four CSV references match manual goldens; production HTTP serving verifies numeric/date Excel cells, OFX amounts, matching synthetic PDF and ZIP contents. Python full gate: 314 passed, none skipped, 13 upstream warnings; no processing logic changed. npm audit: zero known vulnerabilities at this run. Actual screenshots, direct/build/test dependency terms and setup instructions are recorded. Windows launcher and GitHub CI execution remain unobserved; no public staging deployment.

This is Stage B, not a real hosted conversion service. No actual upload/OCR, authentication, private storage, key storage, provider request or payment occurs. Fixed reference downloads are not exports of user files or edits. Stage C connects API/worker/source viewer/shared review/live exports; Stage D adds secure accounts/isolation/BYOK/outbound policies/quotas; Stage E tests chosen hosting. Main remains unmerged. Frontend branch includes the completed Python work; fresh devices follow frontend/README.md for UI and DEVICE_SETUP.md for optional Python setup.
