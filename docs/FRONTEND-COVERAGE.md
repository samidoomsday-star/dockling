# Frontend feature coverage — Stage B

This ledger maps every existing-feature row in WEB-APP-PLAN section 6. **Interactive preview** means in-memory synthetic UI behavior, not a completed production function. **Backend pending** means the existing CLI remains usable but the web endpoint/worker has not been built. No existing Python function was removed.

| Existing capability | Frontend location and current behavior | Integration required |
|---|---|---|
| Create order, currency/dates/outputs, alias/channel/package | `/app/new` guided form; operator details described in admin | Create/update order; operator-only commercial metadata |
| List/show/history/overdue | `/app/jobs` search/status; job Overview/Activity; retention explanation | Pagination, timestamps, overdue reminders |
| Intake sniff/hash/page kind/limits | New conversion file picker; Files clearly labels fixture metadata | Authenticated uploads, signatures/hashes/quotas |
| PDF password | Intake disabled password field | Transient worker handoff, no logged/stored password |
| Combine/EXIF/image ordering | Intake combine toggle and move-up controls | Rotation, normalized private artifacts |
| Force limits | Admin configuration explains permission boundary | Authorized override/reason/audit; customer cannot bypass |
| Quote/pricing/add-ons | `/pricing` truthful unapproved offers; admin pricing validation | Quote service, validated price writes; no checkout |
| Extraction automatic/text/Docling | Intake engine selector; explicit practice-processing action | Durable worker and actual extraction |
| Engine/profile/page groups/diagnostics | Intake advanced fields; Files/Overview | Profile/page routing, per-page statuses |
| Validation/balance/totals/coverage/dates/duplicates | Checks explains fixed fixture amounts and server checks | Existing Decimal core and readable issue DTOs |
| Review/fix/delete/insert/clear/notes | Review modal, staged atomic batches, exact amounts, discard warning | Shared Python review service, authenticated actor/history |
| Revision-bound spotcheck/fixed rows | Checks compares both sample rows; edits invalidate checks/exports | Deterministic server sample and revision assertions |
| AI source confirmation/provenance | AI fixture; engine/page flags; separate full source acknowledgement | Actual source rendering and trusted server record |
| Six exports/date/QB chunks | Exports: six reference downloads, revision gate, import notes | Current-job writers, chunking and private downloads |
| Identity-aware bank/card OFX | Intake account-group confirmation; Exports gate and format notes | Institution/account/direction DTOs and import validation |
| Merge/monthly workbook/continuity | Intake merge confirmation; Files/Exports account and continuity details | Real merge/12-month writer and gap/overlap checks |
| Categories/direction/regex/overrides | `/app/categories` ordered add/edit/remove/move rules; override control | Scoped matching/regex preview and job override upload |
| Deliver/hash/revision/ZIP/templates | Exports prepares preview package and fixed ZIP; Activity revision | Live artifacts/hashes, templates, safe delivery |
| Run/resume/review pauses | Intake start; recovery fixture retry; review/export gates | Durable stage resumption/idempotency |
| Inbox/run.bat | Help and frontend README preserve local CLI/device workflow | Browser upload counterpart; existing local launcher retained |
| Close/retention/partial retry/certificate | Data tab removal, explicit confirmation, simulated partial failure/retry | Inventory all private storage; verified deletion and reminders |
| Close abandon/anonymous outcome | Unfinished job removal requires abandonment; scrubbed preview | Anonymous server ledger, no content leakage |
| Stats/engine/timing/verdict/fix/pages | Dashboard/admin display actual session counts only | Owner-scoped real worker timings and anonymous aggregates |
| AI setup/list/private selection | Connections add/edit/remove custom HTTPS configurations | Encrypted per-owner BYOK key storage/rotation |
| AI models/test/manual IDs | Sample catalog/manual IDs; provider test clearly disabled | Outbound metadata/discovery/test policies |
| AI pick/capability evidence/Max | Model picker auto-selects highest supported effort; unknown default only | Provider evidence validation; renewed consent bindings |
| AI adapter/chat/responses/JSON/tokens/routes/temperature | Connection advanced settings, supported-effort validation | Existing adapter behind server outbound policy |
| Consent/terms/budget/retries | Job AI note/consent/revoke, provider terms, page counter/cap | Binding/caps/reservations/retry accounting; no inference here |
| Profile scaffold/test/YAML | Admin profile picker and private scaffold/test instructions | Sanitized fixture tests and permission-scoped editing |
| Doctor/model download/hash | Admin unknown health status and local commands/setup guidance | Actual system probes, explicit model maintenance |
| Selftest/demo/synthetic assets | Public guided sample, admin local selftest, generated reference files | Isolated backend sample workspace and diagnostics |
| YAML defaults/prices/exports/categories/profiles/templates | Settings/category editors; admin validated pricing example/config controls | Versioned schema-valid server writes |
| CLI help/version/config/env | Help/admin local CLI instructions; frontend README | Preserve CLI; deployment controls remain owner-side |

## New web requirements still pending

Stage C: authenticated API contract implementation, genuine file upload/source viewer, queue/worker status, shared browser/Excel review, real exports and cleanup. Stage D: account isolation, permissions, CSRF enforcement, encrypted BYOK storage, outbound restrictions, quotas, durable restart recovery and negative security tests. Stage E: tested fresh Windows installation and chosen hosting deployment. Stage F: real bank-layout/import trials and approved commercial offer.

UI filters persist through URL parameters where implemented; demo content/preferences reset on reload by design. Public requests/contact and payment are intentionally not presented as working sales channels before their details are approved.

### SaaS Phase 3 runtime update

F10–F22 now have real local review/output/privacy adapters as described in PHASE3-IMPLEMENTATION.md. Browser/Excel share commands; no fictional download fallback exists in real mode. Financial/source gates and artifact revision/hash membership precede downloads. Owner removal can remain partial and never issues a premature certificate. Customer verification overrides remain unavailable; scoped MFA support/owner operations belong to Phase 4. Payment/email, backup expiry, production-scale recovery and accounting-software field imports remain explicit release gates.
