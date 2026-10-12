# Dockling

A statement-conversion web app with customer workspaces, owner/admin tools and a separate Python operator application. The current branch is **`saas-phase-7`**, including Phases 1–7 and the Phase 8 worker security fixes. `main` remains unmerged.

- **Real web app on Windows:** start with [the beginner testing guide](docs/saas/WINDOWS-TESTING.md), including a prompt for a local coding assistant. Uses WSL 2 Ubuntu and Docker Desktop.
- **Real web app on Linux:** follow [the full local setup](docs/saas/LOCAL-SETUP.md) and [device setup protocol](docs/DEVICE_SETUP.md).
- **Screens only:** [the separate frontend demo](frontend/README.md#separate-ui-demo) uses fictional data and does not process uploads. Node only; `run-web.bat` launches this demo on Windows.
- **Existing Python converter:** [device setup](docs/DEVICE_SETUP.md), [operator guide](docs/OPERATOR_GUIDE.md) and [optional BYOK setup](docs/BYOK_GUIDE.md).
- **Frontend plan and progress:** [implementation checklist](docs/FRONTEND-IMPLEMENTATION.md), [feature coverage](docs/FRONTEND-COVERAGE.md) and [full web-app plan](docs/WEB-APP-PLAN.md).
- **Production SaaS roadmap:** [architecture and release gates](docs/PRODUCTION-SAAS-PLAN.md), [progress](docs/PROGRESS.md), [actual staging handoff](deploy/staging/README.md) and [pilot requirements](docs/saas/PHASE8-PILOT.md).

The real local app provides sign-in, private uploads, queued text/OCR/image/protected-PDF conversion, source review/corrections, six export formats, delivery/removal, optional encrypted BYOK/model/effort connections, team/owner tools, accounts/usage limits, manual invoice records and operating/recovery tools. Initial testing needs no hosting account or LLM key. Online checkout, external email and public hosting are not configured.

Use fictional documents for development. Linux/cloud checks pass; Windows/WSL still needs verification on the receiving device. The latest verified worker has zero high/critical advisory findings; rebuild and scan each new image. Independent security/licensing review, actual hosting/field/import/cost checks and a paying pilot remain pending. See [the security evidence](docs/saas/PHASE8-SECURITY-REMEDIATION.md).

GitHub stores code and setup instructions. Installed dependencies, models, passwords, private keys and local jobs stay on each device and must not be committed. Historical milestones are `web-frontend` for the original demo and `development-phases-2-10` for the Python-only workflow; use `saas-phase-7` for current development.
