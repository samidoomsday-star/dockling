# User Flows — Statement Converter

> Derived from `docs/SPEC.md`. Each flow lists steps, edge cases, and spec references. Use these for implementation order and end-to-end tests (`tests/e2e`). If a flow conflicts with SPEC, SPEC wins.
> ⭐ = critical flow (must have an e2e test on synthetic data).

---

## A. Operator flows

### A1. First-time setup ⭐ (SPEC 4, 13)
1. Clone repo, create venv, `pip install -e ".[dev]"`, copy `.env.example` → `.env`.
2. `python -m stmtconv models download` → models in `models/`.
3. `python -m stmtconv doctor` → all checks green or explained warnings.
4. `python -m stmtconv selftest` → pass table.

Edge cases: workspace under OneDrive (warning with fix) · models missing (error with `models download` hint) · wrong Python version (error) · no internet during download (clear retry message).

### A2. New order and quote ⭐ (SPEC 6)
1. `order new --platform fiverr --alias "Buyer K" --package standard` → prints order id and input folder path.
2. Operator copies client files into `input/`.
3. `intake <id>` → file table (pages, text/scanned/blank, password flags) + quote.
4. Operator sends the quote/custom offer on the marketplace.

Edge cases: unsupported file (listed as rejected, rest continues) · password-protected PDF (asks for `--password`) · photos of one statement (`--combine`) · > 500 pages (refused without `--force`) · duplicate file (same SHA-256 → warning, second ignored).

### A3. Convert a digital statement end to end ⭐ (SPEC 7–12)
1. `extract <id>` → per statement: profile used, engine per page, rows, mismatches, verdict.
2. Verdict `VERIFIED` → `spotcheck <id>` → operator compares 10 rows with the PDF → records pass.
3. `export <id>` → files in `output/`.
4. `deliver <id>` → zip + delivery note.

Edge cases: unknown bank → `generic` profile; verdict still decides · statement in reverse order (auto-detected, output chronological) · no running balance (`VERIFIED_BY_TOTALS`) · summary missing (checks that need it are skipped and listed).

### A4. Scanned or photographed statement ⭐ (SPEC 7.1, 7.3)
1. Intake marks pages `scanned`; quote includes the scanned surcharge.
2. `extract` uses Docling with OCR; progress shows sec/page.
3. Mismatches (OCR misreads) → verdict `NEEDS_REVIEW` → flow A5.

Edge cases: very poor image (Docling grade `POOR` + many mismatches) → operator declines or re-quotes (documented in OPERATOR_GUIDE) · rotated pages (auto-rotate) · mixed file (some text pages, some scanned) handled per page.

### A5. Review and fix flagged rows ⭐ (SPEC 10)
1. `review <id>` → opens path of `review/<statement>-review.xlsx`.
2. Operator filters yellow/orange rows, checks the PDF page shown, fills `Fix …` columns and `Action`.
3. `apply-review <id>` → re-validation report; repeat until verdicts are OK.
4. `spotcheck`, `export`, `deliver`.

Edge cases: invalid value in a fix cell (error lists sheet row + column; nothing applied) · deleted row makes chain valid · missing transaction (`insert_after`) · `DATE_ORDER_AMBIGUOUS` resolved by `extract <id> --date-order DMY` rather than per-row fixes.

### A6. Twelve months into one workbook (SPEC 9.4)
1. Order with `merge=true`; 12 files in `input/`.
2. `extract`, review as needed, `export` → merged workbook + per-format files covering all months.
3. Summary shows monthly continuity; gaps flagged.

Edge cases: two accounts in one order (merged per account mask) · missing month (`PERIOD_GAP`) · overlapping statements (`PERIOD_OVERLAP`, duplicates warned).

### A7. Categorized output (SPEC 12.6)
1. Order `categorize=true`; optional client rules file in the order folder.
2. Export adds Category column and "Uncategorized" count in Summary.

Edge cases: conflicting rules (first match wins, documented) · client wants their chart of accounts names (client rules file).

### A8. AI rescue for an unusual layout (SPEC 11)
1. Client agrees in writing; operator sets `ai_consent=granted` + note.
2. `extract <id> --ai` → only failing pages go to AI, masked; rows validated.
3. Delivery note states that AI-assisted extraction was used on N pages.

Edge cases: paid tier not confirmed (gate closed, message explains) · page cap reached · AI returns invalid JSON (retry, then page stays `NEEDS_REVIEW`) · network down (page stays `NEEDS_REVIEW`).

### A9. Close order and certify deletion ⭐ (SPEC 14)
1. After the client accepts, `close <id>` (asks confirmation unless `--yes`).
2. Tool deletes client material, verifies, writes certificate, appends ledger.
3. Operator pastes certificate text to the client if requested.

Edge cases: file locked because it is open in Excel (error names the file; nothing half-deleted is reported as success) · order not yet delivered (refuses unless `--force`).

### A10. New bank layout profile (SPEC 7.4)
1. `profile scaffold <id> <file>` → draft YAML in `work/`.
2. Operator (or Kilo) completes aliases/patterns, copies to `profiles/<bank>.yaml` without client data.
3. `profile test <bank> <pdf>` → rows + verdict.
4. Add a synthetic layout mimicking the structure + golden test (no real data committed).

### A11. Pricing review (SPEC 6.5, 15.3)
1. `stats` → median sec/page by kind/engine, review minutes, verdict mix.
2. Operator updates `config/pricing.yaml` defaults.

---

## B. Client touchpoints (outside the tool)
| Touchpoint | Tool support |
|---|---|
| Asks for price | `intake` + `quote` |
| Sends files | Operator copies into order `input/` |
| Receives delivery | `deliver` zip + note + data-handling statement |
| Asks "is my data deleted?" | `close` certificate text |
| Monthly repeat client | New order per month; `merge` for year-end |

## C. System checks (automatic)
| Check | When | SPEC |
|---|---|---|
| Offline mode for Docling | Every command after config load | 3.1 |
| Log redaction | Always | 15.2 |
| Export blocked on `NEEDS_REVIEW` | `export` | 3.6 |
| Spot-check required | `export` | 10.4 |
| Retention overdue | `order list --overdue` | 14.2 |
