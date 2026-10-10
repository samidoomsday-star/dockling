# SaaS Phase 2 — actual upload and conversion workers

**Status:** implemented for synthetic local development on `saas-phase-2`. See [implementation/evidence](../saas/PHASE2-IMPLEMENTATION.md) and [device setup](../saas/LOCAL-SETUP.md). Production and device/field gates remain pending. Read Phase 1 evidence, `docs/saas/DATA-AND-JOBS.md`, security/permissions and the OpenAPI phase-2 routes first. Preserve the CLI and demo baseline.

## Intended outcome

A signed-in customer uploads a synthetic statement, sees its genuine intake/conversion progress, and receives source-linked canonical results. Review and final exports remain Phase 3; AI/BYOK stays off until the hosted consent/key/gateway boundary in Phase 4.

## Implementation order

1. Extend migrations for file inventories, canonical snapshots, operation leases/heartbeat/fencing/retries, revision/digest mapping and deletion/tombstones. Define and use complete typed pipeline command/repository/artifact/unit-of-work ports; preserve the pure financial/parser core and legacy filesystem adapter. PostgreSQL remains the hosted authority.
2. Add bounded authenticated uploads to private storage: real byte/MIME/PDF validation, encrypted-document handling, filename-as-data, page/image safety limits, atomic inventories and safe synthetic-only operating policy. Owner/editor write; viewer read only. No public object ACLs or plaintext document-password logging/storage.
3. Implement durable idempotent intake/conversion commands. Authorize actor/workspace/job and expected revision at enqueue; revalidate lease/revision/removal state before publication. Reserve test quotas before expensive work. Cross-workspace child IDs, stale revisions and duplicates must fail safely.
4. Build a worker with scoped DB/storage credentials and **enforced** network separation from public/model-download routes. Install/hash-verify CPU models at image/setup time. No CLI subprocess or conflicting hosted order.json. Isolated scratch, bounded memory/CPU/time/pages and cleanup. Platform-admin identity is not a worker grant.
5. Integrate actual intake/page routing, text/Docling OCR and provenance; retain original lifecycle and exact Decimal checks. Multi-page description mismatch evidence still requires source review. Worker crash/reclaim and concurrent duplicate attempts must publish at most one current revision.
6. Connect the real-mode UI to upload/progress/job/file/source/canonical result queries using the API contract. Keep metadata team/sign-in functional. Clearly distinguish financial reconciliation from source-review completion; final exports remain unavailable.
7. Test real PG/storage plus network-restricted synthetic worker, PDF/image/encrypted/invalid/oversize cases, tenant/role denial for every route, lease expiry/retry/stale/removal races and storage failures. Run the existing CLI and frontend regression gates. Record timing/resource evidence without calling it hosting capacity.
8. Update API examples, device/container/model/setup instructions and fresh-device verification; push a reviewable milestone without merging or deploying main. Do not process real customer documents or contact a paid LLM.

Production vendor/country/retention/budget decisions remain pending. This local phase must not silently open real customer intake or apply guessed retention/prices. Complete hosted privacy/key/billing/operations/release gates before advertising a paid SaaS.

## Completed milestone

Tasks 1–8 are implemented for the local synthetic workflow. Evidence: 51 PostgreSQL/storage tests, 314 original Python tests, 42 frontend unit tests, 19 demo browser journeys, genuine text/scanned/image/protected/combined-image source-linked results and actual Keycloak/OTP/browser checks. Actual container public TCP/DNS denial and resource/mount/role checks pass. Actual SIGKILL/45-second lease reclaim publishes one revision, confirmed as generation 2/two attempts, with no duplicate replay. See PHASE2-IMPLEMENTATION.md and PROGRESS.md for failures corrected, exact evidence and remaining device/production gates.

Phase 3 is next: corrections/review/source attestations → recheck → current-revision exports. The existing multi-page description mismatch must remain review-gated. Do not enable paid BYOK, real customer intake or deployment as a side effect of finishing this phase.
