# Dockling web app — proposal for owner review

Implementation status, 10 October 2026 (Asia/Dhaka): the owner authorized frontend implementation, testing and review. Stage B is implemented under `frontend/` with the approved visual direction. See [FRONTEND-IMPLEMENTATION.md](FRONTEND-IMPLEMENTATION.md), [FRONTEND-COVERAGE.md](FRONTEND-COVERAGE.md) and [frontend setup](../frontend/README.md). The sections below retain the complete target architecture; backend/worker/authentication/deployment requirements remain Stages C–E, rather than completed frontend behavior. The original HTML wireframe is still a planning artifact.


**Status:** owner endorsed the plan direction and requested a richer, modern color treatment; visual prototype refinement in progress. Functional application/deployment work has not started. Prepared 9 October 2026 (Asia/Dhaka). Audited source baseline: `a9bf6d36f83c4ddec2c2062465e6ff42512cc954`, branch `development-phases-2-10`. The accompanying [visual wireframe](WEB-APP-WIREFRAME.html) is an offline, synthetic design illustration, not a functioning converter or a deployed app. Open the HTML file directly in a browser to review its seven screen sketches. Links, screen targets, labels and JavaScript syntax were checked; headless capture timed out here, so browser/viewport visual validation is pending.

## 1. What this product becomes

Dockling is a statement-conversion and review workspace for bookkeepers, accounting firms and small-business finance teams. It turns bank/card PDFs or photographed statements into editable transactions and Excel/CSV/OFX files, with financial reconciliation, source review, multi-month continuity checks and a factual delivery report. Docling is the underlying local extraction library; Dockling is our application around it.

Proposed promise: **“Turn statements into accounting-ready files. Review the source. Resolve the differences. Export with confidence.”** Confidence comes from transparent checks and correction, not a promise that every layout or row is automatically accurate. The initial market is statement workflows; invoices and general document extraction remain outside this release.

The current application is a single-operator Windows-oriented CLI with Excel review. Its core services and validations are reusable. The web proposal adds customer self-service and owner administration. Do not claim accounts, subscriptions, APIs, a browser grid, or cloud isolation already exist. Historical TECH_ARCHITECTURE sections mentioning Gemini/per-page candidate mixing are superseded by implemented OpenAI-compatible adapters/whole-statement routing; use source and PROGRESS when implementing.

## 2. Recommended audience and release boundary

Owner confirmed on 9 October 2026: **customer self-service plus owner/admin tools**. Design for that customer-facing experience with a complete owner/admin console. The first working pilot may be one invited customer/workspace plus the owner; do not expose the current shared workspace to unrelated customers. Tenant separation and authorization are required before opening a multi-customer pilot.

Two roles initially:
- **Customer:** own workspace/jobs, uploads, review, exports, own BYOK connections, allowed preferences and cleanup. No access to another customer's files/keys or server configuration.
- **Owner/admin:** service operation, authorized support access, pricing/configuration, profiles, health/model setup, anonymous metrics, limits and controlled overrides. Support access is scoped, explicit and auditable, not an unrestricted default view of every document.

A reviewer/team role can follow when needed; firm-wide sharing and team invitations are additional functionality, not existing features. Prototype screens can illustrate both initial roles. The reviewed design retains all current capabilities, even when only admins see a feature.

Working name stays **Dockling** unless the owner changes it. Sales positioning and pricing require owner approval; the CLI's service quote packages are not subscription prices or a payment system.

## 3. Visual and UX direction

Owner visual feedback, 9 October 2026: keep the friendly basic layout, make it more attractive and current with color, and avoid disco/neon/futuristic styling.

Use a light blue-gray canvas and white surfaces with richer forest-teal actions, gentle peach/coral accents, dusty blue information accents and muted lavender for model/connection tools. Add soft tinted section cards, a restrained pastel gradient behind the public sample preview, outline navigation icons, stronger headline hierarchy, carefully rounded cards, thin borders and subtle shadows. Keep financial tables mostly white so status highlights and money remain readable. Hover/focus states provide polish without busy animation.

Color roles: primary actions `#16665e`; body text `#213542`; canvas `#f6f7fa`; muted text `#586c77`; gentle mint `#e3f1ea`; peach `#fff0e6`; information blue `#315f90`; lavender `#eeebfa`. Amber/red/green retain issue/warning/reconciled meanings; decorative colors never imply that data has been verified. Numbers align right with tabular digits. Use a clean system font stack, consistent outline icons, generous spacing and a compact desktop sidebar. No neon glow, animated backgrounds, excessive gradients or unrelated charts.

