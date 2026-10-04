# Dockling operator guide

Dockling converts **bank/card statements** on your device. It creates Excel, generic CSV, QuickBooks CSV, Xero CSV and OFX files, checks the numbers, lets you correct rows, and packages the delivery. Invoices are outside V1. This is a development preview: complete the device checklist below before taking paid client work.

## Install on your other device

Follow [ENVIRONMENT.md](ENVIRONMENT.md) from `git clone` through `doctor`, the full checks and `selftest`. Clone **development-phases-2-10**. `main` still has the starter. GitHub stores code, profiles and instructions; each device installs Python, dependencies and about 700 MiB of local models separately. Your API keys and job files stay local.

Use 64-bit Python 3.12, Git, at least 5 GB free space, and Excel or LibreOffice. Keep jobs outside OneDrive/Dropbox and confirm device encryption before real client work. No GPU or LLM API key is required for the normal offline flow.

The Windows commands below run in PowerShell **from your cloned project folder**. Each command uses the project's Python directly; no activation is needed. Replace `JOB` with the ID printed by `order new`. In the cloud, replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

## Practice once with fake data

Generate a fake statement, workbook and before/after images:

```powershell
.venv\Scripts\python.exe -m stmtconv demo
```

Expect files in `workspace\demo`. The images are synthetic, not an accuracy guarantee. This command needs the `[dev]` installation in the setup guide. Choose another empty folder with `demo --output workspace\demo2` if you already generated these files.

Create a practice job:

```powershell
.venv\Scripts\python.exe -m stmtconv order new --platform test --date-order YMD
```

Copy **only the generated PDF** into the printed `input` folder, using File Explorer. Do not copy its ground-truth JSON or sample workbook. Run:

```powershell
.venv\Scripts\python.exe -m stmtconv intake JOB
```

Expect page counts and an estimated quote. Then:

```powershell
.venv\Scripts\python.exe -m stmtconv extract JOB
```

Expect rows, verdict and mismatch counts. Then:

```powershell
.venv\Scripts\python.exe -m stmtconv spotcheck JOB
```

Open the original PDF alongside the terminal. Compare every displayed date, description, debit, credit and balance against the stated source page. Answer yes only if all match. A balanced statement alone cannot prove that dates or descriptions were copied correctly.

```powershell
.venv\Scripts\python.exe -m stmtconv run JOB
```

Expect `Delivered` and a ZIP path in the job folder. Open the ZIP and check its Excel/CSV and delivery note. **Delivered means a local package was created; Dockling does not send it to a client.**

## Daily job flow

Create one job per client/order. The default outputs are Excel and generic CSV. Choose the actual statement currency and numeric date order when known:

```powershell
.venv\Scripts\python.exe -m stmtconv order new --platform direct --alias ClientA --currency USD --date-order DMY --outputs excel,csv,qb_csv3,xero_csv
```

Use an alias rather than a real name. `DMY` means day/month/year; `MDY` means month/day/year; `YMD` means year/month/day. `auto` pauses on ambiguous numeric dates. Output dates use the configured output format independently. Amounts currently use two decimal places: do not use this release for currencies requiring different precision.

Put PDF/JPEG/PNG/TIFF statements into its printed `input` folder. Then `intake JOB`, `quote JOB` if needed, `extract JOB`, review if requested, `spotcheck JOB`, `run JOB`. `run` performs the remaining steps and intentionally pauses for source checks/review. Exit code 2 means a planned pause, not successful delivery.

For a password-protected PDF, use `intake JOB --password`; enter its password in the hidden prompt. Never put a password in the command itself. For consecutive image pages, number filenames `001`, `002`, etc., then use `intake JOB --combine`. Check image order before extraction.

Extraction normally treats each input file as one statement. If one PDF contains several statements, use explicit page boundaries, for example `extract JOB --pages "1-4,5-9"`. It does not automatically find every period boundary. For unknown/scanned layouts, use a known profile with `--profile PROFILE_ID`; The filenames in `profiles/` show the available profile IDs. A new bank layout may need a profile developed here with synthetic examples. OCR cannot rescue every borderless table.

### Double-click launcher

Create an `inbox` folder beside `run.bat`. Drop only statement PDFs/images into it, then double-click `run.bat`. It **moves** these files into a new job's `input` folder, prints its ID and runs the default flow. Review/spot-check pauses are expected. Continue that same ID using the commands above. Do not drop copies again, which would create a second job. To customize currency, outputs, profiles or date order, use `order new` instead.

If the launcher errors, use `order list` and inspect the printed job's input folder before retrying. Keep any original backup under your own retention policy; close only removes the tracked job copy.

