# SaaS Phase 0 — decisions and implementation contracts

**Status:** technical Phase 0 deliverables implemented on `saas-phase-0`. Product/vendor decisions remain explicitly pending where the owner has not answered. Benchmark evidence retains a multi-page OCR description mismatch; this phase establishes the design/capacity findings, not production readiness. Original Python phases 0–10 and frontend Stage B remain completed milestones.

## Outcome in plain language

Agree on exactly what customers can do, who can see their documents, how real jobs will run, and how we will prove the app works. This phase produces the blueprints and measured limits needed to implement the real backend in Phase 1. The current interactive browser preview remains available during this work.

Use [PRODUCTION-SAAS-PLAN.md](../PRODUCTION-SAAS-PLAN.md) as the overall roadmap. This checklist covers only its Phase 0. Work through the tasks below in order, save each result in GitHub, and report evidence separately from pending work.

## Current evidence to carry forward

- `frontend/src/lib/api.ts` uses same-origin `/api/v1` and a provisional CSRF header; it has no real authentication or file-upload transport. Its workspace snapshot returns complete job/row collections. Define paginated job lists, row lists and private file/page retrieval instead of treating that snapshot as the production contract.
- `frontend/src/lib/types.ts` has preview roles `customer`/`admin`, numeric preview revisions, and filename-only intake. These are provisional. Production roles come from server membership; a browser role switch cannot authorize an action.
- `src/stmtconv/orders/models.py` defines nine lifecycle states and six outputs. `orders/store.py`, intake, extraction, review, AI and deletion operate on local files/manifests. The hosted service must have one authoritative PostgreSQL record, not a second record silently competing with `order.json`.
- Review metadata and source/export checks already use digests. Decide how an integer hosted edit version relates to the exact content digest, and apply that rule to browser edits, workbooks, source checks, worker results and downloads.
- Existing synthetic acceptance has processing timings, but it does not establish capacity on a selected host. The original exploration's process memory figures are historical and cannot be used as current isolated per-job memory measurements.

## Work sequence and deliverables

| Task | Work to complete | Saved result | Verification |
|---|---|---|---|
| 0.1 Product decision register | Record the initial buyer, bank/card scope, six outputs, invite-only pilot, team roles, deployment region, retention, support, budget, capacity and payment eligibility. Separate development defaults from promises that need an owner answer. | `docs/saas/DECISIONS.md` | Each choice has a value or explicit pending status, reason, responsible person and phase where it becomes required. No invented price or hosting location. |
| 0.2 Permission and feature map | Map all 33 existing feature rows to a customer/admin/local surface, service, proposed endpoint, permitted role, storage and named acceptance scenario. Add accounts, invitations, billing, sessions and support permissions as new requirements. | `docs/saas/FEATURE-MATRIX.md` | Every inventory row is covered; owner tools and local launchers are deliberately mapped. Each private read/write has workspace authorization and a negative test. |
| 0.3 Data and processing design | Define entities, relationships, tenancy constraints, exact money, revisions, artifact inventory and local/hosted repository boundaries. Define lifecycle separately from queue states; cancellation, lease expiry, retry, stale output and partial deletion have explicit outcomes. | `docs/saas/DATA-AND-JOBS.md` | Trace upload → intake → extraction → review → exports → delivery → deletion, plus restart and stale-edit cases. No long-running database transaction or competing authoritative manifest. |
| 0.4 Versioned API contract | Produce OpenAPI with authentication/session context, jobs/uploads/pages/rows/operations, review/source checks/outputs/deletion, BYOK/settings/rules, and admin/billing boundaries. Mark later-phase endpoints as planned. Supply synthetic examples and a migration map from the provisional frontend interface. | `contracts/saas/openapi.yaml`, synthetic examples under `contracts/saas/examples/` | Validate the document using a reviewed OpenAPI validator. Match routes to the feature/permission map. Specify pagination, exact decimal strings, request limits, idempotency, revision conflicts, structured errors and safe responses. Do not claim a schema is a working endpoint. |
| 0.5 Privacy and threat design | Draw data/network boundaries. Define session/CSRF, MFA, parser isolation, password handoff, encrypted BYOK secrets, controlled egress, consent/caps, support access, log redaction, backup expiry and live-data deletion inventory. | `docs/saas/SECURITY-AND-PRIVACY.md` | Each threat has a control, owner and planned test. Trace every original/derived/temporary object to an authorized access and cleanup path. Distinguish live-data removal from backup expiry. |
| 0.6 Capacity and hosting assessment | Prepare a reproducible offline synthetic benchmark for current text/Docling paths; record cold/warm runs, isolated process-tree peak memory, page throughput, scratch/storage growth, hashes/versions and available CPU/RAM. Compare hosting/auth/storage options against those requirements and likely usage. | Benchmark helper under `research/saas/`; results and cost assumptions in `docs/saas/CAPACITY-AND-HOSTING.md` | Check rows against ground truth and preserve observed failures. Label host, workload and measurement limits. Use vendor quotes/current terms when selecting providers; report unknown prices and untested compatibility. No paid cloud resource is created in this task. |
| 0.7 Phase 1 handoff | Consolidate decisions, remaining prerequisites and the first secure backend build checklist. Define its two-workspace isolation fixture, local services, migrations, repository contracts, sessions and CI gates. | `docs/tasks/saas-phase-1.md`; progress entry | The next assistant can implement Phase 1 without guessing tenancy, API behavior, data authority or revision rules. Open business decisions have explicit boundaries. |

