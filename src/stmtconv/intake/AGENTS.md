# src/stmtconv/intake — files in, facts and quote out

- Follow SPEC 6.4–6.5.
- Sniff type by content; SHA-256 every file; per-page text/scanned/blank detection with pypdfium2/pdfplumber.
- Passwords stay in memory only; decrypted copies go to `work/` only.
- Quote logic reads `config/pricing.yaml` and ledger medians; no prices in code.