## Correct rows in Excel

If extraction says `NEEDS_REVIEW` or `UNVERIFIABLE`, run:

```powershell
.venv\Scripts\python.exe -m stmtconv review JOB
```

Open the printed review workbook. Keep its row IDs and original columns intact. Use the `Fix*` columns for replacements, and set `Action` to `fix`, `delete` or `insert_after`. A replacement date can be an Excel date or `YYYY-MM-DD`; amounts must be exact numbers, not formulas. For `insert_after`, fill the replacement date/description/movement and any printed balance. Do not physically delete worksheet rows. Save and close Excel before:

```powershell
.venv\Scripts\python.exe -m stmtconv apply-review JOB
```

Checks run again. Unresolved errors stay visible. Repeat review and source comparison until corrected, then `spotcheck JOB` and `run JOB`. If the source itself is unreadable or does not reconcile, clarify with the client; do not invent an amount. Explicit `export --allow-unverified`, `--accept-unverifiable` or `--skip-spotcheck` are exceptional overrides, with disclosures; they do not make the result verified.

If you selected the wrong input numeric date order, create a replacement order with the correct `--date-order`, copy the input there, and abandon the old job. Never manually edit manifests to bypass checks. Re-extracting an existing job resets its review and spot-check results.

## Import into accounting software

Keep a backup/test company first. Dockling creates import files but does not log into QuickBooks/Xero or upload them. Their import screens vary by product/version; actual imports remain device acceptance checks.

- **QuickBooks:** choose `qb_csv3` (Date, Description, Amount) or `qb_csv4` (Date, Description, Credit, Debit), open the bank-transaction upload/import screen, choose the correct account, match the headers and preview debits/credits/date order. Large files split at the configured row limit; import each once.
- **Xero:** choose `xero_csv`, open the relevant bank account's statement import, upload the file and match headers/date format. Confirm a withdrawal and deposit before accepting the preview.
- **OFX:** choose `ofx` only after confirming account identity. If the source lacks a full account identifier, use `order new --account-group YOUR_PRIVATE_ACCOUNT_LABEL --confirm-account --outputs excel,ofx`. Card/bank sign behavior must be checked in a test import. A masked last-four account alone does not identify an account.
- **Merge:** `--merge --account-group YOUR_PRIVATE_ACCOUNT_LABEL --confirm-account` explicitly confirms that the statements concern the same account. They must also match currency and asset/card direction. Missing periods, overlap or a closing/opening difference are flagged, not hidden. Categories are optional (`--categorize`) and configured in YAML; review them before import.

## Deliver and clean up

Review the local ZIP and send it yourself through your agreed channel. Copy anything you need to deliver **outside the job folder before closing**, because close removes its input, extracted data, review sheets, output and ZIP.

After the agreed retention period:

```powershell
.venv\Scripts\python.exe -m stmtconv close JOB
```

The command asks you to confirm removal; answer yes only after saving/sending what you need. Only the scrubbed manifest/certificate remains, plus an anonymous metrics ledger. This certifies logical removal of the tracked local files, not physical disk erasure, backups, client copies or cloud-sync history. A partial deletion reports an error and issues no success certificate; close Excel/programs holding the files and retry. `order list --overdue` helps identify delivered jobs past the configured retention period; deletion is not automatic.

To discard an unfinished/rejected job deliberately:

```powershell
.venv\Scripts\python.exe -m stmtconv close JOB --abandon
```

That removes the tracked job files and records an anonymous abandoned outcome. Use `stats` for counts and measured processing medians.

## Troubleshooting and device acceptance

Use `order show JOB` to inspect status and `doctor` for setup. Error codes identify missing passwords, unsupported files, unresolved reviews, stale workbooks, changed exports or locked files. Share the code and synthetic reproduction here; do not paste client documents, keys, passwords or unredacted manifests/logs. Unknown errors are deliberately generic to prevent private data appearing in tracebacks.

On Windows, verify the full checks and `selftest`, then the fake first-delivery flow above, `run.bat`, Excel review/save/reload, and test accounting imports. Follow the original 15-document checklist with permitted/anonymized/public samples: 5 layouts, 3 real scanned/photo documents, 2 with 20+ pages, 2 bracket-negative statements, 3 invoices rejected as outside V1. Record expected/extracted rows, balance matches, explained mismatches and seconds/page. Our [synthetic cloud report](PHASE10-SYNTHETIC-ACCEPTANCE.json) supplements these checks; it cannot replace real field samples or laptop timings.

Optional AI setup is in [BYOK_GUIDE.md](BYOK_GUIDE.md). Start with the offline flow. No actual paid/model inference call was made during development.
