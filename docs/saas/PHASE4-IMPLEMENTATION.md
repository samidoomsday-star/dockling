# SaaS Phase 4 — AI controls and owner operations

Implemented on `saas-phase-4`, following the encrypted-connection milestone in [PHASE4-CONNECTIONS.md](PHASE4-CONNECTIONS.md). This is the real local synthetic SaaS app. It is not yet a public paid service; billing, deployment, operational security and launch remain Phases 5–8.

## What the owner can use

- **AI connections:** save a private BYOK key, custom public HTTPS OpenAI-compatible endpoint, chat/responses adapter settings, manual/discovered models, terms reference and supported effort. Highest means the highest advertised supported effort; Max requires evidence. Unknown models use provider default. Keys are encrypted with the dedicated vault key, never returned to the browser and never available to the offline parser.
- **Job → Optional AI assistance:** an owner records permission, names to mask, connection and page/request caps. Editors may request assistance within that consent; viewers read status. Consent binds the exact source/revision/options, captured processing settings, provider/connection version, selected model/effort and terms. Changing them requires new consent. Removing the consenting owner fences queued work.
- **Preferences:** owners save currency, date order, output date format and output defaults. New browser-created jobs use them; current jobs keep their choices. The API still requires explicit valid job choices.
- **Job → Layout tools & support:** generate/download a private page-one scaffold through the isolated worker. The scaffold contains source words and summary candidates; never paste it into shared configuration without a separate permitted synthetic/redaction review. Create named support grants for results, source files/pages and/or private scaffolds, lasting 1–60 minutes. Revoke immediately. New job revisions invalidate access.
- **Service health:** a platform administrator with a fresh second factor sees database/storage availability, the worker heartbeat, startup model-hash evidence and anonymous outcomes. Run the nine-case synthetic selftest or an exact candidate profile test in a private diagnostic workspace. Download reports and use passing test evidence for profile activation.
- **Configuration versions:** advanced, bounded schema-validated processing/pricing/exports/template/profile editing; save a draft, inspect version history, or activate for future jobs. Copy an older version into a new version to revert. Current job runtime snapshots remain fixed. Financial tolerances cannot be loosened beyond the established limit; export columns/date choices must remain supported. Delivery text adds a plain note without removing verification/privacy notices. Pricing remains internal, without changing a public offer or taking payment.

## AI behavior and limits

The trusted API-side gateway sends only normalized transaction cells for selected pages. It excludes original PDFs, page images, raw extraction text, headers, summary/account metadata, filenames and internal job/file identifiers. Known names plus supported email/phone/account-like patterns are masked. This is minimization, not a guarantee of complete anonymization: owners must have appropriate client permission and provider terms.

Hosted AI currently **corrects existing cells only**. It cannot add/remove/reorder rows, recover missing OCR rows or send raw PDFs. It validates exact decimal/date shapes and the complete selected response before applying any page. A bad page leaves the entire request unapplied. AI rows retain source provenance and require the full AI-source review gate before export; financial reconciliation alone never proves descriptions/dates.

Reserve one page and one request for every selected page before send. Up to five pages per run; platform defaults cap a job at 40 pages/requests, and owner consent can set lower caps. Reservations persist through cancellation, failure, model changes and consent renewal. They are conservative application limits, not a dollar-spend guarantee or a provider invoice. An interrupted/failed send may have been charged; no POST is resent automatically. An explicitly acknowledged new attempt uses another reservation and can incur another charge. Up to 30 requests per workspace/hour plus the configured active-work limit.

Revocation/cancellation/close fences publication immediately. Removing data waits for active gateway private references and parser scratch receipts; the live-removal certificate does not cover third-party provider retention, backups, browser copies or downloaded files. No raw provider responses are saved in the request ledger.

## Operating boundaries

The supported initial development topology is **one Linux API/gateway process and one isolated worker**. The local gateway holds both an OS lock and a PostgreSQL lock. Local crash recovery preserves uncertain sends and reservations, and acknowledges cleanup only after obtaining those locks. Production-mode interrupted runs deliberately retain the cleanup fence: deployment must implement verified process/container teardown recovery before customer use. A SQL lock alone cannot prove an old process has released memory. Do not add API replicas or Uvicorn workers until Phase 6 addresses this boundary.

The parser retains no public egress or vault key. Its only new authority is bounded utility publication and a narrow worker-report SQL function. Model downloads remain explicit setup maintenance, hash-checked against the pinned manifest; the app does not offer arbitrary model URLs. A heartbeat updates availability every ten seconds; it does not rehash models on every tick.

Platform administrators gain no implicit customer memberships. Synthetic diagnostics get a separate private workspace. Every support read checks the assigned administrator, fresh MFA, active consenting owner, exact job revision, expiry, revocation and selected data class, and records an audit event. File inventories include only authorized current artifacts. Anonymous outcome buckets need at least five workspaces and contain no client/job IDs, filenames or statement text; this threshold is not a formal differential-privacy guarantee.

## Reproduce on another device

Follow [LOCAL-SETUP.md](LOCAL-SETUP.md) and [DEVICE_SETUP.md](../DEVICE_SETUP.md). Use Linux x86_64 / WSL 2, Python 3.12, pinned Node 24 and Docker Compose. Preserve private `.local-saas` files and volumes, especially `ai-key.env` and its matching database backup. Upgrade through forward migrations `0009_ai_ledger` and `0010_owner_tools`, rebuild/restart the worker, rebuild the API frontend and restart the API. Never run demo and API builds simultaneously.

Ordinary verification uses the real server and fictional key save/revoke only:

```bash
node scripts/saas-browser.mjs --phase3 --phase4 --phase4-owner
```

To verify the AI interface **without an external model**, stop the ordinary API, then run the explicitly local test server in one terminal:

```bash
.venv/bin/python scripts/saas-fake-ai-server.py
```

In another terminal:

```bash
node scripts/saas-browser.mjs --phase3 --phase4 --phase4-ai --phase4-owner
```

The test server accepts only the named fictional no-key provider/model and has no live-provider fallback. It uses real identity, PostgreSQL, storage and the restricted worker. Stop it afterward and restart the ordinary server with `scripts/saas-local.py run`. Set `PLAYWRIGHT_BROWSERS_PATH` if Chromium was installed into a custom location. These commands are internal verification, not public preview links. Real BYOK inference requires separately authorized terms/capability/payment checks; it was not executed in development.

## Acceptance evidence

Evidence is recorded in `docs/tasks/saas-phase-4.md`. Gates include the original 315-test converter suite; real PostgreSQL/private-storage/API tests; frontend lint/format/types, 42 unit tests and 19 demo journeys; the genuine OIDC/OTP, isolated-worker, owner/AI/review/export/removal browser journey; and worker network/SQL/model restrictions. The contract is version 0.4.1; planned future aliases remain distinguishable from implemented hosted routes.

Windows/WSL acceptance on a receiving device, real-provider capability/terms/inference/charges, accounting imports, production gateway recovery, storage backups/restore/expiry, security review, capacity/region and public hosting remain release gates. No customer invitation/email, payment, main merge or public deployment is included.
