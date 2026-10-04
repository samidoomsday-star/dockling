# Extraction rules (SPEC 7)

- Router order per statement: `text` for text pages, `docling` for scanned pages; fallback `text → docling → ai` when 0 rows, > `fallback_mismatch_ratio` MISMATCH rows, or a structural `NEEDS_REVIEW`. Keep the best result per page by validation score; record engine + reason in `order.json`.
- Text engine: pdfplumber word coordinates; header detection via profile `header_aliases`; column bounds from header positions unless the profile fixes them; amounts assigned by right edge (x1).
- Docling: build one `DocumentConverter` per command run; OCR only for scanned pages; table structure ACCURATE; CPU threads from settings; store confidence grades per page. Check option names in the installed Docling version before coding (APIs change between releases).
- Row assembly (SPEC 7.5): date starts a row; dateless text-only lines append to the previous description; dateless lines with amounts inherit the date and set `date_inherited`; drop `noise_patterns` and repeated headers; opening/brought-forward lines feed the summary, not transactions.
- Summary values (opening, closing, totals, period, account) come only from profile `summary_patterns`; missing → `None`, never guessed.
- New layout support = new `profiles/<id>.yaml` + a synthetic layout in `tools/synth` + golden test. Never add bank-specific branches in Python.
- Engines return strings in `RawRow`; all parsing to Decimal/date happens in `core`.
- Performance: record seconds per page per engine in order timings; don't re-run Docling on pages that already validated.
