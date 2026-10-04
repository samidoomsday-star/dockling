# Research — Statement Converter (26 September 2026)

> Background for `docs/SPEC.md`. Informs decisions; **not** requirements. If anything here conflicts with SPEC, SPEC wins. Prices and terms change; re-check before quoting them to clients.

## 1. Docling today

- **Status:** actively released; v2.106.0 shipped 23 June 2026 and the ecosystem (docling-serve, docling-java) had releases through September 2026. MIT license, LF AI & Data project, IBM origin.
  Source: https://github.com/docling-project/docling/blob/main/CHANGELOG.md · https://pypi.org/project/docling-serve/
- **Python:** 3.9 support was dropped in 2.70.0; related Docling packages support 3.10–3.14. Python 3.12 is a safe pin.
  Source: https://github.com/Baho73/docling (README mirror) · https://pypi.org/project/langchain-docling/
- **Install:** `pip install docling`; runs on Windows/macOS/Linux, x86_64 and arm64. Models depend on PyTorch; a CPU-only torch index is available for Linux.
  Source: https://docling-project.github.io/docling/getting_started/installation/
- **OCR engines:** RapidOCR (default since v2.56), EasyOCR, Tesseract (system install, `TESSDATA_PREFIX`), OcrMac, OnnxTR plugin, Nemotron (Linux + CUDA only — irrelevant here).
  Source: installation page above · https://github.com/docling-project/docling/discussions/2451
- **Speed:** OCR is the most expensive stage. Docling's own benchmark measured EasyOCR at roughly 13 s/page on an x86 CPU versus 1.6 s on an L4 GPU. On the owner's i5-8250U, scanned pages will be slow; measure and price accordingly.
  Source: https://blog.gopenai.com/using-doclings-ocr-features-with-rapidocr-a757fbc1e7c8
- **Confidence grades:** since v2.34 each conversion has page- and document-level grades (`POOR/FAIR/GOOD/EXCELLENT`) for layout, OCR and parse quality; the table score is not implemented yet. Useful to prioritize review, not a substitute for balance checks.
  Source: https://docling-project.github.io/docling/concepts/confidence_scores/
- **Known table weaknesses:** open issues report tightly spaced columns being merged/split, rows of varying height scattered across rows, and merged cells misread — exactly the traits of many bank statements.
  Source: https://github.com/docling-project/docling/issues/2756 · https://github.com/docling-project/docling/discussions/2241
- **Speed comparison:** a third-party benchmark (512 docs) measured Docling at ~0.6 pages/s (with a GPU) but with the best scores on difficult tables; fast heuristic extractors were far quicker but weaker on irregular layouts.
  Source: https://pypi.org/project/fibrum-pdf

**Implication:** use pdfplumber word geometry as the primary engine for digital PDFs (fast, controllable with bank profiles), Docling for scanned pages and as a fallback, and let balance validation pick the winner. (SPEC 7, ADR-003)

## 2. Why bank statements are hard

- Bank statement tables are long, span pages, and have densely packed multi-line rows; general table-structure models don't generalize well to them.
  Source: https://arxiv.org/html/2412.12827v1 (TabSniper)
- Production experience: columns are implied by spacing, rows by alignment; treating each physical line as a row splits transactions; table-like non-transaction blocks get mis-extracted without semantic checks.
  Source: https://www.infoq.com/articles/redesign-pdf-table-extraction/
- An existing extractor on Apify uses pdfplumber for ruled tables and word-position clustering for line-less statements, charges $30 per 1,000 pages, flags scanned pages instead of guessing, and does not merge running balances across pages.
  Source: https://apify.com/automation_curious/pdf-table-bank-statement-extractor

**Implication:** explicit multi-line row logic, noise-line removal, cross-page continuation, and validation (SPEC 7.5, 9).

## 3. Market & competition

- **Self-serve SaaS is crowded.** DocuClipper: $29/month for 60 pages up to $899/month for 5,000 pages (Sept 2026), ~$0.18–$0.48/page, exports CSV/Excel/QBO/OFX etc., reconciles against statement summaries. CapyParse: $29 for 150 pages, $79 for 600. Documentric: free 50 pages/month, $29 for 500. BankXLSX, Lido ($29/month), Parsli, Zedly, SaasAnt also compete.
  Sources: https://bankxlsx.com/blog/best-bank-statement-converter-software · https://capyparse.com/blog/bank-statement-converter-pricing-comparison · https://www.documentric.com/blog/docuclipper-review-2026 · https://www.docuclipper.com/integrations/quickbooks/bank-statements/
- **Reconciliation is table stakes.** DocuClipper advertises comparing extracted totals against the statement summary before import.
  Source: docuclipper.com integration page above
