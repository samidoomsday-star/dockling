# SaaS product and development decision register

**Status:** Phase 0 task 0.1 implemented. This register makes development decisions explicit; pending business/vendor choices remain pending. It is not a price list, customer agreement or claim of a working hosted backend.

Authority: the owner's instructions to build a customer/admin web app, retain all existing capabilities, use optional custom OpenAI-compatible BYOK and proceed one SaaS phase at a time. See [the roadmap](../PRODUCTION-SAAS-PLAN.md) and [Phase 0 task](../tasks/saas-phase-0.md). Attached original specifications remain historical input; current owner instructions govern the SaaS direction.

## Status meanings

- **Accepted:** explicitly requested or already accepted direction.
- **Development default:** engineering/product choice used for synthetic development; can be revised before its external commitment.
- **Pending owner:** cannot infer this business promise or spending preference.
- **Pending evidence:** benchmark, vendor eligibility or operational testing must establish it.

## Product and architecture

| ID | Choice and current value | Status / reason | Responsible person | Required before |
|---|---|---|---|---|
| D01 | Customer self-service with separate owner/admin tools; restrained modern colors and guided upload/review/download | Accepted; owner's selling and UX goals | Engineering | All web phases |
| D02 | First audience: invited bookkeeping teams and small businesses | Development default; endorsed roadmap audience, narrow enough for meaningful bank/card trials | Owner | Pilot recruitment and final marketing |
| D03 | Bank/card statement PDFs and supported images; six outputs: Excel, generic CSV, QB 3/4-column CSV, Xero CSV, OFX | Accepted existing capability scope; retain merge, categories, Excel review and advanced/operator tools | Engineering | Feature contract and implementation |
| D04 | Invoices, direct bank feeds, accounting account sync and `.qbo` are outside this release | Development default following current engine limits; import files are the real capability | Owner / engineering | Public feature claims |
| D05 | React/TypeScript frontend, thin FastAPI service, existing Python Decimal engine | Accepted architecture direction; reuse current work and authoritative financial checks | Engineering | Phase 1 |
| D06 | PostgreSQL metadata/queue, private object storage, independently restartable CPU worker; filesystem CLI adapter retained | Accepted architecture direction; one source of truth per deployment and bounded background work | Engineering | Phase 1 contracts |
| D07 | One origin for site/API; maintained OIDC implementation, server sessions and invite-only access first | Development default; simplify secure sessions and limit initial abuse | Engineering | Phase 1; vendor selected for deployment later |
| D08 | Workspace owner/editor/viewer; platform administrator separate; no implicit admin access to customer documents | Development default; least privilege with explicit support grants | Engineering | Phase 1, detailed in [permission map](FEATURE-MATRIX.md) |
| D09 | Hosted changes use an expected revision, exact decimal strings, server checks, actor/history and invalidation of stale outputs | Accepted financial/review requirements | Engineering | Data contract and Phase 3 |
| D10 | Customer preview and public sample remain synthetic and clearly labelled; real-mode failures never use demo fallback | Accepted existing frontend behavior | Engineering | Every web phase |
| D11 | Optional BYOK, custom HTTPS compatible endpoints, discovered/manual model IDs, evidence-based effort up to Max | Accepted owner requirement; no universal Max assumption or silent downgrade | Engineering | Phase 4 |
| D12 | Workspace owner controls connections, terms, per-job AI consent and page cap; editor can process only within a current authorization | Development default; owner holds the workspace provider cost/privacy decision | Engineering | Permission contract and Phase 4 |
| D13 | Only fake providers and synthetic statements in automated tests; real inference requires explicit customer/owner action | Accepted privacy/paid-call boundary | Engineering | All development/testing |
| D14 | Every existing feature stays mapped to a web, admin or retained local path | Accepted; no silent feature removal | Engineering | Each phase acceptance |

## Commercial and operating choices

