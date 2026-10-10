# Dockling hosted API contract

`openapi.yaml` is the versioned API design; it does not start a server. Version **0.2.0** implements Phase 2 bounded raw-byte uploads (revision/name/synthetic headers), published intake limits/profiles, recent operation lists, statement summaries and read-only source-linked rows. Legacy multipart Upload design is superseded; later enum/action values remain planned and rejected until implemented. Version 0.1.1 adds the owner-only `InvitationDelivery.accept_url` response for the implemented Phase 1 manual invitation flow. Version 0.1.0 fixed the initial Phase 1 foundation and describes the planned later-phase boundaries. Phase 1–2 routes are implemented and checked against this contract for synthetic local use; later-phase routes remain planned. Domain/compatibility review may refine later schemas before their implementation; document versioned changes rather than silently changing clients. Root URL is same-origin `/api/v1`.

Run from the repository root, using the configured Python 3.12 environment:

```powershell
python scripts/check-saas-contract.py
```

The validator uses the official OpenAPI 3.1 schema, JSON Schema 2020-12 validation, local reference resolution, synthetic response/command examples, inventory comparison and essential money/key/revision boundary probes. It is fully offline. It verifies structure and design coverage, not working HTTP routes or security controls. Dependencies are in `research/saas/requirements-tools.txt`; the existing cloud environment already supplies them. A fresh device can install that file into its project virtual environment if they are missing.

The vendored official schema is from `https://spec.openapis.org/oas/3.1/schema/2022-10-07`, SHA-256 `da01ba28852cac0de53893797cb8d1942bc3b05084f526dcc216717dec314ed0`. Its OpenAPI Specification Apache 2.0 license is included in `vendor/LICENSE-OpenAPI.txt`. Keep provenance/hash intact when updating the validation baseline.

## Conventions and enforcement

- Cookie session authenticates members; every write also requires CSRF. Admin endpoints require MFA and server-controlled platform permissions. `x-access-roles`/`x-workspace-scoped` describe required checks; OpenAPI annotations do not implement them. See [permissions](../../docs/saas/FEATURE-MATRIX.md).
- Durable mutations use `Idempotency-Key`; relevant job commands use `expected_revision`; configuration/membership changes use an expected version. HTTP 409 returns a safe revision/state/idempotency conflict. Private 404 must not expose someone else's IDs. Errors contain safe field codes and a request ID, never raw statement/key/password text.
- Money is exact two-decimal text in the current engine scope; nullable evidence is distinct from zero. Numeric timings/counts are not money. Unsupported currency precision needs a separate domain upgrade before advertising support.
- List pages use bounded opaque cursors; rows and original/page/output streams are separate endpoints. Private binary reads have current permission/revision/deletion checks and `private, no-store` caching.
- Uploads/workbook applies carry bytes, not only filenames. Enforce byte/page/time/row/decompression bounds in the server/parser as well as contract field bounds.
- Connection read objects never contain credentials. Write-only credential endpoints, capability evidence, consent/reservation and controlled egress are server requirements. Model effort is never trusted from client metadata alone.
- Partial command semantics are validated beyond structural JSON Schema: edits require changes for fix/insert, valid targets/ordering, no ambiguous clears, and whole-batch validation; consent grants need complete binding/cap/terms; membership changes protect the final owner; overrides require explicit authorized action grants and hard resource bounds. These rules must be tested in application services.
- Global profile/config YAML is data validated against existing section-specific schemas, not arbitrary code or filesystem controls. Later commercial webhook/checkout shapes remain placeholders until a merchant-eligible provider is selected; provider raw bytes/signatures must replace the placeholder webhook encoding before enablement.
- OIDC login start/callback are maintained-framework routes outside this resource API. Verify callback state/nonce/PKCE/token security in Phase 1. Public sample/help remains the separate synthetic frontend, never a private tenant snapshot.

## Migration from the provisional frontend

Replace `HttpApi.snapshot()` with session/workspace context, paginated job summaries and on-demand row/file/check/operation reads. Replace filename-only `NewJob.files` with authenticated streaming uploads. Derive role from server session; retain role picker only in explicit demo mode. Pass expected revision/version and idempotency keys; handle structured errors and queued operations. Obtain CSRF via `/session` (do not discard it whenever an unrelated GET lacks a token header). Preserve the current no-demo-fallback behavior.

The old `/process` action becomes a durable `/operations` request; the adapter translates atomic review commands and source attestations; output/close commands return tracked operations. Connection credentials use a separate write-only action. Expected Decimal strings, null values, server provenance, row statement identity and content version mappings need contract fixtures before real-mode UI integration.

Phase 3 extends the contract with accurate `Hosted*` input schemas and explicit implemented route annotations. Planned earlier spellings remain design references; use PHASE3-IMPLEMENTATION.md and FoundationApi for current URLs. The full inventory still includes later-phase capabilities; schema validation is separate from runtime tests.


Version **0.4.0** implements hosted `/connections` list/create/read, `PUT /connections/{connection}/key`, and POST `revoke`, `models`, `test`, `models/manual`, `selection`, `terms`. `HostedConnectionRead` rejects credential fields; owner mutations use CSRF/idempotency and expected revision. Earlier edit/delete/discovery spellings remain planned annotations. Consent/AI dispatch and owner operation routes remain planned; recording provider terms alone does not enable processing. See PHASE4-CONNECTIONS.md.

Version **0.4.1** adds implemented consent/request/cancel/status routes, workspace preference writes, versioned admin configuration, isolated utility/selftest/profile diagnostics, scoped expiring support access and aggregate metrics. Hosted routes carry implementation/role annotations; legacy future aliases and production integrations remain planned. Read docs/saas/PHASE4-IMPLEMENTATION.md for the single-process development boundary and remaining deployment gates. Health now includes nullable worker/model evidence timestamps and the pinned manifest digest. Money remains exact text; API read projections never return raw credentials or private consent notes.
