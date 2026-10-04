# Statement Converter — Product & Technical Specification (V1.1 — Codex/BYOK migration)

> **Messy PDFs → verified Excel / QuickBooks / Xero files. Local-first, balance-checked.**
> **Source of truth:** this SPEC. The owner's roadmap `01-docling-roadmap.md` (25 Sep 2026) is a **reference only**. Phase 0 clones, runs and explores Docling first; Phases 1+ are a **draft plan, confirmed or changed after the owner reviews `docs/EXPLORATION_REPORT.md`**. Research is in `docs/RESEARCH.md` (Appendix A lists where it changed the roadmap).

---

## Owner-approved migration note (4 October 2026)

Develop and explore in Codex with synthetic data; save source versions in GitHub, then install and validate on another device. Preserve phases 0–10. Explain all owner actions in plain language. Replace Gemini-only AI with custom OpenAI-compatible BYOK providers, model discovery/manual entry, and a model picker with supported reasoning effort up to Max. Provider default or the highest supported level must be labelled honestly; never silently downgrade a rejected effort. See ADR-013/014 and `CODEX-PROJECT-PLAN.md`. Historical research and `.kilo/` remain reference material.

## 0. Instructions for the AI coding agent (READ FIRST)

1. **Phase 0 is exploration only:** clone a pinned Docling release into `vendor/docling`, set it up without paid services, and run the statement-relevant feature checks, fill `docs/EXPLORATION_REPORT.md`, then **stop** for the owner's review. No product code and no changes to Docling in Phase 0. Don't start Phase 1 until the owner confirms the plan (it may change after exploration).
1b. **Owner authorization update:** the owner now asks to complete all remaining phases in sequence without approval pauses. Keep separate implementation/test milestones and report limitations. **Build phase by phase** using Section 17. Complete one phase, make it run, pass its acceptance criteria, then stop and summarize before starting the next. Never build all phases in one pass.
2. **Architecture rules in Section 3 are non-negotiable.** If a shortcut would violate one, don't take it.
3. **Accuracy beats coverage.** The product promise is "no silent errors": a wrong number that is *flagged* is acceptable; a wrong number that is *not flagged* is a critical bug. When unsure, flag.
4. **Money is `decimal.Decimal`, never `float`**, from parsing to export.
5. **Client data never leaves the laptop** unless an order has explicit AI consent and the configured-provider AI gate passes (Section 11). No other code may open a network connection during order processing.
6. **Never hardcode secrets** (API keys) — they come from `.env` via the typed config module (Section 16).
7. **Never hardcode bank-specific layouts, category keywords, prices, or delivery text in Python.** They live in YAML/template files under `profiles/`, `config/`, and `templates/` (Section 3.8).
8. **The finished application must run on the owner's laptop; cloud development is Linux and Windows acceptance remains separate:** Windows 10/11, Intel i5-8250U (4 cores/8 threads), 12 GB RAM, no usable GPU, Python 3.12. No CUDA-only dependencies. Commands must work in Windows PowerShell 5.1 (no `&&` chaining in documented commands; use `python scripts/check.py`).
9. When this spec is ambiguous, pick the simplest option consistent with Section 3, write the assumption in `docs/ASSUMPTIONS.md`, and continue.
10. Write automated tests for: amount parsing, date parsing and year inference, multi-line row merging, running-balance validation (bank and credit-card direction), statement verdicts, every export format, deletion, the AI consent gate, and log redaction.
11. Features marked **V2** or **Future** must NOT be built in V1, but the V1 data model must allow adding them without restructuring (e.g. `document_type` exists even though only statements are built).
12. Keep `docs/PROGRESS.md` updated with completed phases and known issues.
13. Items marked *(inferred)* or *(reported)* are reasonable interpretations or third-party claims; implement them but keep the values configurable.

---

## 1. Product overview

**Statement Converter** (package name `stmtconv`) is a **local command-line tool the owner uses to deliver a done-for-you service**: clients (bookkeepers, small businesses, loan processors) send PDF or photographed bank / credit-card statements; the owner runs the tool, reviews what it flags, and delivers clean Excel plus accounting-software import files with a **balance-verification report**.

It is **not** a SaaS and has no client-facing UI in V1. The client-facing "product" is the delivered files and the verification proof.

**Core loop (one order):** create order → drop files → intake (page count, text vs scanned, quote) → extract (text engine → Docling → optional AI) → normalize → validate balances → operator reviews flagged rows in Excel → apply fixes → spot-check → export (Excel, QuickBooks CSV, Xero CSV, OFX) → delivery package + note → close order (delete client files, keep anonymous metrics).

**Positioning (from research, see `docs/RESEARCH.md`):** self-serve converters (DocuClipper, CapyParse, BankXLSX, Lido…) already sell balance reconciliation for roughly $0.13–$0.50 per page, and QuickBooks Online itself now accepts statement PDFs/photos with built-in AI extraction. The service therefore competes on what software alone doesn't give: **human-reviewed output with a written verification report, messy/scanned/non-US statements, multi-month merging with continuity checks, categorization, per-job pricing (no subscription), and local-only processing with a deletion certificate** that helps US bookkeepers document vendor oversight under the FTC Safeguards Rule.

### Key surfaces (required)
1. **CLI** (`python -m stmtconv …`) — all operator actions (Section 13).
2. **Client workbook** (`<order>-<statement>.xlsx`) — Transactions, Summary, Issues sheets (Section 12.1).
3. **Review workbook** — same data plus editable fix columns for the operator (Section 10).
4. **Import files** — QuickBooks CSV (3- or 4-column), Xero CSV, generic CSV, OFX (Section 12).
5. **Delivery package** — zip with outputs, delivery note, verification summary, data-handling statement (Section 14).
6. **`run.bat` drop-folder launcher** — double-click convenience for the default flow (Phase 10).

### Glossary