| ID | Choice and current value | Status / reason | Responsible person | Required before |
|---|---|---|---|---|
| D15 | Likely customers in the **US or Europe**, per owner; first launch country and permitted data region: **undecided** | Owner preference recorded; country-specific market/hosting choice remains pending; Europe is not one jurisdiction | Owner | Hosting selection or receiving customer documents |
| D16 | Owner business/merchant country and payment eligibility: **undecided** | Pending owner/evidence; provider eligibility cannot be guessed | Owner | Phase 5 payment-provider commitment |
| D17 | Prefer free local development and feasible synthetic staging; maximum paid monthly hosting budget: **undecided** | Accepted free-option preference; production costs still need approval and measurements | Owner | Creating paid resources or final prices |
| D18 | Invite-only manual-invoice paid pilot, then tested self-service checkout | Development default; supports learning demand and merchant eligibility without simulated checkout | Owner | Paid pilot offer; change if immediate checkout is required |
| D19 | Plans, currency, monthly prices, refunds, tax handling and margins: **undecided** | Pending owner/evidence; historical service quotes are not SaaS subscriptions | Owner | Published offer, invoices or checkout |
| D20 | Page/byte/job/team limits and first cohort size: **undecided**; explicit conservative synthetic limits chosen for tests only | Pending evidence/owner; benchmark and budget determine actual quotas | Engineering / owner | Capacity selection and customer plans |
| D21 | Live-data retention and automatic cleanup policy: **undecided**; manual verified removal retained in development | Pending owner/evidence; do not automatically apply local seven-day preferences to cloud | Owner / engineering | Customer terms and real documents |
| D22 | Backup retention/expiry, restoration policy and tombstone replay: **undecided** | Pending evidence/owner; live deletion cannot promise instant backup erasure | Engineering / owner | Real documents and deletion wording |
| D23 | Support contact, hours, response targets and platform operator: **undecided** | Pending owner; support must have a real destination and responsible person | Owner | Paid pilot and public contact route |
| D24 | Availability, maximum data loss and recovery time: **undecided** | Pending evidence/owner; must follow restore drills and measured topology | Engineering / owner | Customer service promises |
| D25 | Identity, compute, database, object storage, email and payment vendors: **unselected** | Pending evidence; shortlist follows region, resource/license/eligibility and cost review | Engineering / owner | Actual deployment/integration commitment |
| D26 | Legal/privacy text and subprocessor inventory: **pending chosen market/providers and qualified review** | Pending owner/evidence; no unsupported compliance badge or financial-advice promise | Owner | Public signup/paid pilot/customer documents |

## Work permitted while business answers are pending

Implement synthetic contracts and local foundations without creating accounts, subscribing to paid services, processing customer documents or publishing provisional prices. Region, retention, quotas and vendor integrations are validated deployment configuration, not hard-coded global guesses. Reject real-mode configuration missing mandatory operating policy before opening customer intake.

Keep database state, secrets and storage interfaces independent of vendor brand. Use a local maintained identity provider/test issuer for synthetic auth integration; the production issuer must separately meet the chosen market and security requirements. User/issuer subjects map to server membership, never browser-supplied roles.

## Change control

Changing money/source/output-affecting settings creates a new job revision and invalidates dependent checks/artifacts. Changing model/endpoint/effort/terms requires renewed AI consent without resetting consumed/reserved pages. Plan and global configuration changes are versioned, audited and validated before activation. Changing an accepted architecture decision requires a superseding record in [the ADR history](../DECISIONS.md), not erasure of prior evidence.

## Verification of task 0.1

All choices have a status, responsible person and point where they are required. Customer geography, business country, budget, prices and retention have not been fabricated. The feature/permission map implements the development defaults; later phases still need working code and their own acceptance evidence.

## D14 — Phase 2 bounded byte upload and capability-only worker (10 October 2026)

Accepted implementation: bounded buffered raw uploads avoid multipart scratch spooling, with one file/request, CSRF/idempotency/expected-revision/name/synthetic headers and private hash-verified inventory. Worker SQL claim/heartbeat/publish functions and a private Unix capability broker replace unscoped document-table/S3 credentials. Docker internal networking plus disabled public DNS enforce offline processing. Result IPC uses bounded JSON rather than unpickling parser output. Hash-verified models are mounted read-only. Captured page quotas and lease generations fence stale/cancelled/revoked/deleted work. PostgreSQL snapshots reuse the existing Decimal/parser code; financial success always remains source-review-required. Production isolation, artifact/SBOM/native package freeze, region/backup/retention and release reviews remain separate gates.

## Phase 4 implementation decisions

- Hosted AI corrects existing normalized cells only, with unchanged count/order and atomic all-page validation. Every AI row remains source-untrusted until full source review. Missing-row recovery/raw-page inference is outside this first dispatch scope.
- Conservative one-page/one-request reservations persist across consent renewal, configuration changes, cancellation and uncertainty. No automatic completion POST retries; explicit risk acknowledgement creates another reservation. Application counts do not prove dollars charged.
- API-side trusted gateway runs separately from parser authority. Local single-process restart obtains an OS lock plus SQL lock before cleanup acknowledgement; production interrupted cleanup remains withheld until deployment adds verified teardown recovery. SQL ownership alone is not proof that old memory is gone.
- Global config versions are immutable; activation snapshots processing, exports, templates and profiles into future jobs. Private customer scaffold words never publish automatically. Global profile activation requires exact passing synthetic evidence plus explicit private-fingerprint review.
- Support authority is named, job/revision/data-class scoped, 1–60 minutes, fresh MFA checked on every read, immediately revocable and audited. Platform admin status adds only a private synthetic diagnostic workspace, never implicit customer membership. Metrics suppress groups below five workspaces.
