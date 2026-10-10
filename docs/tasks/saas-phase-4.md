# SaaS Phase 4 — optional BYOK and owner operations

**Status:** in progress on `saas-phase-4`, starting from Phase 3 `3ba921afcd3167e671d259ff24377a9865e353ab`. The owner requested continuing Phase 3 and then starting Phase 4. No real customer data or paid model calls are authorized for development tests.

## Sequence and acceptance

1. Encrypted workspace-scoped connection vault with a dedicated key, owner-only write/replace/revoke, safe public HTTPS OpenAI-compatible endpoints, discovery/manual models and capability-based highest effort. Unknown capabilities allow provider default only; no silent downgrade/provider switch. Connect the real friendly model/key UI and test tenant/role/CSRF/stale/credential disclosure/SSRF boundaries.
2. Consent bound to source/revision/connection/model/effort/terms/config, masked transaction cells only, page/request reservations and uncertainty-safe bounded provider dispatch. Keep public networking outside the parser. Test using fake providers; actual provider terms and paid inference are later explicit owner checks.
3. Owner profile scaffolding/testing, validated versioned price/config controls, verified model/worker/health/selftest reports, expiring named-job support grants with MFA/audit, and anonymous operating metrics. Never turn a platform admin into an implicit customer-data reader or publish unapproved prices.
4. Complete real database/storage, fake-provider, offline CLI, browser/mobile/axe and operating boundary gates. Update contracts/device/cloud instructions and push reviewable milestones. Retain evidence and precise remaining launch/device/provider gates; do not claim Phase 4 complete before the full checklist passes.

Phase 3 remains independently available on `saas-phase-3`; `main` remains unchanged.


## First milestone acceptance

Sequence item 1 is implemented. Items 2–3 remain pending; Phase 4 is not complete. See `../saas/PHASE4-CONNECTIONS.md` for behavior, security policy and vault backup instructions.

- Original Python gate: 315 passed, 13 upstream warnings; lint/format and strict mypy over 99 source files passed.
- PostgreSQL/private-storage/API suite: **84 passed**, three dependency/image warnings; 25 connection cases use fictional keys/fake providers, including all owner-only mutations, validation redaction, supported Max, preserved failed discovery, wrong-vault-key, private/mixed DNS, redirect and response bounds. No paid model call.
- Frontend lint/format/types/demo build, 42 unit tests and 19 demo browser journeys passed; final API build passed.
- Genuine browser `--phase3 --phase4`: fictional key save/manual picker/revoke, six formats and actual ZIP, all six conversion inputs, live removal/certificate, viewer/A–B/OTP restrictions and mobile axe/layout passed. Connection/review screenshots inspected.
- Forward migrations repeated without changing the private vault key; key file permission 600 checked. Worker restrictions and pinned models/SQL/public TCP/DNS denial passed.
- OpenAPI 0.4.0: 115 operations, 120 schemas, seven examples and all 33 mappings validate offline. Implemented connection routes have explicit annotations; planned consent/dispatch/admin routes remain planned.
- Phase 3 GitHub checks passed at the pushed commits. Phase 4 GitHub result must be read after pushing, separately from local evidence. No main merge/public deployment, Windows/device acceptance or real provider billing/terms/inference is claimed.
