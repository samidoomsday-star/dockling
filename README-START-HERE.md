# Dockling — start here

**Want the web app?** The `saas-phase-1` branch includes real sign-in, customer workspaces and saved job records. Start with [the beginner web setup guide](docs/saas/LOCAL-SETUP.md). Upload/conversion, web review/exports, hosted BYOK and billing will be connected in the next phases. This foundation is for local synthetic testing.


Dockling now includes the cloud-developed phases 1–10: local order intake, text/OCR extraction, financial checks, Excel review, CSV/Excel/OFX exports, merging/categories, delivery/cleanup, and optional custom OpenAI-compatible BYOK models with supported effort choices up to Max.

The frontend plus completed Python version is on **`web-frontend`**. The Python-only milestone remains on **`development-phases-2-10`**. `main` remains the original starter; no merge has been performed. Think of this branch as your saved IDE project. GitHub carries source and setup instructions, while Python, dependencies, local OCR models, job data and API keys are installed/kept separately on each device.

- [New interactive frontend: setup and guided testing](frontend/README.md)
- [Frontend feature coverage and pending integrations](docs/FRONTEND-COVERAGE.md)
- [Beginner operator guide and first fake delivery](docs/OPERATOR_GUIDE.md)
- [Clone, installation and update commands](docs/ENVIRONMENT.md)
- [Ask an assistant to set up your cloned device](docs/DEVICE_SETUP.md)
- [Your own provider, model picker and effort](docs/BYOK_GUIDE.md)
- [Phase evidence and remaining device checks](docs/PROGRESS.md)
- [Synthetic cloud acceptance](docs/PHASE10-SYNTHETIC-ACCEPTANCE.json)
- [Original specification](docs/SPEC.md)
- [Approved customer web-app direction and remaining backend stages](docs/WEB-APP-PLAN.md)
- [Offline visual wireframe — open the HTML file in a browser](docs/WEB-APP-WIREFRAME.html)

For cloud development: `bash scripts/install-linux.sh`, `.venv/bin/python -m stmtconv models download`, `.venv/bin/python -m stmtconv doctor`, `.venv/bin/python scripts/check.py`, then `.venv/bin/python -m stmtconv selftest`.

Windows installation, real camera/field samples, Excel/accounting imports and your actual BYOK service still need device checks. This is a development preview; financial reconciliation does not prove source dates/descriptions, and Docling cannot rescue every borderless layout. Use synthetic documents until you complete those checks. No paid LLM inference call was made here.

The `.kilo/` files remain historical reference; Kilo Code is not required. Active development instructions are in `AGENTS.md`.
