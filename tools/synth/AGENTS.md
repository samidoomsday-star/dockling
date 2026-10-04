# tools/synth — synthetic statement generator

- Follow ADR-011 and SPEC 17 Phase 2.
- reportlab PDFs + ground-truth JSON; layouts cover separate debit/credit, signed single amount, credit card (liability, no running balance), wrapped descriptions, page breaks, bracket negatives, reverse order, borderless wrapped layout.
- "Scanned" variants: rasterize with pypdfium2 at 200 dpi, small rotation + noise with Pillow, re-wrap as image PDF.
- Fake names/merchants only (seeded random); output into a caller-given temp folder; nothing written to the repo.