Primary action per screen: **Try sample → Upload → Review → Export**. Advanced settings expand only when needed. Every advanced capability remains discoverable in Settings, job tabs or admin tools. UI language uses “Needs a source check,” “Numbers reconcile,” and “Ready to export”; raw flags/error codes are available in details and support, not the main explanation.

Accessibility target: WCAG 2.2 AA for the built interface. Keyboard navigation, visible focus, meaningful labels, text as well as color for verdicts, reduced-motion support and adequate contrast. Desktop is the primary document-review experience; tablet remains useful; mobile supports uploads/status/downloads and stacked source/row review without forcing a desktop-width table. Show a larger-screen recommendation for long reconciliation sessions rather than blocking phones.

A public guided sample demonstrates real synthetic input/output and the review flow before sign-in. Sales content uses actual screenshots, export samples and precise data-handling explanations. No fake customer logos/testimonials, universal accuracy numbers, invented compliance badges, countdown pressure or fabricated time-saved figures.

## 4. Navigation and screens

| Surface | Main experience | Important details |
|---|---|---|
| Public home `/` | Benefit statement, sample preview, 3-step explanation, formats, BYOK/privacy FAQ, Try sample / Request pilot | Explain processing location truthfully; no “stays on your device” claim for hosted uploads |
| Sample `/demo` | A seeded statement and guided correction/export tour | Synthetic data, no real account/key needed; clearly identified as sample |
| Pricing `/pricing` | Clear one-off service/pilot offer and approved package explanation | Publish only approved offers. Subscription/page credits are separate commercial work; no inactive “Buy” checkout |
| Help `/help` | Import guides, supported inputs, source-review explanations, limits and setup | Help reachable in context; direct bank/accounting links are not implemented integrations |
| Access `/sign-in`, `/invite` | Invite-first pilot sign-in; appropriate recovery flow for chosen auth | No unrestricted public signup until account isolation/abuse controls pass |
| Dashboard `/app` | New conversion, jobs needing review, ready files, recent activity, retention reminders | Empty state provides sample or upload; expose only genuinely measured usage |
| New conversion `/app/new` | Guided file upload → options → intake summary → start | Password field, image ordering, currency/date examples and output choices |
| Jobs `/app/jobs` | Search/filter/status/page counts, resume a job, overdue/failed views | Backend pagination; bulk destructive actions excluded initially |
| Job `/app/jobs/:id` | Overview, Files, Review, Checks, Exports, AI, Activity & data tabs | One job can contain several files/statements; tab selection/filters survive refresh |
| Connections `/app/connections` | Private BYOK providers, discovery/manual models, model/effort picker, metadata test | Never display saved keys; Advanced adapter fields accessible |
| Categories `/app/categories` | Ordered rules, direction, match preview, per-job overrides | Shared defaults admin-controlled, customer rules workspace/job scoped |
| Settings `/app/settings` | Currency/date/output preferences, limits and data policy | Server filesystem/env/model controls are owner-only; no raw `.env` editor |
| Admin `/admin` | Profiles, pricing, operational jobs, health/models, diagnostic metrics, safe configuration | Diagnostics/redacted support export, explicitly authorized customer support access |

## 5. Main customer journey

**Discover → try a sample → sign in → upload → inspect intake/options → process → correct/source-check → choose exports → download → delete when appropriate.**

### Upload and intake

Accept PDF, JPEG, PNG and TIFF via a keyboard-accessible picker/drop zone. Show filenames, validated type/size, page count and whether pages have text, need OCR or are blank. Never trust the extension alone. Upload failures identify the affected file without losing successful selections. Encrypted PDFs open a private password prompt; password is used transiently, never stored in the job or retried automatically with a guessed value.

Image sets show thumbnails with explicit page order. Reordering before combination is new web functionality; the adapter must submit a stable ordered set matching the existing filename-order semantics. Support multiple separate statements and combined image pages. If a PDF contains several statements, let the user assign page ranges; automatic boundary detection is not implemented. Invalid/overlapping ranges show inline errors.

