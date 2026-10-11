# SaaS Phase 6: security and operating readiness

Status: engineering implemented; production exit blocked; local and GitHub development checks passed on `saas-phase-6`, following pushed Phase 5. Owner authorized both phases sequentially on 11 October 2026 (Asia/Dhaka).

## Implementation sequence

1. Fix observed dependency advisories with official hash-pinned packaging-tool artifacts; scan installed Python/Node versions, record dependency/model/license inventory and rerun the original conversion gate.
2. Add authenticated aggregate operations/alert status, minimal public liveness/readiness, immutable operator-written backup/restore receipts and bounded intake/security headers. Alerts must contain no document, account, secret, object-key or customer identifier.
3. Add independently encrypted, authenticated local backup archives containing matched PostgreSQL, identity, private objects and vault/config material. Require quiesced local writers. Verify corruption/wrong-key/path limits and perform a real restore into disposable isolated resources, never overwrite active volumes/buckets. Verify restored grants, metadata, artifact hashes and vault decryptability; rehearse forward migration and restore-based rollback. Add explicit backup expiry/purge dry-run.
4. Hide private browser caches immediately after session loss/expiry and test actual cross-tab logout plus keyboard/mobile accessibility. Preserve supported BYOK/Max, source review and exact money.
5. Add incident, support, recovery, migration and staging handoff runbooks, CI checks and reproducible inventories/load evidence. Record what was run and what still depends on the chosen hosting region/provider.
6. Complete appropriate local/CI gates, push the Phase 6 branch and save updated device/cloud startup instructions. Main stays unmerged.

## Release boundaries

This is engineering preparation with fictional data. The implementer cannot certify their own work as an independent external security review. A selected HTTPS production topology, merchant/provider terms, customer-data permissions/region, retention/backup expiry and recovery promises, host-specific sustained load, native image scan coverage and independent review remain explicit launch gates. Production interrupted AI cleanup continues to fail closed until the selected deployment proves old-process/container teardown; neither an SQL lock nor a restored backup proves memory erasure. No public deployment, paid inference, real payment or external email is authorized by these local checks.

## Observed local evidence

- 128 real PostgreSQL/private-storage/API tests pass, including authenticated aggregate reports, denied receipt writes, slow-body admission, encrypted archive abuse and restored authority/tombstone tests. Strict lint/format/type gates pass; OpenAPI 0.6.0 retains all 33 features.
- 42 frontend unit tests and 19 demo journeys pass; API build passes. The full real Keycloak/OTP/isolated-worker/fake-AI browser run passes all six conversion inputs, six exports/ZIP/removal, supported Max and full source review, onboarding/invitations/downloads, manual invoice/refund/support/notices, owner tools and mobile axe/overflow.
- New Phase 6 browser acceptance passes fresh-MFA anonymous operations/readiness and a real logout from the shared browser context followed by a denied private form write. Cached support content/navigation disappear immediately; keyboard/public axe passes.
- Matched isolated restore passes 352 private files, a fictional encrypted vault key, identity/database/grants, revoked sessions, fenced work/AI consent, repeated migrations, prior-schema rollback preserving a fictional exact paid ledger, and cleanup of its own resources. Zero newer tombstones existed in that snapshot; real-storage tests separately prove scoped replay and failed verification without a false certificate.
- Synthetic expiry dry-run/apply removes exactly an expired test archive and preserves an unexpired one; source backups stay untouched. Local liveness baseline: 100/100 at concurrency eight, p50 8.22 ms, p95 14.63 ms; no OCR/host capacity claim.
- Official package tooling updates: OSV 147 Python packages and npm audit report zero known advisories. Native Trivy gate remains **blocked: 59 high / one critical, 60 unfixed**; no suppression. Complete license/model terms, independent review and selected-host capacity/teardown/restore policies remain release prerequisites.

Read `docs/saas/PHASE6-OPERATIONS.md`, `PHASE6-THREAT-REVIEW.md` and `PHASE6-SECURITY-FINDINGS.json`. New-device guidance uses the Phase 6 branch and preserves all credentials/volumes/keys. No production launch, paid provider request, actual payment/email, real statement or main merge occurred. Exact final image/crash-recovery and GitHub CI results follow when observed.


Final-source worker image `a446867e8b75f4fddbef2b8cfa6443ec6fb4e8a907bbe94af261463b0b03be27` passes model/network/SQL/container restrictions. The ordinary-server actual SIGKILL/reclaim/replay test passes after sequential worker replacement; one orchestration run overlapped recreation and failed, so it is recorded as a failed harness attempt, not a product pass. The subsequent check retains all original assertions. Original converter full gate again passes 315 tests; nine targeted operations/recovery cases include the additional expired-backup receipt regression. Source `44b2b6df9e57b2a5938687f000834f97783a6846` is pushed; full GitHub SaaS and frontend workflows are in progress.


Pushed-source [frontend CI](https://github.com/samidoomsday-star/dockling/actions/runs/38123735406) passes. The strict native command on the final rebuilt image exits 1 as required (59 high/one critical); a live API also causes the backup command to refuse creation before any snapshot. These are expected failed safety/release checks, not successful production acceptance.


## Final GitHub acceptance

Both complete workflows pass on source `44b2b6df9e57b2a5938687f000834f97783a6846`: [SaaS pipeline](https://github.com/samidoomsday-star/dockling/actions/runs/38123735381) and [frontend checks](https://github.com/samidoomsday-star/dockling/actions/runs/38123735406). The SaaS job log confirms **129 SaaS tests and 315 original converter tests, no skips**. It also passes installation, contracts/types/lint/format, verified isolated worker build, package audit, actual container/network/SQL/model restrictions, full Keycloak/OTP/fake-AI/owner/accounts/operations browser acceptance and ordinary-server actual SIGKILL/reclaim/replay.

The fresh GitHub stack's encrypted restore verifies **27 objects**, one wholly fictional vault key, identity/database/evidence permissions, fenced sessions/work, repeated forward migration and matched prior-schema ledger rollback, then removes its disposable resources. The observed 14 seconds is not a recovery promise. Its isolated expiry drill removes exactly its expired synthetic archive and preserves the valid one/source backups. These counts differ from the local 352-object drill because CI starts from a fresh fictional stack.

GitHub's development native scan also explicitly records **59 high / one critical / 60 unfixed / release blocked**. A green functional workflow does not override this result. Independent security review, complete transitive/native/model licensing, selected-host capacity and verified teardown/disaster recovery, and launch policy/integration decisions remain gates. **Phase 6 engineering work is complete; the production acceptance gate is not passed.** Main remains unmerged. Final evidence and device-instruction changes after the tested source are documentation only.