- **QuickBooks Online now ingests statement PDFs/images with its own AI** (in addition to CSV/QBO/QFX/OFX uploads).
  Source: https://quickbooks.intuit.com/learn-support/en-us/help-article/import-transactions/manually-upload-transactions-quickbooks-online/L0rE9OXBz_US_en_US
- **Gap the service can fill:** a G2 reviewer of DocuClipper asked for a per-job rate for one-time use — subscription tools fit poorly for one-off year-end catch-ups. Privacy-sensitive users dislike uploading statements to third-party servers.
  Sources: https://www.g2.com/products/docuclipper/pricing · https://www.quickbankconvert.com/blog/comparisons/docuclipper-review-2026
- **Fiverr:** many sellers offer "bank statement PDF to Excel/QuickBooks" gigs starting at $10; some include up to 25 pages in the basic package.
  Sources: https://www.fiverr.com/haseebjee/convert-pdf-to-excel-bank-statements-and-prepare-analysis · https://www.fiverr.com/nidhi/convert-pdf-to-excel

**Positioning:** don't sell "PDF to Excel". Sell *verified* books-ready data: human-reviewed, balance-proven with a written report, messy/scanned/non-US statements, 12-month merges with continuity checks, categorization, per-job pricing, local-only processing with a deletion certificate.

## 4. Import formats

### QuickBooks Online CSV (Intuit guide, updated Sept 2026)
- 3-column `Date, Description, Amount` or 4-column `Date, Description, Credit, Debit`.
- Remove zeros (leave cells blank); fix numeric-only descriptions; header must be `Credit`/`Debit` without "amount"; one date format throughout; strip weekday text from dates; credit-card files go into a credit-card account.
  Source: https://quickbooks.intuit.com/learn-support/en-global/help-article/bank-transactions/format-csv-files-excel-get-bank-transactions/L4BjLWckq_ROW_en
- Only 3- or 4-column layouts are supported (e.g. a 6-column file is rejected).
  Source: https://quickbooks.intuit.com/learn-support/global/importing-and-exporting-data/can-i-upload-bank-transactions-csv-file-in-quickbooks-that-has-6/00/1401242
- Third-party reports: 1,000-transaction limit per CSV upload; a community answer mentions a 350 KB file-size limit. Treat as configurable.
  Sources: https://www.saasant.com/blog/upload-bank-statements-to-quickbooks/ · https://quickbooks.intuit.com/learn-support/en-us/reports-and-accounting/i-am-trying-to-import-my-bank-statements-to-quickbooks-online-i/00/1209704

### Xero CSV
- Only Date and Amount are required; amount in one column, income positive, expenses negative (minus sign or brackets), no currency symbols; dates DD/MM/YYYY, MM/DD/YYYY or YYYY/MM/DD. Optional Payee, Description, Reference, cheque number, analysis code, transaction type.
  Sources: https://central.xero.com/0/article/Import-a-precoded-CSV-bank-statement · https://central.xero.com/0/article/Import-a-CSV-bank-statement

### OFX / QBO Web Connect
- QBO (Web Connect) is OFX with Intuit headers, mainly `INTU.BID`; QuickBooks Desktop requires `.qbo`, QuickBooks Online accepts OFX and QBO.
  Sources: https://accountingconverter.com/tools/ofx-to-qbo · https://bankqbo.com/blog/quickbooks-ofx-file
- `FITID` values prevent duplicate imports; deterministic IDs are good practice.
  Source: https://pypi.org/project/ccparse/

## 5. AI provider terms (Gemini)

- On the free tier, Google uses prompts, files and responses to improve its products, and human reviewers may read them; Google advises against sending sensitive information. Paid-tier (billing linked, prepay) content is not used for product improvement.
  Sources: https://en.wikipedia.org/wiki/Google_AI_Studio · https://ai.google.dev/gemini-api/docs/billing/
- 2026 changes: Pro models left the free tier on 1 April 2026; free tier remains rate-limited.
  Source: https://www.cloudzero.com/blog/gemini-pricing/

**Implication:** cloud AI only on the paid tier, only with client consent, only masked table text (SPEC 11, ADR-005).

## 6. Client compliance context (US)

- The FTC Safeguards Rule (16 CFR Part 314) treats tax preparers — and, per most guidance, bookkeepers handling client financial data — as financial institutions that need a written information security program, including service-provider oversight.
  Sources: https://armourcyber.io/industries/ftc-safeguards-rule-accounting-firms/ · https://bellatorcyber.com/blog/ftc-safeguards-rule-service-provider-oversight-tax-preparers · https://verito.com/blog/wisp-for-bookkeepers-ftc-safeguards-requirements-2026/

**Implication:** a clear data-handling statement and deletion certificate are selling points for US bookkeeping firms (SPEC 14). Describe practices; never claim legal compliance on the client's behalf.