Simple defaults: Excel + generic CSV, local text/OCR extraction (on the user's computer for local mode, on the server for hosted mode), AI off. Currency and source date order show examples such as “31/12/2026 — day/month/year.” Source numeric order and output date format are separate controls. Current financial precision is two decimals; unsupported precision must be explained, not silently rounded into a compatible currency.

Advanced: output formats, merge same account, account identity confirmation, categorization, profile, engine, explicit page groups and optional AI. Service channel/client alias/package metadata is in an operator section. Pre-extraction editing of configuration is new API work; changes after extraction must invalidate affected reviews/spot-checks/exports or require a fresh extraction. Never silently reinterpret an existing reviewed job.

After intake show text/scanned/blank counts, quote range and provisional processing estimate. Current prices are the service's configured quote values. OCR estimates use recorded timings only when enough successful orders exist; distinguish default estimates, queue wait and actual runtime. No automatic charging or payment authorization exists.

### Processing and recovery

A durable worker processes one OCR job at a time initially. Show actual stages: queued, inspecting files, extracting, checking, ready for review, preparing exports. The current library does not provide complete live per-page progress; add instrumentation before showing a percentage. Otherwise show an indeterminate stage with elapsed time, never a fabricated countdown.

Reloading/closing the browser does not cancel a server job. Persist job state and resume viewing. Prevent double-click/retry duplicate work with idempotency keys. Queue state is separate from the existing order state machine. Map failures into plain explanations plus safe error code and actionable Retry or Fix settings controls. Only restart stages supported by the actual state; otherwise offer a new conversion preserving the original until the owner chooses cleanup.

Queued cancellation is possible with new worker support. Running cancellation needs cooperative safe boundaries; do not kill a process mid-write or claim it cancels a paid provider call already sent. Pause-for-review already exists and is essential.

### Browser review — the central selling experience

Desktop layout: source document/page viewer on the left, editable transaction grid on the right, issue/check panel and primary action visible. Select a row to open its **source page**. Exact cell/bounding-box highlights are not available in all current saved provenance; promise page navigation first, add precise overlays only where reliable coordinates are retained.

Grid: date, description, debit, credit, balance, category where applicable, check status. Expand a row for expected balance, difference, flags, engine, source file/page, inherited date, manual fix/source confirmation. Toggle “Needs attention,” “AI rows,” “Source checks,” and “All rows”; allow search/sort without changing canonical financial sequence. Large jobs require virtualization and accessible alternatives.

Edits stay as a staged batch until **Save changes & recheck**. Support fix, insert after, delete, clear optional money fields, note and discard unsaved changes. Validate exact amounts, dates, movement signs, required fields and revision before writing. Deleted rows remain auditable; financial totals reconcile against canonical rows, not filtered/sorted browser results. Changing category alone is distinct from changing source money.

Show before/after values and financial effect. Stage undo is supported before save; restoring a saved correction is a new revision with history, not deletion of audit evidence. Warn on navigation with unsaved edits. If a concurrent change occurs, refuse a stale save and offer reload/compare rather than overwriting it.

Retain **Download Excel review workbook / Upload corrected workbook** for users who prefer Excel. Reuse its validation and stale-workbook protection. Browser edits require a shared typed review service; do not silently bypass the workbook's validation or implement financial rules in JavaScript.

### Checks, spot-check and AI source confirmation

Separate **financial reconciliation** from **source accuracy**. Show opening/closing, printed debit/credit totals, running-balance differences, missing pages, dates outside the period and possible duplicates. Missing evidence stays “not available,” not zero. Duplicate warnings do not automatically remove transactions.

Verdict labels: VERIFIED → “Numbers reconcile”; VERIFIED_BY_TOTALS → “Reconciles by totals”; VERIFIED_WITH_FIXES → “Reconciles after corrections”; NEEDS_REVIEW → “Differences need review”; UNVERIFIABLE → “Not enough evidence to reconcile.” Tooltips preserve exact meaning.

Spot-check wizard displays deterministic sampled rows plus all manually fixed rows next to their source pages; record pass/fail/note/revision. Editing relevant data resets completion. AI-derived rows require a separate full source-comparison acknowledgement, even when totals reconcile. That acknowledgement is not an amount fix and does not fabricate fix counts.

### Export, delivery and cleanup

Present Excel, generic CSV, QuickBooks 3-column CSV, QuickBooks 4-column CSV, Xero CSV and bank/card OFX as distinct format choices with example columns/date formats. Explain that “QuickBooks/Xero” means downloadable import files; there is no direct accounting login/sync integration or `.qbo` writer. Reconcile preview money/date cell types with actual files; preserve formula-text escaping, deterministic content and QB row splitting.

Merge screen confirms actual account identity, currency and asset/card direction before combining, then visualizes period overlap/gaps and exact closing→opening differences. Display masks alone cannot establish identity. Provide per-month and All Transactions workbook previews. Categorization shows ordered keyword/regex rules, direction and job overrides; new UI validation must restrict slow expressions before hosting.

Blocking issues offer a direct fix action. Existing unverified/unverifiable/skip-source-check overrides stay in an admin-only exceptional path with explanation/acknowledgement and factual disclosures. Identity mixing is never overridden. Permission enforcement must exist on the server, not just disabled buttons.

Exports list format, revision, generated time, parts and safe verification status. Download individual files or the complete ZIP with delivery note, verification summary and data-handling statement. Check file hashes/revision before delivery. “Package ready” does not mean an email was sent or received; client dispatch remains a separate manual action unless a later integration is approved.

Data tab displays retention policy, overdue status, consent/history, logical deletion result and a downloadable certificate. Delete now is explicit, with a list of what will be removed, including the delivery ZIP. Unfinished jobs support explicit abandonment. Partial deletion remains pending with retry and no success certificate. Scrubbed certificates/anonymous metrics must not retain client descriptions, aliases, keys or amounts. The hosting layer must also remove previews/temporary uploads/queue payloads and document backup retention; job-folder deletion alone does not cover new server storage.

## 6. Full existing-feature coverage map

Legend: **Reuse** = existing service logic plus a new authenticated API/UI adapter. **Extend** = significant new browser or hosted behavior. **Admin** = retained owner capability. All rows remain in the plan; grouping hides complexity rather than dropping functions.

| Existing capability / source | Web home | Work required |
|---|---|---|
| `order new`, alias/channel/package, currency, dates, selected outputs | New conversion; operator details | Reuse; safe preference/update API |
| `order list/show`, history, overdue filter | Jobs, overview/activity/data | Reuse; searchable owner-scoped pagination |
| `intake`, content sniff/hash/page kind/limits | Upload and Files | Reuse + authenticated streaming uploads and quotas |
| `intake --password` | Hidden unlock prompt | Reuse; transient worker secret handoff |
| `intake --combine`, image normalization/EXIF | Ordered image preview/combine | Reuse + safe reorder adapter |
| `--force` size/page-limit bypass | Admin job override | Admin; limits remain enforced for customers |
| `quote`, pricing/add-ons, measured/default estimates | Intake summary; admin pricing | Reuse; no subscription/checkout inference |
| `extract`, automatic text/Docling fallback | Processing and advanced method | Reuse; durable queue/status instrumentation |
| `--engine`, `--profile`, `--pages`; per-page diagnostics | Advanced extraction; file/page map | Reuse; configuration edits/version rules |
| `validate`, balance/totals/coverage/date/duplicate checks | Checks and issue cards | Reuse; readable flag dictionary |
| `review`, `apply-review`, fix/delete/insert/clear and notes | Browser grid; Excel fallback | Extend shared review command service with equivalent batch validation/history |
| `spotcheck`, revision-bound samples and fixed rows | Source-check wizard | Reuse; per-row completion UI/server record |
| AI source confirmation and source warning provenance | AI-row review filter/confirmation | Reuse; full comparison flow, distinct from fixes |
| Six output types and dates/QB split | Export builder/downloads | Reuse; safe authorized file delivery |
| Bank/card identity-aware OFX | OFX export identity step | Reuse; test sign/import preview; no `.qbo` |
| Merge/monthly workbook/account confirmation/continuity | Merge step; monthly results | Reuse; known identity mandatory |
| Category rules/direction/regex/job overrides | Categories; job categorization | Reuse + scoped validated editor/preview |
| `deliver`, hashes/revision, ZIP/templates | Exports/package and data policy | Reuse; no automatic email/marketplace dispatch |
| `run`, resumable stages/review pauses | Continue job action | Reuse; worker integration/idempotency |
| `inbox`, `run.bat` | Browser upload equivalent; local setup/help | Keep local compatibility; browser cannot silently move arbitrary PC files |
| `close`, retention/overdue, partial retry/certificate | Data tab, reminders, admin overdue | Reuse + cleanup of all new storage; overdue reminder is not automatic deletion |
| `close --abandon` and anonymous outcome | Discard unfinished conversion | Reuse; explicit confirmation |
| `stats`, engine/timing/verdict/fix/page metrics | Workspace/admin usage | Reuse; owner-scoped anonymous aggregation, not fabricated revenue/time saved |
| `ai setup/list`, private provider selection | Connections | Reuse adapter logic; new per-owner encrypted secret storage |
| `ai models/test`, manual IDs | Discover/search/manual add + metadata test | Reuse; distinguish metadata from completion test |
| `ai pick`, documented capabilities/Max | Model and effort picker; capability reference | Reuse; highest known supported default, no downgrade |
| `ai adapter`, chat/responses/JSON/tokens/routes/temperature | Advanced connection settings | Reuse; outbound policy and compatibility validation |
| `ai-consent`, terms/binding/page budget/retries | Job AI tab + consent step | Reuse; explicit activation and remaining-budget display |
| `profile scaffold/test`, validated YAML layout rules | Admin profile workshop | Admin; private scaffolds may contain source text; publication requires sanitized fixtures |
| `doctor`, `models download`, hash verification | Admin system health/model maintenance | Admin; network only for explicit setup; no customer server path exposure |
| `selftest`, `demo`, synthetic assets | Admin self-check; public guided sample | Reuse; isolate sample workspace, no customer-data leak |
| YAML defaults/prices/exports/categories/profiles/templates | Safe settings/admin editors | Reuse schemas; versioned validated writes, no arbitrary executable/config injection |
| CLI help/version/config/env selection | About/help/local setup | Keep CLI usable; config/env selection is deployment control, not a customer filesystem picker |

Reserved flags are not implemented promises: `show_full_account` is present in the manifest but does not establish a full-account UI feature; account masks remain the display default. `document_type=invoice` is reserved and rejected. Customer names/files are not published into shared profile fingerprints. Generic plus three synthetic layouts are the current bundled examples, not verified coverage of every real bank.

## 7. BYOK connection experience in detail

Connection wizard: nickname → custom HTTPS base URL → hidden API key → API preset (Chat Completions or Responses) → Discover or enter model ID → effort → terms confirmation → save. Saved key field reads “Configured” with Replace/Remove, never returns the original key. Key deletion/provider deletion requires a new management API (not currently in the CLI).

Effort menu lists only supported `provider_default`, minimal, low, medium, high, xhigh, max choices. Default to highest known supported; label Max with capability evidence. If discovery gives no capabilities, show provider default and an explanation; allow model-specific documentation/reference registration. Refreshing models must not discard operator-documented capabilities without an explicit review. Rejected settings fail with a clear message and retain chosen settings.

Metadata connection test sends no statement content; it does not prove completion parameters/effort work. An optional synthetic inference test shows possible cost and runs only after explicit confirmation. Provider-specific schema, effort parameter, token field, routes and zero-temperature controls remain under Advanced.

Per-job AI panel is off by default, displays provider/model/effort, consent/note, terms state, used/remaining page cap and source-review requirements. Existing consent binding is preserved across retries; changing connection/model/effort requires consent renewal without resetting budget. Insufficient safe table cells produce a manual/profile recovery path, not a whole-PDF upload. All processing requests remain behind the adapter gate.

Hosted custom endpoint validation must block private/internal/link-local/metadata destinations and DNS-rebinding routes; current loopback allowance is suitable for local mode, not arbitrary hosted customer endpoints. Keep admin-maintained outbound policy and ownership checks. A model server on the customer's localhost is not reachable from a hosted server; hosted UI must explain this and offer local mode or an approved reachable endpoint.

## 8. New architecture needed to make the screens real

Recommended frontend: **React + TypeScript + Vite**, Tailwind-based design tokens, accessible headless components, a typed API client/query cache, forms with shared schema validation, virtualized grid, and a locally bundled PDF.js viewer plus image preview. Confirm actual package versions/licenses when approved; do not install a frontend stack during this planning task. Keep marketing and app in the same codebase initially.

Recommended backend: **FastAPI** adapters calling Python services directly, a durable background worker and SQLite metadata/jobs for a single-server pilot. Reuse file-based per-order artifacts behind the existing store, organized under verified per-workspace roots. Database maps account/workspace ownership to opaque order IDs and durable jobs; it does not replace financial core rules. Serialize Decimal values as exact strings; JavaScript displays/formats amounts and never computes the authoritative reconciliation.

Browser edits need `ReviewCommand`-style typed actions extracted from workbook logic, canonical revision checks, atomic persistence, history and spot-check/export invalidation. File replacement/date-order/profile changes also need a consistent revision contract. Store enough source provenance for page viewing; do not fabricate coordinates. Browser schema errors give field/row feedback; backend remains authoritative.

Web authentication/session recovery is new work. Prefer a maintained implementation with secure HTTP-only sessions, CSRF protection, rate limits and permission checks on every job/file/connection/admin request. Invite-only access first; no home-grown password cryptography or secrets in browser localStorage. Provider keys must be encrypted with deployment-held keys or a supported secret service, isolated per owner, absent from ordinary API reads/logs, and removable. Existing plaintext local providers.json is not a hosted tenant vault.

Uploads validate actual content, size and page count; use confined storage, generated server filenames and safe document handling with resource bounds. Worker tasks persist IDs/configuration, not passwords/API keys in readable queue records. Recovery after process restart is explicit and never silently repeats an already-reserved paid request. Decide whether encrypted short-lived credential handoff or immediate synchronous intake best fits password-protected PDFs; prove cleanup before hosting them.

Local mode binds to loopback and retains local files. Hosted mode uses HTTPS, private storage and an explicit server-processing notice. API and worker use one deployment/config boundary; keep pure core and CLI behavior intact. Serve compiled static UI from the same origin for the first pilot, reducing deployment and cross-origin complexity. Poll durable job status initially; tunnels/free tiers may not support long-lived event streams reliably.

Example API families (proposed, not implemented): session/invitations; scoped jobs/uploads/intake/quote; enqueue extraction and operation status; statements/source-page streaming; review batch/workbook/spot-check; merge/categories; exports/package/download; consent/connections/models/capabilities; deletion/certificate; admin profiles/config/health/model setup/selftest. An endpoint acceptance checklist must map every coverage-table row before pilot release.

## 9. State, errors and permissions contract

Map existing states explicitly: created→Draft; intake_done→Ready to process; extracted→Checking; needs_review→Review needed; reviewed→Ready for source check or export depending on spot-check; exported→Files generated; delivered→Package ready; closed→Data removed; failed→Needs recovery. Add a separate queued/running/interrupted operation indicator, not a fake `order.status=processing` unsupported by the state machine.

Each surface designs loading, empty, success, partial success, offline/browser disconnect, validation error, timeout, quota exceeded and expired/deleted states. “Ready” requires both relevant financial verdict and current source-check gates. Downloads generated for an old revision are marked stale and blocked. Save/discard is explicit; destructive operations use accessible confirmations. Unauthorized users get no leaked job existence/filenames. In the first release, server admin manages global profile/config/model actions; regular customers cannot bypass checks, execute YAML, change retention policies globally or inspect logs.

The first server pilot remains one durable filesystem deployment with controlled concurrency. Multiple replicas, object storage, PostgreSQL, cloud workers and team collaboration need an explicit storage/locking migration; no claim that SQLite/file locking already provides a distributed service.

## 10. Buying experience and commercial boundaries

Attract the right users by letting them see a real sample, understand supported formats, preview correction/source comparison and inspect exports before commitment. The landing page should answer “Will this handle my statements?”, “What happens when numbers differ?”, “Where does my data go?”, “Do I need an AI key?”, and “Can I import the result?”. Explain remaining bank/layout limitations clearly.

Initial primary CTA: **Try a sample**; secondary **Request a pilot** through an approved working contact mechanism. Do not invent a contact address/form backend or claim it sends anything before implementation. A paid pilot/service can be fulfilled manually. Revenue dashboards, automated invoices, subscriptions/page-credit billing, payment webhooks and customer billing portals are new scope; proposed as a separate commercial stage after real pilot demand. If the owner wants checkout in the first release, choose the pricing/payment provider before designing its final flows and include sandbox payment, cancellation, refunds and entitlement checks. No “Buy” button leading to a simulated checkout in a real pilot.

Support multiple sectors as buyer examples only when they share the bank/card workflow; do not advertise invoice extraction, live bank feeds, automated tax/accounting decisions or certified financial accuracy. Complete pending license/model provenance review and actual field/import checks before making commercial distribution/accuracy claims.

## 11. Build order after approval

| Stage | Deliverable | Review / acceptance |
|---|---|---|
| A — Design approval | This plan, screen inventory, wireframe; choose audience/branding/style/pricing scope | Owner edits/accepts proposal; no application implementation yet |
| B — Interactive frontend prototype | Landing/sample/dashboard/upload/review/checks/exports/connections/settings/admin with a shared design system and synthetic fixtures | Owner can click the major journeys at desktop/tablet/mobile sizes; every coverage row has a route/control; demo-only mode is explicit |
| C — Local working web application | API + worker + source viewer + browser/Excel review + all existing export/AI/privacy functions integrated | Actual PDF → review → six outputs → package → verified deletion; no fake results substituted for backend outcomes |
| D — Private customer pilot readiness | Authentication/isolation, hosted key handling/outbound policy, quotas, restart recovery and cleanup for all new artifacts | Cross-user negative tests, gate bypass tests, no secrets/client content in logs, stale edits/downloads rejected; test users and synthetic documents first |
| E — Staging deployment | Reproducible local Windows startup plus one selected host with health/worker/storage/rollback instructions | Fresh install and hosted end-to-end test; owner controls cloud credentials, paid inference and final publication |
| F — Commercial validation | Permitted bank/layout samples, real spreadsheet/import checks, pilot feedback, approved pricing/contact and optional billing scope | Measured correction time/accuracy and real willingness to pay; no invented sales claims |

The functional acceptance at C/D includes all current feature-table rows, including advanced/admin and Excel fallback. Staging review is not an excuse to omit features. Rollout order limits operational risk; it does not authorize silently dropping the requested coverage. Any approved scope change updates this plan and the feature ledger.

Prefer a new feature branch based on development-phases-2-10 when building, preserving the working CLI milestone and original phase history. Record web stages separately from completed phases 0–10. Push reviewable milestones; do not merge main automatically.

## 12. Deployment and testing requirements

Develop/test the web app on localhost on Windows first, keeping the documented Python setup and adding verified frontend prerequisites/start scripts. A public staging link is a later step. Oracle Always Free is a candidate full backend only if account/capacity/ARM package compatibility is verified. Google Cloud Run can fit occasional testing within allowances but needs ephemeral-state/storage/worker adaptations and billing awareness. Render Free can host a light preview; it cannot be treated as a verified full OCR server with durable storage. A tunnel can expose a private local server while that computer stays on. Recheck official terms at selection time; free hosting does not cover BYOK inference charges.

Testing: existing 314-test cloud baseline must remain meaningful; run relevant/full backend gates after changes and retain exact golden exports. Add frontend component/route/accessibility checks and browser end-to-end journeys for upload/passwords, ambiguous dates, scanned/source warnings, exact edits, Excel import, merges/categories/OFX, rejected AI settings and budgets, stale revisions, download permissions and partial cleanup. Use fake providers/no paid calls for automation. Test worker restart/idempotency/capacity, deletion of temporary preview/upload/secret material and tenant isolation; do not mark mocked UI interactions as real conversion tests.

Public prototype review uses synthetic data. Actual Windows, Excel/accounting imports, real camera/field samples, ARM hosting and actual BYOK completion are pending until run. Hosted privacy wording and backup/key policies require verification of the chosen deployment, not a generic “secure” badge.

## 13. Review choices and assumptions

Recommended defaults for review:
1. **Confirmed audience:** customer self-service with owner/admin tools. Invite-only pilot remains the recommended rollout.
2. Bank/card statements for accountants/bookkeepers as the first market.
3. Dockling name; refreshed light workspace with forest teal, peach, dusty blue and muted lavender; accessible responsive layout, no neon styling.
4. Complete current feature coverage with advanced/admin placement; preserve CLI and Excel fallback.
5. Local functioning web app before private staging; hosting selected after runtime checks.
6. BYOK optional/off by default; highest known supported effort, Max only with evidence.
7. Sample-first selling experience; paid pilot/service offer before automatic subscription billing.

Owner can accept these defaults or change: audience, name/style, navigation/workflow, initial commercial/payment scope, and hosting route. The owner has endorsed the plan direction with a visual refinement request. This update refines the synthetic planning preview; it does not claim that a functioning web application or deployment exists. The agreed look will carry into the frontend build, with publication remaining a separate step.
