# Phase 4 first milestone — secure BYOK connections

Phase 3 is complete on `saas-phase-3`. The `saas-phase-4` branch adds the first Phase 4 milestone: real workspace connections and a React **AI connections** screen. Phase 4 remains in progress; consent, AI statement processing and owner operations are still pending. This is a local synthetic development app, not a deployed production service.

## What an owner can use

Sign in, select a workspace and choose **AI connections**. Add your provider name and public HTTPS OpenAI-compatible base URL. Advanced settings cover chat/responses APIs, completion route, effort field, JSON mode, token limit field and optional keys. Save a key through a masked input; the input clears after submission, and saved keys never come back to the browser. Replace it or explicitly revoke the connection to erase its live saved key.

**Discover models** and **Test connection** request only the provider model list. They do not send statements or request generation; provider-specific model-list billing/terms must still be checked before real use. You can add an exact model ID manually. Choose a model and **Highest supported**, **Provider default**, or an advertised effort. Max is offered only when reported by the provider and supported by the adapter. Unknown/manual capabilities allow provider default only. A changed provider catalog preserves an unavailable model/effort choice and shows a warning; it never silently downgrades it. Provider terms can be recorded separately; this does not grant per-job consent or certify legal suitability.

Only owners create/change/revoke connections, save keys, discover/test models or change terms/selection. Editors/viewers can read sanitized metadata in their workspace. A platform admin without membership cannot read customer connections.

## Security and setup

The dedicated `STMTCONV_WEB_AI_ENCRYPTION_KEY` is a generated 256-bit hex server secret. Local `scripts/saas-local.py setup`/`migrate` creates `.local-saas/ai-key.env` once with private permissions, independently of cookie signing/DB credentials. AES-GCM uses a fresh nonce and binds ciphertext to the workspace and connection identities. Never commit, print or share that key. Back up it and the matching database privately together. If the file is lost while encrypted connections exist, setup stops and asks for the original backup; it does not generate an unusable replacement. Forward migration `0008_connections` gives no connection-table grant to the conversion worker. Hosted production secret injection/rotation and backup-expiry policy require later deployment design.

The server-only metadata transport accepts public HTTPS on port 443. It rejects credentials/query data in URLs, private/metadata/loopback/mixed DNS answers, redirects and compressed responses. It connects to the checked numeric address while validating TLS against the original hostname, without honoring uncontrolled proxy settings or doing a second hostname lookup. DNS, socket, response-time/body and model-list limits bound calls. Metadata GET may retry once for a transient status; POST is never automatically resent. No hosted AI generation route is enabled by this milestone.

Revoke erases the current live credential, not historical backups. Provider-supplied capability claims are evidence for the picker, not proof of a successful inference. Raw documents remain in the existing private/offline workflow.

## Verified evidence and remaining work

The local baseline passed 315 original Python tests, 84 database/storage/API tests, 42 frontend unit tests and 19 demo browser journeys. The suite includes 25 connection tests, including wrong-vault-key failure, workspace-bound encryption, role/CSRF/revision/replay checks, failed discovery preserving the catalog, supported Max/unknown default and DNS/redirect/response limits. Fake transports block live provider connections; no paid inference was used.

The genuine Keycloak/browser journey covers fictional key save, manual picker, revoke/key erasure, mobile accessibility/layout, then Phase 3 corrections, six output formats, delivery/live removal and six actual synthetic conversion inputs. See `docs/tasks/saas-phase-4.md` for the final execution record. CI independently runs `scripts/saas-browser.mjs --phase3 --phase4`; report its actual result separately.

Next: per-job consent tied to content/revision/provider/model/effort/terms; minimized masked cells and durable page/request reservations; uncertainty-safe gateway dispatch with fake providers; owner profiles/config/health/selftest and expiring audited MFA support grants. These must pass their own gates before Phase 4 can be marked complete. Windows/WSL, actual provider terms/capability/inference, accounting imports, public hosting, load/security review and production backup/restore remain separate release checks.