| Term | Meaning |
|---|---|
| Operator | The owner running the tool. Only user of the system in V1. |
| Client | Person/firm who sends documents and receives outputs. Never touches the tool. |
| Order | One client job. Folder under `workspace/orders/<order_id>/` with a manifest `order.json`. |
| Source file | One file the client sent (PDF, JPG, PNG, TIFF). |
| Statement | One account + one period inside a source file. A file can hold several statements (V1: one per file unless split, see 7.4). |
| Page analysis | Per-page facts: has text layer, rotation, is blank, is scanned. |
| Engine | An extraction method: `text` (pdfplumber word geometry), `docling` (layout + TableFormer + OCR), `ai` (cloud LLM, gated). |
| Raw row | A row as extracted, strings only, with page number and source engine. |
| Transaction | A normalized row: date, description, debit, credit, balance (Decimals), plus provenance. |
| Bank profile | YAML describing one statement layout: header aliases, date/amount conventions, summary-label patterns, noise lines. |
| Account direction | `asset` (bank account: balance = prev − debit + credit) or `liability` (credit card: balance = prev + debit − credit). |
| Row check | Per-row running-balance result: `OK`, `MISMATCH`, `UNVERIFIED` (no balance printed). |
| Statement verdict | `VERIFIED`, `VERIFIED_BY_TOTALS`, `VERIFIED_WITH_FIXES`, `NEEDS_REVIEW`, `UNVERIFIABLE`. |
| Review | Operator edits in the review workbook, re-imported with `apply-review`. |
| Spot-check | Random sample of rows the operator compares against the PDF before delivery. |
| Ledger | `workspace/ledger.jsonl`: anonymous per-order metrics (pages, seconds, engines, verdicts). No client data. |
| AI consent | Per-order flag recorded in `order.json` that the client agreed to cloud AI processing. |

---

## 2. Scope

### V1 (build now)
- Bank statements and credit-card statements (PDF text-based, PDF scanned, JPG/PNG/TIFF photos).
- Engines: `text`, `docling`, optional `ai` (OpenAI-compatible BYOK, suitable provider terms, consent-gated).
- Normalization, running-balance and totals validation, statement verdicts.
- Review workbook round-trip, spot-check sampler.
- Exports: client Excel, QuickBooks CSV (3-col and 4-col), Xero CSV, generic CSV, OFX 1.02.
- Multi-statement merge (e.g. 12 months) with period-continuity checks.
- Keyword categorization from YAML rules (optional per order).
- Orders, quotes from `config/pricing.yaml`, delivery package, delivery note, data-handling statement, deletion certificate, anonymous metrics.
- Synthetic statement generator + golden test corpus.
- `run.bat` launcher, `doctor` and `selftest` commands, operator guide.

### V2 (design for, don't build)
- Invoice extraction (`document_type = invoice`: vendor, number, date, subtotal, tax, total, line items).
- QuickBooks Desktop `.qbo` Web Connect export (needs an Intuit bank ID, see ADR-009).
- Local LLM fallback (e.g. via Ollama) instead of cloud AI.
- Local web review UI (instead of Excel round-trip).
- Loan-processor summary sheet (average balance, NSF count, income deposits by month).
- Multi-currency statements with FX columns.

### Future ideas
Client upload portal, monthly-subscription client dashboard, Tally/Sage export formats, IIF export, running on a small server.

---

## 3. Architecture rules (non-negotiable)

1. **Local-first & offline by default.** During `extract`, `validate`, `export`, only the `ai` engine may use the network, and only through the AI gate (11.2). After models are downloaded, the tool sets `HF_HUB_OFFLINE=1` so Docling never phones home during client work.
2. **Decimal money.** All amounts are `decimal.Decimal` quantized to the statement's currency exponent (default 2). Parsing never goes through `float`.
3. **Pure core.** `stmtconv.core` (models, money, dates, validation, merge, categorization) has no I/O and no imports from engines, exports, or CLI. Everything risky is unit-testable without PDFs.
4. **Engines behind one interface.** `Extractor.extract(page_set, profile, options) -> ExtractionResult` (raw rows + statement summary + per-page diagnostics). The router (7.3) picks engines; callers never import an engine directly.
5. **Provenance on every row.** Each transaction keeps `source_file`, `page`, `engine`, `raw_text`, and `fixed_by` (null / `review` / `ai`). Outputs can always be traced back to a page.
6. **No silent errors.** Every transaction ends with a row check; every statement ends with a verdict. Exports refuse to run when a statement is `NEEDS_REVIEW` unless `--allow-unverified` is passed, and then the Summary sheet and delivery note must say "not fully verified".
7. **Orders are folders with a manifest.** All state for an order lives in `workspace/orders/<order_id>/order.json` + subfolders (6.2). No database in V1. State changes go through `stmtconv.orders` functions that write the manifest atomically (write temp → replace).
8. **Domain as data.** Bank profiles (`profiles/*.yaml`), category rules (`config/categories.yaml`), prices (`config/pricing.yaml`), validation thresholds (`config/settings.yaml`), export column specs (`config/exports.yaml`), and delivery/statement texts (`templates/*.md`) are data files validated by pydantic schemas at load. No bank names, keywords, prices or client-facing sentences in Python.
9. **Privacy by construction.** Logs, ledger, and error messages never contain descriptions, names, or full account numbers (redaction filter, 15.2). Account numbers in outputs are masked to last 4 unless the order sets `show_full_account=true`.
10. **CLI is thin.** Typer commands parse arguments, call a service function, print a report. No business logic in `stmtconv.cli`.
11. **One config module.** `stmtconv.config` (pydantic-settings) reads `.env` + `config/settings.yaml` and validates at startup; nothing else reads environment variables.
12. **Deterministic outputs.** Same inputs + same profile + same settings → byte-identical CSV/OFX (stable ordering, deterministic FITIDs, fixed timestamps from order data). Excel may differ only in file metadata.
13. **Windows-first paths.** Use `pathlib`; never build paths with string concatenation; handle spaces and non-ASCII file names.

---

## 4. Tech stack & environment

