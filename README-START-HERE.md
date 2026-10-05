# Dockling — start here

Dockling now includes the cloud-developed phases 1–10: local order intake, text/OCR extraction, financial checks, Excel review, CSV/Excel/OFX exports, merging/categories, delivery/cleanup, and optional custom OpenAI-compatible BYOK models with supported effort choices up to Max.

The complete development version is on **`development-phases-2-10`**. `main` remains the original starter; no merge has been performed. Think of this branch as your saved IDE project. GitHub carries source and setup instructions, while Python, dependencies, local OCR models, job data and API keys are installed/kept separately on each device.

- [Beginner operator guide and first fake delivery](docs/OPERATOR_GUIDE.md)
- [Clone, installation and update commands](docs/ENVIRONMENT.md)
- [Ask an assistant to set up your cloned device](docs/DEVICE_SETUP.md)
- [Your own provider, model picker and effort](docs/BYOK_GUIDE.md)
- [Phase evidence and remaining device checks](docs/PROGRESS.md)
- [Synthetic cloud acceptance](docs/PHASE10-SYNTHETIC-ACCEPTANCE.json)
- [Original specification](docs/SPEC.md)

For cloud development: `bash scripts/install-linux.sh`, `.venv/bin/python -m stmtconv models download`, `.venv/bin/python -m stmtconv doctor`, `.venv/bin/python scripts/check.py`, then `.venv/bin/python -m stmtconv selftest`.

Windows installation, real camera/field samples, Excel/accounting imports and your actual BYOK service still need device checks. This is a development preview; financial reconciliation does not prove source dates/descriptions, and Docling cannot rescue every borderless layout. Use synthetic documents until you complete those checks. No paid LLM inference call was made here.

The `.kilo/` files remain historical reference; Kilo Code is not required. Active development instructions are in `AGENTS.md`.