## Defaults and owner choices

Development defaults come from the approved direction: React/TypeScript screens; FastAPI and the existing Python Decimal core; PostgreSQL metadata/queue; private object storage; separate CPU worker; synthetic data; optional BYOK with capability-supported effort including Max. Start with invited bookkeeping teams/small businesses and plan a manual-invoice pilot before online checkout, unless the owner chooses another audience or sales path.

Proposed workspace roles are **owner**, **editor** and **viewer**. The owner manages members, BYOK connections and workspace commercial settings; editors process/review jobs; viewers read permitted job pages and current outputs. Platform administration is a separate permission set. Define document support access through a scoped, time-limited grant with audit, rather than silently granting every platform administrator customer content access. Final permissions are specified in task 0.2.

These answers are required before the related external action, while local synthetic contracts and foundation work can proceed:

| Owner choice | Why it matters | Needed before |
|---|---|---|
| First customer market and allowed data region | Chooses vendors, privacy wording and where documents can go | Selecting/publicizing hosting or receiving real customer data |
| Maximum monthly infrastructure spend and pilot size | Sets worker capacity, quotas and affordable hosting | Creating paid resources or approving a launch offer |
| Merchant/business country and manual invoices versus checkout | Determines eligible payment services and sales flow | Payment integration/provider commitment in Phase 5 |
| Live retention, backup expiry, support contact/hours and recovery promise | Must match the actual storage and operating process | Customer-facing terms, paid pilot and real documents |

Do not publish provisional retention, subscription prices, compliance claims or service guarantees. The owner's timezone is not proof of their business country or allowed data location.

## Checklist

- [x] 0.1 [Decision register](../saas/DECISIONS.md) complete, with pending business choices labelled and US/Europe preference recorded.
- [x] 0.2 [Feature/permission matrix](../saas/FEATURE-MATRIX.md) maps all 33 capabilities and new SaaS controls.
- [x] 0.3 [Data/jobs contract](../saas/DATA-AND-JOBS.md) specifies tenancy, revisions, queue/fencing and local/hosted boundaries.
- [x] 0.4 [API contract](../../contracts/saas/README.md) validates 89 planned operations, 89 schemas and seven synthetic examples; migration documented.
- [x] 0.5 [Threat/privacy model](../saas/SECURITY-AND-PRIVACY.md) and live/backup data inventory reviewed against current services.
- [x] 0.6 [Capacity/hosting assessment](../saas/CAPACITY-AND-HOSTING.md) records seven cases/two runs each and a focused OCR failure diagnosis; exact-source failure preserved.
- [x] 0.7 [Phase 1 task](saas-phase-1.md) and two-workspace acceptance fixture specified.
- [x] Progress/decisions updated; milestone packaged for GitHub on `saas-phase-0`.

## Completion and Phase 1 entry gate

Phase 0's technical preparation is complete when the deliverables above are consistent and verified. A local synthetic Phase 1 may start with explicitly unresolved vendor/business choices if they do not affect its contracts; no real hosting, payment commitment or customer document processing is implied by that transition. Public/customer readiness still requires the corresponding choices and all later release gates.

Phase 1's first working result will be a real API with two synthetic workspaces, persisted database state and permission checks. Tests must show that one workspace cannot list, retrieve, change or discover the other's private records, and unauthenticated/forged-role/CSRF requests fail. Authentication uses a maintained implementation; it must not silently accept the preview role picker. Real conversion and uploads follow in Phase 2.

## Evidence for this planning milestone

Reviewed the existing frontend API/types, order model/store, extraction/review/intake/AI/deletion dependencies, overall SaaS roadmap, feature ledger and historical acceptance helpers. This milestone prepares the starting-phase task; it does not mark its contracts, benchmark or backend as implemented. No application code, models, vendor account or hosted environment changes are required to review this checklist.

Planning validation: all relative Markdown links in changed user-facing documents resolve, tasks 0.1–0.7 are present, and `git diff --check` passes. Application tests were not rerun for this documentation-only milestone.

## Phase 0 implementation evidence

The paragraph above records the earlier checklist-only milestone. The current milestone implements tasks 0.1–0.7 as documents, validated contracts and reproducible measurement tools. API schema checks verify official OpenAPI structure, local references, exact-money/no-key/revision boundaries, examples and unchanged 33-row inventory. They do not run HTTP routes or prove auth/tenant controls. Lint/format checks cover the new Python tools.

The full capacity probe ran 14 conversions across seven cases. Six cases matched all expected rows in both runs. The two-page scan found 12 rows with 10 exact descriptions in both runs; a targeted repeat confirmed two description differences with all dates/amounts/balances exact. Its report remains failed, and source warnings remain present. Phase 2/3 must address the review workflow/regression case; Phase 0's diagnostic task is complete. No core/UI application change, real provider inference, customer document or deployment occurred.

Validation also passed from an export of the staged Git source using the existing cloud Python environment. The official schema/license are tracked despite the broad historical `vendor/` ignore rule. This verifies fresh-source completeness, not a new Windows/ARM dependency installation. Source whitespace, new-tool lint/format and relative-document links pass; the unchanged full Python/frontend suites were not rerun for this contract/measurement milestone.
