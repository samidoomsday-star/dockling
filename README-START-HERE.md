# Dockling — start here

**Want the web app?** Use **`saas-phase-7`**, including the latest Phase 8 worker security fixes. On Windows, start with [the beginner testing guide](docs/saas/WINDOWS-TESTING.md); on Linux, follow [the full local setup](docs/saas/LOCAL-SETUP.md). The real app includes sign-in/workspaces, private uploads, actual text/OCR conversion, review/corrections, six outputs, delivery/removal, BYOK/model/effort connections, owner/team tools, accounts/usage, manual invoice records and operating/recovery tools. Initial testing needs no hosting account or API key. Online checkout, external email and public hosting remain unconfigured.


Dockling now includes the cloud-developed phases 1–10: local order intake, text/OCR extraction, financial checks, Excel review, CSV/Excel/OFX exports, merging/categories, delivery/cleanup, and optional custom OpenAI-compatible BYOK models with supported effort choices up to Max.

The current app is on **`saas-phase-7`**. The earlier demo milestone is **`web-frontend`** and the Python-only milestone is **`development-phases-2-10`**. `main` remains the original starter; no merge has been performed. Think of this branch as your saved IDE project. GitHub carries source and setup instructions, while dependencies, OCR models, job data and API keys are installed/kept separately on each device.

- [Windows browser testing: installation, first login, samples and restarts](docs/saas/WINDOWS-TESTING.md)
- [Complete real-app setup and assistant checks](docs/saas/LOCAL-SETUP.md)
- [Separate fictional UI demo](frontend/README.md#separate-ui-demo)
- [Frontend feature coverage and pending integrations](docs/FRONTEND-COVERAGE.md)
- [Beginner operator guide and first fake delivery](docs/OPERATOR_GUIDE.md)
- [Clone, installation and update commands](docs/ENVIRONMENT.md)
- [Ask an assistant to set up your cloned device](docs/DEVICE_SETUP.md)
- [Your own provider, model picker and effort](docs/BYOK_GUIDE.md)
- [Phase evidence and remaining device checks](docs/PROGRESS.md)
- [Synthetic cloud acceptance](docs/PHASE10-SYNTHETIC-ACCEPTANCE.json)
- [Original specification](docs/SPEC.md)
- [Approved customer web-app design](docs/WEB-APP-PLAN.md)
- [Current worker security evidence](docs/saas/PHASE8-SECURITY-REMEDIATION.md)
- [Hosted staging requirements](deploy/staging/README.md)
- [Offline visual wireframe — open the HTML file in a browser](docs/WEB-APP-WIREFRAME.html)

For the real web app, follow LOCAL-SETUP.md: run `bash scripts/install-saas-linux.sh`, then `worker-build`, `worker` and `run` using `.venv/bin/python scripts/saas-local.py`. The commands `bash scripts/install-linux.sh`, model download, doctor, `scripts/check.py` and selftest are the separate Python operator workflow.

Latest Linux/GitHub evidence passes 164 SaaS tests, 318 converter tests, real browser/worker/recovery checks and a strict worker scan with zero high/critical findings. Windows/WSL, independent security/licensing review, selected-host capacity/recovery, real camera/field samples, Excel/accounting imports and your actual BYOK service still need checks. Financial reconciliation does not prove source dates/descriptions, and Docling cannot rescue every borderless layout. Use synthetic documents initially. No paid LLM inference call or public deployment was made here.

The `.kilo/` files remain historical reference; Kilo Code is not required. Active development instructions are in `AGENTS.md`.
