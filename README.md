# Dockling

A statement conversion project with a Python operator application and a new customer-facing web frontend preview.

- **Browser preview:** [frontend setup and guided testing](frontend/README.md). On Windows, install Node 24 LTS and open `run-web.bat`. The preview uses fictional data; real web processing/login/hosting are pending.
- **Existing Python converter:** [device setup](docs/DEVICE_SETUP.md), [operator guide](docs/OPERATOR_GUIDE.md) and [optional BYOK setup](docs/BYOK_GUIDE.md).
- **Frontend plan and progress:** [implementation checklist](docs/FRONTEND-IMPLEMENTATION.md), [feature coverage](docs/FRONTEND-COVERAGE.md) and [full web-app plan](docs/WEB-APP-PLAN.md).
- **Production SaaS roadmap:** [architecture, implementation phases and release gates](docs/PRODUCTION-SAAS-PLAN.md), starting with the [Phase 0 task checklist](docs/tasks/saas-phase-0.md). The owner authorized proceeding one phase at a time; the live backend, billing and hosting have not been built.

Use branch `saas-production-plan` for the latest frontend, Python work and SaaS proposal. The frontend milestone is `web-frontend`; the Python-only milestone is `development-phases-2-10`; `main` remains unmerged. Follow the setup guide before processing real client information. No production deployment or commercial pricing is implied by this development preview.