| Area | Choice |
|---|---|
| Language | Python 3.12 (3.10–3.13 supported by dependencies; pin 3.12) |
| Packaging | `pyproject.toml`, `src/` layout, `pip install -e ".[dev]"` inside `.venv` |
| CLI | Typer (+ Rich for tables/progress) |
| Config & schemas | pydantic v2, pydantic-settings, PyYAML |
| Text-PDF engine | pdfplumber (word coordinates) on pdfminer.six; pypdfium2 for page rendering |
| Layout/OCR engine | Docling (standard PDF pipeline, TableFormer ACCURATE mode, RapidOCR on CPU — Docling's default OCR) |
| Images | Pillow (EXIF rotation, image→PDF for photos) |
| Excel | openpyxl |
| OFX | Hand-written OFX 1.02 SGML writer (no dependency; small, testable) |
| AI (optional) | OpenAI-compatible BYOK client/adapters, provider/model picker, capability-aware effort and schema output (ADR-014) |
| Tests | pytest, pytest-cov; synthetic PDFs via reportlab; hypothesis for parsers |
| Quality | ruff (lint + format), mypy (strict on `core`) |
| Secrets | `.env` via python-dotenv through pydantic-settings |
| Licenses | Only permissive (MIT/BSD/Apache) dependencies. **Do not add PyMuPDF** (AGPL) or other copyleft libraries (ADR-006). |

### Runtime & hardware budget
- Docling first run downloads ~1 GB of models (roadmap); `stmtconv models download` pre-fetches them to `models/` (`DOCLING_ARTIFACTS_PATH`).
- Docling CPU threads: `STMTCONV_NUM_THREADS` default 4.
- Expected speed *(inferred, must be measured in Phase 5)*: text engine < 0.5 s/page; Docling without OCR ~2–3 s/page; with OCR on CPU several seconds to 15 s/page. The ledger records real timings; quotes use measured medians once ≥ 5 orders exist.

---

## 5. Actors & permissions

| Action | Operator | Client |
|---|---|---|
| Run any CLI command | ✅ | ❌ (never has access) |
| Provide source files and answers (date order, categories, output format) | — | ✅ (via marketplace/email; operator records in `order.json`) |
| Grant AI consent for an order | records it | ✅ must be explicit, in writing |
| Receive outputs + deletion certificate | — | ✅ |

V2 might add a second operator; no permission system is needed in V1, but `order.json` stores `operator` for later.

---

## 6. Orders & workspace

### 6.1 Order fields (`order.json`)
`order_id` (`YYYYMMDD-<platform>-<short>` e.g. `20261003-fiverr-a7k2`), `created_at` (UTC ISO), `platform` (`fiverr|upwork|direct|test`), `client_alias` (no real names required; free text ≤ 40 chars), `package` (key from pricing.yaml), `addons` (list), `document_type` (`statement`; `invoice` reserved V2), `outputs` (subset of `excel, qb_csv3, qb_csv4, xero_csv, csv, ofx`), `date_order` (`auto|DMY|MDY|YMD`), `output_date_format` (e.g. `%m/%d/%Y`), `currency` (ISO 4217, default from settings), `categorize` (bool), `merge` (bool), `ai_consent` (`none|granted`) + `ai_consent_note` (where/when granted), `show_full_account` (bool, default false), `status`, `status_history[]`, `files[]` (name, sha256, pages, kind, password_protected), `statements[]` (id, file, pages, profile, account_mask, period, direction, verdict, counts), `timings` (seconds per stage), `manual_fixes` (count), `spot_check` (sample ids, passed bool, note), `deleted_at`, `deletion_certificate`.

### 6.2 Folder layout
```
workspace/
  ledger.jsonl                 anonymous metrics (survives deletion)
  orders/<order_id>/
    order.json
    input/                     client files, untouched copies
    work/                      page images, docling JSON, raw rows, intermediate JSON
    review/                    <statement>-review.xlsx
    output/                    client deliverables
    delivery/<order_id>.zip
```

### 6.3 Order statuses
`created → intake_done → extracted → needs_review ⇄ reviewed → exported → delivered → closed`. `failed` from any state with `error_code`. Transitions only via `stmtconv.orders.transition()`; illegal transitions raise `OrderStateError`.

### 6.4 Intake rules
- Accepted types by sniffed content (not extension): PDF, JPEG, PNG, TIFF. Others → rejected with reason.
- Max file size 100 MB, max 500 pages per order *(inferred; settings)*. Larger → `--force` required (roadmap: don't accept huge jobs before the pipeline is proven).
- Password-protected PDFs: intake marks `password_protected`; `stmtconv intake --password <pw>` decrypts to `work/` only; the password is never written to disk or logs.
- Photos: EXIF-rotate, convert to single-page PDF in `work/`; multiple photos of one statement can be combined in given order with `--combine`.
- Per page: text-layer detection (≥ 20 extractable characters and not only a hidden OCR layer of garbage *(inferred)* → `text`; else `scanned`), blank-page detection, rotation.
- Output of intake: file table (pages, kind, text/scanned counts) and a **quote** (6.5).

### 6.5 Quote
`stmtconv quote <order_id>` picks the smallest package in `config/pricing.yaml` whose page limit covers the order, applies add-ons (scanned surcharge +25% if any scanned pages, rush +50%, categorization, reconciliation report), and prints price range and estimated processing time (median sec/page from the ledger by kind, fallback to settings defaults). Packages (from roadmap, beginner prices): Basic ≤10 pages $10–15; Standard ≤50 pages $30–40 incl. QB/Xero CSV; Premium ≤200 pages $80–100 incl. categorization + summary; Monthly direct $99–199 fair-use. All values live in YAML.

---

## 7. Extraction

### 7.1 Engines
| Engine | Used for | How |
|---|---|---|
| `text` | Pages with a text layer | pdfplumber words with x/y; detect header row using profile aliases; derive column x-ranges from header positions (or profile-fixed ranges); assign words to columns; build rows by y-lines; merge continuation lines (7.5) |
| `docling` | Scanned pages; text pages where `text` fails | Docling `DocumentConverter` with `PdfPipelineOptions(do_ocr=True for scanned, do_table_structure=True, table mode ACCURATE)`; export each table to rows; keep page numbers; read Docling's confidence grades (`mean_grade`, `low_grade`) per page |
| `ai` | Pages where both fail, only with consent + gate | Send the page's Docling markdown (not the image) with PII masking (11.3); receive JSON rows matching the raw-row schema |

### 7.2 Statement summary extraction
From page text (any engine), profile regexes capture: account number (→ mask), statement period start/end, opening balance, closing balance, total debits, total credits, currency. Missing values are `None`, never guessed.

### 7.3 Engine router (per statement)
1. Pages marked `text` → `text` engine. Pages marked `scanned` → `docling` (OCR on).
2. After normalization + validation (Section 8, 9): if a statement has **0 rows**, or **> 5% MISMATCH rows**, or **verdict `NEEDS_REVIEW` caused by a column/structure problem**, re-run the failing pages with the next engine (`text → docling → ai`). `ai` only if `ai_consent=granted` and the gate passes (11.2); otherwise stop and leave `NEEDS_REVIEW`.
3. Keep the best result per page by score: fewest MISMATCH rows, then totals-check pass, then more rows. Record in `order.json` which engine won per page and why.
4. Thresholds (`fallback_mismatch_ratio: 0.05`, `min_rows: 1`) live in `config/settings.yaml`.

### 7.4 Profiles
- `profiles/<id>.yaml`: `id`, `display_name`, `fingerprints` (strings/regexes that identify the layout on page 1), `direction` (`asset|liability`), `header_aliases` (date/description/debit/credit/amount/balance → list of header texts), `amount_style` (`separate_columns|signed_single|dr_cr_suffix`), `decimal_separator` (`.`|`,`), `thousands_separator`, `negative_patterns` (`parentheses`, `trailing_minus`, `leading_minus`, `CR/DR`), `date_formats` (list of strptime patterns, tried in order), `date_order` hint, `year_source` (`in_date|period`), `summary_patterns` (named regexes), `noise_patterns` (page headers/footers/"continued" lines/balance-forward lines to drop), `row_order` (`chronological|reverse|auto`), optional fixed `columns` x-ranges.
- `profiles/generic.yaml` is the fallback: common English header aliases, auto date order, auto row order.
- Auto-detect: first profile whose fingerprints all match page 1 text; else `generic`. Operator can force `--profile <id>`.
- `stmtconv profile scaffold <order_id> <file>` dumps page-1 words, detected headers, candidate column x-ranges and summary-line candidates into `work/profile-draft.yaml` for the operator to finish. Client data in the draft stays inside the order folder; a profile committed to `profiles/` must contain no client data (only layout facts).
- Multiple statements in one file: V1 detects a new statement when a new "opening balance"/period header appears after transactions *(inferred)*; the operator can also split with `--pages 1-4,5-9`.

### 7.5 Row assembly rules
- A line with a parsable date in the date column starts a new transaction. A line without a date but with description text and no amounts is appended to the previous transaction's description (space-joined). A line without a date but with amounts starts a new transaction that inherits the previous date *(inferred; common "same-day" layout)* and is marked `date_inherited=true`.
- Drop noise lines matching profile `noise_patterns` and repeated table headers on every page.
- "Balance brought forward / opening balance" lines are not transactions; they feed `opening_balance` if the summary has none.
- Tables continuing across pages are one sequence; order preserved by page then y.

---

## 8. Normalization

### 8.1 Amounts
- Strip currency symbols and codes, spaces, thousands separators per profile.
- Negative if: parentheses `(123.45)`, trailing minus `123.45-`, leading minus, suffix `DR`/`CR` per profile meaning, or the value sits in the debit column.
- Output: `debit` and `credit` as non-negative Decimals (one of them empty), plus signed `amount` = credit − debit (asset) for single-column exports.
- Unparsable amount text → row flag `AMOUNT_UNPARSABLE` (never zero-filled).

### 8.2 Dates
- Try profile `date_formats` in order; generic fallback set covers `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM-DD`, `DD Mon YYYY`, `Mon DD`, `DD Mon`, `DD-MM-YY`.
- **Date-order ambiguity:** if `date_order=auto` and every parsed date has day ≤ 12, the statement is flagged `DATE_ORDER_AMBIGUOUS` → verdict `NEEDS_REVIEW` until the operator sets `date_order`. If any day > 12 proves the order, use it for the whole statement.
- **Year inference** for dates without a year: use statement period; if the period spans a year boundary, months ≥ start month take the start year, others the end year. No period → flag `YEAR_UNKNOWN`.
- Weekday tokens (`TUE`) are stripped before parsing (QuickBooks rejects them).
- Every date must lie inside the statement period ± 7 days *(inferred)*; otherwise flag `DATE_OUT_OF_PERIOD`.

### 8.3 Descriptions
Collapse whitespace, keep original case, strip leading/trailing punctuation noise, keep reference numbers. Keep `raw_text` unchanged for provenance. A description that is only digits gets flag `DESC_NUMERIC` (QuickBooks import issue).

### 8.4 Row order
If `row_order=auto`, validate both chronological and reverse; choose the one with fewer MISMATCH rows; output always chronological (oldest first).

---

## 9. Validation

### 9.1 Row check (running balance)
For each row with a printed balance and a previous balance (previous row or opening balance):
- asset: `prev − debit + credit == balance`
- liability: `prev + debit − credit == balance`
- Tolerance `balance_tolerance: 0.01` (settings). Pass → `OK`; fail → `MISMATCH` with `expected` and `difference`. Row without printed balance → `UNVERIFIED` and the chain continues from the computed balance *(inferred)*.

### 9.2 Statement checks
1. Opening balance vs first row's previous balance.
2. Closing balance vs last computed balance.
3. If totals printed: sum(debits) and sum(credits) vs printed totals.
4. `opening ± net movement == closing` (direction-aware).
5. Duplicate detection: same date + amount + description within the statement → `POSSIBLE_DUPLICATE` warning (not an error; banks do repeat).
6. Page coverage: every page with transactions produced ≥ 1 row, or is marked as a summary/blank page.

### 9.3 Verdicts
| Verdict | Condition |
|---|---|
| `VERIFIED` | All rows OK or UNVERIFIED-with-chain-closing, opening and closing match, no blocking flags |
| `VERIFIED_BY_TOTALS` | No running balances printed, but opening + movement = closing and printed totals match |
| `VERIFIED_WITH_FIXES` | `VERIFIED` after operator review changed ≥ 1 row |
| `NEEDS_REVIEW` | Any MISMATCH, failed statement check, or blocking flag (`AMOUNT_UNPARSABLE`, `DATE_ORDER_AMBIGUOUS`, `YEAR_UNKNOWN`, `DATE_OUT_OF_PERIOD`) |
| `UNVERIFIABLE` | No balances and no opening/closing/totals available; operator must acknowledge with `--accept-unverifiable` and delivery note says so |

### 9.4 Multi-statement merge
When `merge=true` and statements share an account mask: sort by period; check `closing(n) == opening(n+1)` (flag `CONTINUITY_GAP` with amount) and no overlapping/missing periods (flag `PERIOD_GAP`/`PERIOD_OVERLAP`). Merged workbook: one sheet per month + `All Transactions` + `Summary` (monthly opening/closing/debits/credits/count/verdict).

---

## 10. Review & spot-check

1. `stmtconv review <order_id>` writes `review/<statement>-review.xlsx`: all rows with `Row ID`, `Page`, `Engine`, `Check`, `Expected`, `Difference`, `Flags`, then editable `Fix Date`, `Fix Description`, `Fix Debit`, `Fix Credit`, `Fix Balance`, `Action` (`keep|fix|delete|insert_after`), `Note`. Problem rows highlighted (MISMATCH yellow, blocking flags orange); an `Issues` sheet lists statement-level problems with the page to look at.
2. Operator edits in Excel, saves, runs `stmtconv apply-review <order_id>`. The tool re-reads fix columns (validates types, rejects unknown actions with row numbers), applies them, marks `fixed_by=review`, re-validates, updates verdicts and `manual_fixes`.
3. Round trips repeat until no `NEEDS_REVIEW` remains or the operator exports with `--allow-unverified`.
4. `stmtconv spotcheck <order_id>` samples `spot_check_rows: 10` random rows per statement (seeded by order id) plus every fixed row, prints page + row data for comparison, and records `passed/failed` + note via prompt. Export is blocked until spot-check is recorded (can be skipped only with `--skip-spotcheck`, which the delivery note records).
5. Review budget target: ~5 minutes per statement (roadmap); the ledger records review time for pricing.

---

## 11. Optional cloud AI fallback

### 11.1 Purpose
Rescue pages that `text` and `docling` cannot parse (unusual layouts). Off by default. Never used for categorization or anything else in V1.

### 11.2 AI gate (all must pass)
1. Operator explicitly activates AI for the command/order.
2. Order has recorded client consent and a nonempty consent note.
3. A configured provider/model has usable credentials where required and the operator confirms provider data-handling terms are suitable for sensitive data. Billing status alone is not proof.
4. The per-order page cap is not exceeded.

### 11.3 Data minimization
Send only masked transaction-table text for failing pages, never images, file names, or header blocks. Mask account/card numbers, names when available, emails and phone numbers. Logs contain operational metadata only. Local/self-hosted endpoints still require deliberate activation and clear routing.

### 11.4 Output handling and model settings
Use a guided CLI menu to add named OpenAI-compatible endpoints, enter keys privately, test connections, discover or manually enter models, and choose reasoning effort. Show Max only when supported; otherwise clearly label the highest supported level or provider default. Refresh capabilities on model changes. Never silently change requested effort/model/provider. Keep keys/personal configuration out of Git.

Provider adapters explicitly handle endpoint routes, effort parameters and schema support. Validate JSON outputs and bounded retries even when native structured output is unavailable. Returned rows use the same normalization and financial checks; failures remain NEEDS_REVIEW. Tests use fake clients and never call paid APIs. See CODEX-PROJECT-PLAN for detailed acceptance cases.

---

## 12. Exports

All exporters read validated `Statement` objects only. Column specs, header names and date formats come from `config/exports.yaml`.

### 12.1 Client Excel workbook (`<order_id>-<account_mask>-<period>.xlsx`)
- **Transactions:** Date (real Excel date, format from order), Description, Debit, Credit, Balance, Check, Category (if enabled), Page, Source file. Numbers as numeric cells with `#,##0.00`; MISMATCH rows yellow; frozen header; autofilter; column widths set.
- **Summary:** account (masked), period, currency, opening, closing, total debits, total credits, rows, mismatches, fixes, verdict, verification sentence from template (e.g. "218 transactions · running balance verified on every row · 2 rows corrected manually (page 7)").
- **Issues:** only if any flags remain or were fixed: row/page/flag/resolution.
- Merged orders: sheets per 9.4.

### 12.2 QuickBooks Online CSV
- `qb_csv3`: `Date,Description,Amount` — amount signed (money in positive, money out negative).
- `qb_csv4`: `Date,Description,Credit,Debit` — header words exactly `Credit`/`Debit`, no "Amount". Operator maps columns during upload; the delivery note explains which column is money in.
- Rules from Intuit's format guide: one date format for the whole file (order's `output_date_format`); no zeros — empty cells instead; no currency symbols or thousands separators; no weekday text in dates; flag numeric-only descriptions.
- Split into files of at most `qb_csv_max_rows: 1000` rows *(reported by third parties as a per-upload limit; configurable)*, suffix `-part1`, `-part2`.
- Credit-card orders: add a note that the file must be uploaded to a credit-card account in QuickBooks.

### 12.3 Xero CSV
Columns `Date, Amount, Payee, Description, Reference` (Payee empty unless categorization provides it; Reference = cheque/reference number if detected). Amount single column, income positive, expenses negative, no currency symbols or thousands separators. Date format: one of Xero's accepted `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY/MM/DD`, chosen per order.

### 12.4 Generic CSV
All Transaction fields incl. check, flags, page, engine; UTF-8 with BOM (so Excel opens non-ASCII correctly), comma-separated, ISO dates.

### 12.5 OFX 1.02
SGML-style OFX with `BANKMSGSRSV1` (asset) or `CREDITCARDMSGSRSV1` (liability); `CURDEF` from order currency; `BANKACCTFROM`/`CCACCTFROM` with masked account id; `DTSTART`/`DTEND` from period; one `STMTTRN` per transaction with `TRNTYPE` (`DEBIT`/`CREDIT`), `DTPOSTED`, `TRNAMT` signed, deterministic `FITID` = first 16 hex chars of SHA-256 over `account_mask|date|amount|normalized description|occurrence index`, `NAME` (≤ 32 chars) and `MEMO` (full description); `LEDGERBAL` = closing balance at period end. Accepted by QuickBooks Online and Xero uploads (research). `.qbo` Web Connect is V2.

### 12.6 Categorization (optional per order)
`config/categories.yaml`: ordered rules `{category, match: [keywords or regex], direction: debit|credit|any}`; first match wins; client-specific rules in `workspace/orders/<id>/categories.yaml` override. Uncategorized rows get `Uncategorized` and appear in a Summary count. Category column added to Excel and Xero `Payee`/description is unchanged.

---

## 13. CLI (command inventory)

| Command | Purpose |
|---|---|
| `doctor` | Checks Python version, venv, models present, offline flag, free disk, workspace writable, disk-encryption reminder, `.env` keys present (never prints values) |
| `models download` | Pre-download Docling models to `models/` |
| `order new --platform fiverr --alias "…" [--package …]` | Create order folder + manifest |
| `order list` / `order show <id>` | List/inspect orders (status, verdicts) |
| `intake <id> [--password] [--combine] [--force]` | Analyze files, write file table, print quote |
| `quote <id>` | Print price/time quote |
| `extract <id> [--profile] [--pages] [--engine auto|text|docling] [--ai]` | Run router, normalize, validate |
| `validate <id>` | Re-run validation only |
| `review <id>` / `apply-review <id>` | Review round trip |
| `spotcheck <id>` | Sample and record spot-check |
| `export <id> [--allow-unverified] [--skip-spotcheck]` | Write outputs per `order.outputs` |
| `deliver <id>` | Build zip, delivery note, data-handling statement |
| `close <id> [--yes]` | Delete input/work/review/output, keep manifest skeleton + certificate, append ledger |
| `profile scaffold <id> <file>` / `profile test <profile> <pdf>` | Profile authoring helpers |
| `run <id>` | Default chain: intake → extract → review (if needed) or export |
| `selftest` | Generate synthetic corpus in a temp folder and run the full pipeline; prints pass/fail table |
| `stats` | Aggregates from ledger: pages, sec/page by kind and engine, verdict mix, review minutes |

Every command prints a short Rich summary and exits non-zero on failure. Messages are in `stmtconv/cli/messages.py` constants (English only in V1; no i18n requirement for an operator tool).

---

## 14. Delivery, retention & privacy

### 14.1 Delivery package
`delivery/<order_id>.zip` contains `output/*`, `DELIVERY-NOTE.txt` (from `templates/delivery_note.md`: counts, verdicts, manual fixes with pages, file guide, import tips for QuickBooks/Xero), `VERIFICATION-SUMMARY.txt`, and `DATA-HANDLING.txt` (from `templates/data_handling.md`: processed locally on an encrypted laptop, no cloud AI unless consented, files deleted within `retention_days_after_delivery: 7` days of completion, deletion certificate on request). Placeholders are filled from order data only.

### 14.2 Close & deletion
`close <id>`: deletes `input/`, `work/`, `review/`, `output/`, `delivery/`, re-checks nothing remains, writes `deletion_certificate` into `order.json` (order id, file names' SHA-256 hashes, deleted_at UTC, statement "files deleted from operator workstation"), and prints the certificate text for the client. Order manifest keeps only non-sensitive fields (counts, verdicts, timings, hashes). The certificate states plainly that deletion is logical deletion on an encrypted disk (SSD overwrite is not guaranteed) *(research note)*.
`order list --overdue` lists delivered orders older than the retention window.

### 14.3 Operator environment (documented, checked by `doctor` where possible)
Full-disk encryption on (BitLocker/Windows Device Encryption), Windows login password, workspace outside cloud-synced folders (OneDrive/Dropbox), antivirus on. `doctor` warns if the workspace path is inside a OneDrive folder.

---

## 15. Logging, metrics & errors

### 15.1 Logging
Python `logging` with JSON lines to `workspace/logs/stmtconv.log` (rotating 5 × 5 MB) and Rich console. Levels via `STMTCONV_LOG_LEVEL`.

### 15.2 Redaction
A logging filter masks digit runs ≥ 8 (keep last 4), emails, and any string attached to fields named `description`, `raw_text`, `payee`, `name`. Tests assert a sample transaction never appears in log output.

### 15.3 Ledger (`workspace/ledger.jsonl`)
One line per closed order: order_id, platform, package, pages by kind, statements, engines used per page count, seconds per stage, verdict counts, manual fixes, review minutes, AI pages used. No client alias, file names, or amounts.

### 15.4 Errors
`StmtconvError` hierarchy with `code` (e.g. `INTAKE_UNSUPPORTED_TYPE`, `PDF_PASSWORD_REQUIRED`, `ORDER_STATE`, `PROFILE_INVALID`, `EXPORT_BLOCKED_UNVERIFIED`, `AI_GATE_CLOSED`), operator-readable message, and next-step hint.

---

## 16. Environment variables & config files

```
STMTCONV_WORKSPACE=
STMTCONV_LOG_LEVEL=INFO
STMTCONV_NUM_THREADS=4
STMTCONV_OFFLINE=true
DOCLING_ARTIFACTS_PATH=
STMTCONV_AI_PROVIDER=
STMTCONV_AI_MODEL=
STMTCONV_AI_EFFORT=provider_default
STMTCONV_AI_API_KEY=
STMTCONV_AI_TERMS_CONFIRMED=false
```
BYOK variables above are planned, not implemented. Provider endpoints and personal model selections will live in ignored local settings; exact names are finalized in Phase 9.

Config files: `config/settings.yaml` (thresholds, defaults, retention, limits), `config/pricing.yaml`, `config/categories.yaml`, `config/exports.yaml`, `profiles/*.yaml`, `templates/*.md`. Details in `docs/ENVIRONMENT.md`.

---

## 17. Build phases

Each phase: implement → run `python scripts/check.py` → run `python -m stmtconv selftest` (from Phase 4 on) → pass acceptance → update `docs/PROGRESS.md` → stop for review.

### Phase 0 — Clone, set up & explore Docling (exploration only, hard checkpoint)
Clone a pinned Docling release into ignored `vendor/docling`; record its commit/version. Use a Python 3.12 environment and CPU-only dependencies. Download the required local model artifacts explicitly. Explore synthetic digital, scanned and simulated-photo statements, Markdown/JSON/HTML outputs, tables including borderless/multi-page layouts, OCR, confidence grades, timing and memory. Compare rows with known truth and include a tables-to-Excel experiment. Try additional input formats and a free alternate OCR engine where feasible; document unrun/blocked checks honestly. Word/Excel imports and a local API/UI server are optional research. Use ignored `explore/` for inputs/outputs and versioned `research/phase0/` for reproducible experiment helpers.
**Accept:** successful offline Docling conversion on three synthetic document types, measured output-quality/performance report with no paid service or real client data; document cloud hardware separately from outstanding Windows/actual-photo checks. Migration/setup/research files are allowed by the owner's current instruction; no product code in Phase 0. Use the exploration runner as the gate because `scripts/check.py` starts in Phase 1. Stop for owner review before Phase 1 and record the decision in PROGRESS.

> **Phases 1–10 below are the draft plan**, written before exploration. After the Phase 0 review, update them (with the owner's approval) before starting Phase 1.

### Phase 1 — Foundation
`pyproject.toml` (pinned deps, dev extras), `src/stmtconv` package skeleton with all module folders, Typer CLI with `--help` and `doctor`, pydantic-settings config reading `.env` + `config/settings.yaml`, logging with redaction filter, error hierarchy, `scripts/check.py` (`--quick`: ruff check + mypy + `pytest -m "not slow"`; full: ruff check, ruff format --check, mypy, all pytest incl. slow Docling tests), `.env.example`, config YAML stubs with schemas, `models download` command, workspace creation.
**Accept:** `python scripts/check.py` passes on Windows PowerShell; `python -m stmtconv --help` lists all Section 13 commands (unbuilt ones print "not implemented in this phase"); `doctor` reports Python 3.12, venv active, workspace path, models status, and warns when the workspace is under OneDrive; a test proves a 12-digit number and a description passed to the logger are masked.

### Phase 2 — Orders, intake & synthetic corpus
Order model + atomic manifest writes + state machine; `order new/list/show`; intake (type sniffing, SHA-256, page count, per-page text/scanned/blank detection, password handling, photo → PDF with EXIF rotation, combine); quote from pricing.yaml; synthetic statement generator in `tools/synth/` (reportlab) producing PDFs + ground-truth JSON for 3 layouts (separate debit/credit + balance; single signed amount + balance; credit card liability without running balance) with multi-line descriptions, page breaks, parentheses negatives, and a scanned variant (rasterized 200 dpi, slight rotation and noise via Pillow).
**Accept:** tests for every legal/illegal status transition; intake of the synthetic set reports correct page counts and text/scanned kinds; a password-protected synthetic PDF is rejected without password and processed with it, and the password appears in no file or log; `quote` on a 12-page scanned order returns the Standard package with the scanned surcharge.

### Phase 3 — Core model, normalization & validation
`core` models (Transaction, Statement, RowCheck, Verdict, flags), money parsing, date parsing with ambiguity detection and year inference, description cleanup, multi-line assembly from raw rows, row-order detection, running-balance validation (asset and liability), statement checks, verdict rules, duplicate warning, multi-statement continuity checks. Pure functions, no PDFs.
**Accept:** table-driven tests cover every amount pattern in 8.1 (incl. `(1,234.56)`, `1.234,56`, `123.45-`, `45.00 DR`) and every date rule in 8.2 (incl. an all-days-≤12 statement → `DATE_ORDER_AMBIGUOUS`, Dec→Jan year rollover); validation tests show a single wrong digit anywhere in a 50-row statement produces MISMATCH on that row and verdict `NEEDS_REVIEW`; hypothesis test: formatting then parsing random Decimals round-trips exactly; mypy strict passes on `core`.

### Phase 4 — Text engine, profiles & router skeleton
Extractor interface; pdfplumber `text` engine (header detection, column x-ranges, line grouping, noise removal, continuation lines, cross-page continuation); summary extraction; profile schema + loader + auto-detect + `generic.yaml` + 3 synthetic-layout profiles; `profile scaffold` and `profile test`; `extract` and `validate` commands; router step 1 (text only); `selftest` command for text PDFs.
**Accept:** `selftest` on the 3 text layouts (3 statements each, ≥ 2 multi-page) reproduces ground truth exactly (100% rows, amounts, dates) with verdict `VERIFIED` or `VERIFIED_BY_TOTALS`; a statement with one digit altered in the PDF yields exactly one MISMATCH row and `NEEDS_REVIEW`; no bank-specific strings exist in `src/` (test greps profiles' fingerprints against source).

### Phase 5 — Docling engine, OCR & full router
`docling` engine (converter built once per run, ACCURATE tables, OCR only for scanned pages, RapidOCR, thread count from config, offline mode), table → raw rows mapping via profile header aliases, confidence grades captured per page, router fallback and best-result selection per 7.3, timing per page into order timings.
**Accept:** scanned synthetic statements: ≥ 98% of rows exact vs ground truth **and 100% of wrong rows flagged** (zero silent errors); a text statement whose layout breaks the text engine (synthetic "borderless wrapped" layout) is rescued by the docling fallback and the manifest records the engine switch; per-page timings are recorded and printed by `order show`; conversion runs with networking disabled after `models download`.

### Phase 6 — Exports & review loop
Excel client workbook (12.1), QuickBooks CSV 3/4-column with splitting (12.2), Xero CSV (12.3), generic CSV (12.4), export blocking rules (Rule 3.6), review workbook, `apply-review` with fix/delete/insert actions, verdict `VERIFIED_WITH_FIXES`, spot-check sampler and recording.
**Accept:** golden-file tests for each CSV format (byte-identical to fixtures); exported QB CSV has no `0` cells, no currency symbols, one date format; Excel opens with numeric cells and highlighted MISMATCH rows (openpyxl reload test checks types and fills); a review round trip that fixes one MISMATCH row turns the verdict into `VERIFIED_WITH_FIXES` and `manual_fixes=1`; export is refused for `NEEDS_REVIEW` without `--allow-unverified` and for missing spot-check without `--skip-spotcheck`.

### Phase 7 — Merge, categorization & OFX
Multi-statement merge with continuity checks and merged workbook; categorization rules engine with order overrides; OFX 1.02 writer for bank and credit-card statements with deterministic FITIDs.
**Accept:** 12 synthetic monthly statements merge into one workbook with 12 month sheets + All Transactions; removing month 5 produces `PERIOD_GAP`, altering month 7's opening produces `CONTINUITY_GAP` with the exact amount; categorization tests for rule order, direction filter and order override; OFX output is byte-identical across two runs, parses back with a round-trip test, and FITIDs are unique per transaction including same-day identical amounts.

### Phase 8 — Delivery, retention & metrics
`deliver` (zip, delivery note, verification summary, data-handling statement from templates), `close` with deletion certificate, ledger append, `order list --overdue`, `stats`, `run` default chain.
**Accept:** after `close`, a directory walk finds no client file in the order folder and the manifest contains no descriptions or amounts (test scans for sample strings); ledger lines contain none of the order's descriptions, alias or file names; delivery note numbers equal the Summary sheet numbers for the synthetic order; `stats` prints median sec/page by kind.

### Phase 9 — Optional BYOK AI fallback
OpenAI-compatible provider adapters; guided provider/key setup; connection tests; model discovery/manual entry and presets; model picker with supported effort levels up to Max; consent gate, masking, page cap and routing.
**Accept:** fake-provider tests cover discovery/manual models, redacted credentials, endpoint/schema variations, supported and rejected effort, invalid output, and zero network calls when any gate condition is missing. No silent provider/model/effort changes. AI rows are revalidated. API keys/personal settings remain local; current provider terms and paid connection tests are separate owner-authorized checks.

### Phase 10 — Field readiness & polish
`run.bat` drop-folder launcher (creates order for files in `inbox/`, runs `run`), demo-asset generator (fake-data sample workbook + before/after PNG of a synthetic statement for gig images), `docs/OPERATOR_GUIDE.md` (daily workflow, review tips, QuickBooks/Xero import steps, troubleshooting), real-world acceptance run on the roadmap's 15-document checklist using the owner's anonymized/public samples, performance notes in PROGRESS.
**Accept:** on a fresh clone, following OPERATOR_GUIDE from `git clone` to first delivered synthetic order works end to end; the 15-document checklist (5 layouts, 3 scanned/photo, 2 × 20+ pages, 2 bracket-negatives, 3 invoices *(invoices are recorded as "out of scope V1, rejected cleanly")*) is recorded in PROGRESS with rows matched, balances matched, mismatches explained, and sec/page; `selftest` passes.

---

## 18. Assumptions & notes for the owner

- **Competition is real.** Self-serve tools cost ~$0.13–$0.50/page and QuickBooks Online now reads statement PDFs itself. Sell verification, review, messy/scanned documents, multi-month merges and privacy — not "conversion". (RESEARCH §3)
- **Never use a provider whose terms are unsuitable for client data.** Its terms allow Google to use the content to improve products; this spec blocks it by design. For testing prompts, use synthetic statements only.
- **Bookkeeper compliance angle.** US bookkeepers/tax preparers are treated as "financial institutions" under the FTC Safeguards Rule and must oversee service providers; your data-handling statement and deletion certificate directly help them. This is not legal advice; don't claim "compliance" — describe your practices.
- **Docling is not magic on bank statements.** Borderless tables, wrapped rows and page-spanning tables are known weak spots for table models; that's why the text engine is primary for digital PDFs and validation decides.
- **OCR on your CPU is slow.** Price scanned work higher (the +25% add-on may be low; measure with `stats`).
- **Photos of statements** vary wildly; decline or quote higher when balances can't be verified.
- **QuickBooks upload limits** (1,000 rows, file size) are third-party reports; the split setting is configurable.
- **Invoices** were in the roadmap's test list and customization table but are V2 here to keep V1 focused on the repeatable bank-statement niche.

## Appendix A — Historical roadmap items changed by research

The Gemini-only R1 entry below is superseded by ADR-014; retained to explain history.

| # | Roadmap said | Spec does | Why | Refs |
|---|---|---|---|---|
| R1 | Gemini free tier for AI extraction | Paid tier only + client consent + masking | Free-tier content may be used by Google | 11, ADR-005 |
| R2 | Docling converts every PDF | pdfplumber text engine first; Docling for scanned/fallback | Bank-statement tables are a known weak spot for table models; text engine is faster on CPU | 7, ADR-003 |
| R3 | QuickBooks CSV "Date, Description, Amount" | 3-col and 4-col, blank-not-zero, one date format, row splitting, credit-card note | Intuit's format guide rules | 12.2 |
| R4 | Excel + QB CSV | + Xero CSV + OFX | Competitors ship QBO/OFX; OFX works in QBO Online and Xero | 12.3, 12.5 |
| R5 | Scripts in `scripts/convert.py` | Installable package + CLI + order workflow | Repeatable service delivery, testability | 3, 13 |
| R6 | "Delete files after delivery" | `close` command + deletion certificate + retention window | Sellable privacy proof for bookkeepers | 14 |
| R7 | Floats implied by pandas | Decimal end-to-end, pandas not required | Money accuracy | 3.2, ADR-004 |

## Appendix B — Open questions for the owner
1. Which client regions first — US only, or also UK/Canada/Australia? This sets default date order and output date formats (currently: per-order choice, default `MM/DD/YYYY` for QuickBooks US).
2. Answered: optional BYOK OpenAI-compatible AI with model and effort selection; configure provider details when Phase 9 begins. No key is needed for local exploration.
3. Should credit-card statements be offered from day one (spec says yes)?
4. Is your laptop's disk encrypted (BitLocker/Device Encryption)? Which Windows edition (Home/Pro)?
5. What business/brand name should appear in delivery notes and the data-handling statement?
6. Do you want invoices moved into V1 after Phase 8, or kept for V2?
7. Answered: Codex cloud development, GitHub source versions, later clone/install on another device.
