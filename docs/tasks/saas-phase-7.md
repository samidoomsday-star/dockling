# SaaS Phase 7: staging and field validation

Status: engineering and complete local/fresh GitHub synthetic HTTPS acceptance verified on `saas-phase-7` at `212cde6`. Public hosted acceptance and permitted field acceptance are pending. This is the SaaS plan's Phase 7, separate from the completed original CLI Phase 7.

## Implementation sequence

1. Add verified TLS for API/worker database, identity and private storage without weakening local compatibility or worker egress restrictions.
2. Add bounded, read-only staging preflight and a private field-observation format. Keep permission, source accuracy, financial reconciliation, actual imports and complete allocated costs separate.
3. Build a separate loopback HTTPS rehearsal with real Keycloak authorization-code/PKCE/OTP, PostgreSQL, private storage, the restricted worker and the API React build. Preserve the original stack, all matched secrets and every existing volume.
4. Exercise six actual synthetic document inputs, source pages, review, six outputs, hashed delivery ZIP, tenant/viewer denial and verified live removal. Record raw extraction differences before applying known fictional source corrections. Test the real browser with trusted certificates and rejected wrong hostnames, rather than disabling TLS checks.
5. Fix the observed combined-image coverage bug using `(source_file, physical_page)` coordinates. Preserve ordinary single-file behavior, strict financial gates and legacy serialization. Test missing/wrong source coverage before rebuilding the worker.
6. Finish regressions, native release scan, CI and receiving-device/host handoff. Push the review branch; keep `main` unmerged.

## Acceptance boundaries

The rehearsal is synthetic and loopback only. It exercises production-mode TLS/authentication and a separate service topology; it does not establish selected-host capacity, durability, backup recovery, legal approval or real accounting imports. The native critical/high findings remain a production blocker. Public deployment, actual customer statements, paid model requests, payments, email and a paying pilot have not happened here.

Read `docs/saas/PHASE7-STAGING.md` and `deploy/staging/README.md`. [Phase 8 preparation](saas-phase-8.md) and [its pilot runbook](../saas/PHASE8-PILOT.md) are implemented. The controlled external pilot waits for the release gates and explicit publication approval; it has not launched.

## Local milestone

All 13 read-only preflight checks and actual production-mode worker TLS/SQL/model/network/resource restrictions pass. The six-input HTTPS sweep produces all six outputs for each input, verified hashed ZIP delivery and verified live removal, with real Keycloak/OTP and tenant/viewer denial. Raw rows match 15/16; one scan description is corrected from known fictional ground truth. The positive combined images are 216 DPI. A 144 DPI combined case misses its ending date and correctly fails OFX; the new early gate explains this and permits other formats without inventing dates. Worker peak since start is 1592.0 MiB, not a host load promise.

The actual HTTPS browser passes real login/cookies, paused inference, source checks, six exports/ZIP/removal, tenant privacy, mobile axe/overflow, and untrusted-CA/wrong-hostname rejection. Frontend complete checks pass 42 unit tests and 19 browser journeys; serial browser workers retain all assertions/timeouts. Original converter checks pass 318 tests and nine selftest cases. Final complete SaaS checks pass 156 tests, including 24 staging/field cases. [Fresh GitHub CI](https://github.com/samidoomsday-star/dockling/actions/runs/38159876737) passes on `212cde6`: the full suites, genuine HTTPS browser/six-case sweep, ordinary OIDC/fake-AI/account/billing/crash-recovery journey and quiesced encrypted backup/isolated restore/expiry drill. Frontend source remains unchanged since its verified `8d80030` workflow.

Strict native scan on the local acceptance image `a4676cd9f89382b1696c12c3c6935fd8eda50de8d16e339a045072adb6ebde5c` remains **59 high / one critical / 60 unfixed**, exit 1, release blocked. No suppression, public deployment, payment, email, real statement, paid model call or main merge occurred. Private configuration/volumes/models/backups remain preserved. Exact sanitized evidence is in `docs/saas/PHASE7-EVIDENCE.json`.
