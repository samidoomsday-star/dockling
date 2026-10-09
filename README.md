# Dockling

A statement conversion project with a Python operator application and a new customer-facing web frontend preview.

- **Browser preview:** [frontend setup and guided testing](frontend/README.md). On Windows, install Node 24 LTS and open `run-web.bat`. The preview uses fictional data; real web processing/login/hosting are pending.
- **Existing Python converter:** [device setup](docs/DEVICE_SETUP.md), [operator guide](docs/OPERATOR_GUIDE.md) and [optional BYOK setup](docs/BYOK_GUIDE.md).
- **Frontend plan and progress:** [implementation checklist](docs/FRONTEND-IMPLEMENTATION.md), [feature coverage](docs/FRONTEND-COVERAGE.md) and [full web-app plan](docs/WEB-APP-PLAN.md).
- **Production SaaS roadmap:** [architecture and release gates](docs/PRODUCTION-SAAS-PLAN.md), [completed Phase 0 design/capacity findings](docs/tasks/saas-phase-0.md) and [Phase 1 backend checklist](docs/tasks/saas-phase-1.md). The owner authorized proceeding one phase at a time; the live backend, billing and hosting have not been built.

Use branch `saas-phase-0` for the latest frontend, Python work and SaaS contracts/capacity findings. The roadmap milestone is `saas-production-plan`; the frontend milestone is `web-frontend`; the Python-only milestone is `development-phases-2-10`; `main` remains unmerged. Follow the setup guide before processing real client information. No production deployment or commercial pricing is implied by this development preview.
