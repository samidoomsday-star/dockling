# Architecture rules (mirror of SPEC Section 3, enforced)

- `src/stmtconv/core` is pure: no file/network I/O, no imports from `extract`, `export`, `cli`, `orders`. Business rules live here.
- CLI (`src/stmtconv/cli`) only parses args, calls one service function, renders the report. No business logic.
- Extraction engines implement the `Extractor` protocol in `extract/base.py`; only `extract/router.py` chooses and calls engines.
- Every `Transaction` keeps provenance: `source_file`, `page`, `engine`, `raw_text`, `fixed_by`. Never drop it.
- Order state changes only via `orders.transition()`; manifests and outputs are written atomically (`*.tmp` → `os.replace`).
- Bank layouts, category rules, prices, thresholds, export columns and client-facing texts come from `profiles/`, `config/`, `templates/` (pydantic-validated). No bank names, keywords, prices or client sentences in Python.
- Only `stmtconv/config.py` reads environment variables. Everything else receives a `Settings` object.
- Use `pathlib.Path` for all paths; support spaces and non-ASCII names (Windows).
- Outputs must be deterministic: stable sort (date, page, y, index), deterministic FITIDs, seeded sampling.
- Keep all documented commands single `python …` invocations (PowerShell 5.1 has no `&&`).
- Dependencies: permissive licenses only (MIT/BSD/Apache). Never add PyMuPDF or other AGPL/GPL libraries. New dependency → stop and ask, then ADR.
- Follow module boundaries and dependency direction in `docs/TECH_ARCHITECTURE.md` Section 3.
