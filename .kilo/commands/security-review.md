---
description: Review changed code for security and permission problems
---

# Security review

Review all files changed in the current phase (`git diff main...HEAD`). Check against `.kilo/rules/03-security.md`, `.kilo/rules/07-ai-cloud.md` and `.kilo/rules/02-architecture.md`:

1. No network access outside `extract/ai_engine.py`; Docling runs with offline flags set before import.
2. AI gate checks all four conditions before any request; masking applied to every AI payload; no images or file names sent.
3. No descriptions, names, full account numbers or amounts-with-descriptions in logs, ledger, errors or manifests after close.
4. PDF passwords never persisted (manifest, logs, temp files).
5. `close` deletes input/work/review/output/delivery and verifies nothing remains before writing the certificate.
6. Account numbers masked to last 4 in all outputs unless `show_full_account`.
7. All YAML/JSON/Excel inputs validated by pydantic with row/field errors; no eval/exec of document content.
8. No real statements or client-derived text committed (fixtures are synthetic).
9. New dependencies are permissively licensed and approved (no AGPL/GPL, no PyMuPDF).

Output a table: issue, file:line, severity (high/medium/low), fix suggestion. Don't change code until the user approves.
