# Hosted data, revision and worker contract

**Status:** Phase 0 task 0.3 specification, not database migrations or a working worker. This extends the [permission map](FEATURE-MATRIX.md) and [decision register](DECISIONS.md). The existing CLI keeps its current local records.

## Ownership and storage model

| Entity | Key relationships and constraints | Purpose |
|---|---|---|
| User / server session | User is unique by validated OIDC issuer+subject, not email. Session stores a hash of its opaque cookie token, user, selected workspace, expiry and revocation. | Authentication context; no browser role authority |
| Workspace / membership / invitation | Membership unique on workspace+user; active owner/editor/viewer. Invitation binds workspace, intended identity, role, expiry and one-use token hash. Final active owner cannot remove/demote self without atomic transfer. | Customer isolation and team control |
| Job | Opaque UUID, workspace, creator, monotonic `revision`, `content_digest`, lifecycle, data-removal state, validated options/config versions. Composite unique `(workspace_id,id)`. | One hosted source of truth |
| File / artifact | Workspace+job FK, opaque object key, kind, content hash, bytes, object version, relevant revision, inventory state. Display filename is data, never an object key/path. | Original, unlocked/normalized document, page preview, workbook, output, ZIP and manifest |
| Statement / canonical row | Workspace+job FK, statement/order sequence, exact Decimal domain JSON snapshot or lossless rows, page/file provenance. Use decimal string JSON or exact numeric columns with explicitly supported range/scale; never floats. | Authoritative extraction and financial validation |
| Review revision / event | Workspace+job, previous/new revision and digest, actor, command metadata, checks invalidation; changed private values stay in protected job data. | Atomic changes and source-check provenance |
| Operation / attempt | Workspace+job, input revision, action/options hash, idempotency key, state, lease token/generation, worker, heartbeat, attempts, error code and publish references. | Durable work queue and fenced execution |
| AI connection / consent / reservation | Workspace connection metadata with key ciphertext/version; job consent binds content/provider/model/effort/terms; reservation unique on operation+page+attempt, with reserved/settled/uncertain state. | Optional bounded authorized provider access |
| Rule / settings / config version | Customer records scoped; shared profiles/prices/templates separate platform scope. Effective version frozen on job where outputs/cost depend on it. | Validated configuration without global retroactive changes |
| Usage / entitlement / payment event | Workspace billing references and idempotent server event IDs; payment webhook identity/signature and event order recorded separately from user sessions. | Quotas and paid access; no trusting browser entitlement |
| Audit / support grant / deletion record | Workspace+resource scope where applicable; minimal event metadata, assigned support actor, permission class, expiry/revocation. Deletion tombstone and remaining inventory references. | Auditable authorization and verified removal |

All private child references use composite workspace+parent constraints, not only globally unique IDs. Apply workspace filtering at every repository method; row-level security can be a second barrier with a non-owner application DB role and a transaction-scoped workspace context. Workers use an equally scoped context. Never put customer content into global operational lists or audit/log summaries. Sensitive operational tables such as sessions and webhook events are accessible only to their service, not ordinary members.

Private object keys are opaque, server-generated and unrelated to filenames/account numbers. Download authorization is performed at request time, followed by streaming through the API; do not issue long-lived bearer URLs that outlast deletion/revocation. Storage writes publish pointers only after checksum verification. A sweeper deletes unreferenced temporary objects after a safe grace window, checking active upload/operation ownership.

## One authoritative service boundary

Introduce scoped `JobRepository`, `StatementRepository`, `ArtifactStore`, `OperationRepository`, `ConsentRepository` and transaction/unit-of-work interfaces. Application commands receive an authenticated `ActorContext` with server-resolved workspace/capabilities, not an unchecked workspace string. Financial normalization/validation/writers keep existing pure domain behavior.

The local adapters continue using `orders/store.py` and existing CLI paths. Hosted adapters use PostgreSQL plus object storage. Extraction, workbook review, export, delivery and deletion must move their persistence decisions behind these interfaces incrementally; wrapping CLI subprocesses with a second database record does not satisfy this contract. Worker scratch copies are disposable and cannot become a second authoritative `order.json`. Run repository/service parity cases across local and hosted adapters. Do not promise unchanged output bytes when a change intentionally adds accurate disclosure/provenance; compare core financial fields and approved writer goldens.

The current `Order.order_id` validator accepts only the local date/channel ID pattern. A hosted UUID cannot be inserted into that model unchanged. Shared application job records must stop assuming the local filename/ID syntax: the local adapter preserves legacy IDs and validates confined paths, while the hosted adapter validates opaque UUIDs and resolves object references. Pure financial `Statement`/`Transaction` records are retained. Do not weaken filesystem path checks to accommodate hosted IDs or expose legacy operator channel/alias through public IDs.

## Revision and digest rules

`revision` is a server-owned monotonic integer for all changes that affect source interpretation, canonical rows, output options, categories, account identity or processing policy. `content_digest` is SHA-256 of a specified canonical representation of source hashes, relevant options/config versions and ordered domain statements. Specify that representation in implementation tests; plain browser JSON reserialization is not authoritative.

Keep the existing core statement digest/version functions for CLI workbook compatibility, with an explicit mapping from the hosted job revision to the contained statement digests. A hosted workbook carries job ID, workspace-scoped lookup, job revision and exact statement digest; customer-provided workbook metadata never establishes authorization.

Each relevant command includes `expected_revision`. In one short transaction, lock/check the job, validate the complete batch, apply domain changes, advance revision/digest, invalidate source attestations, exports and download permissions, and add its actor event. A stale request returns `409 REVISION_CONFLICT` without partial edits. Category/output option changes invalidate outputs; source/row-changing operations additionally invalidate source checks. Permission/config changes revoke access or AI consent without erasing usage. Idempotent replay of the same accepted command must return its recorded result even if the current revision has advanced; a changed payload under the same key returns conflict.

Sources and financial evidence stay separate. A financial verdict proves only the checks actually present. Current spot-check completion binds sampled and fixed row IDs to the revision/digests; AI-source acknowledgement binds all required AI rows separately. Normal customer export cannot bypass either gate. Platform exceptions require MFA, owner-approved action scope, reason and truthful export disclosure; mismatched account/currency/direction can never be bypassed.

## Lifecycle versus execution state

Retain CLI lifecycle names: `created`, `intake_done`, `extracted`, `needs_review`, `reviewed`, `exported`, `delivered`, `closed`, `failed`. The hosted lifecycle is set by domain results, not by optimistic browser timers.

Operation states are separate: `queued`, `running`, `awaiting_input`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `uncertain`. Deletion state is separately `active`, `pending`, `partial`, `removed`. A job can remain `needs_review` while a validation operation is running; a delivered job can be deletion-pending while downloads are already blocked.

| Action | Preconditions and durable result |
|---|---|
| Create/upload/intake | Create records in `created`; stage/check object bytes before file inventory activation. Intake success produces `intake_done`; a password wait is `awaiting_input`, not false success. Failed upload cleanup remains inventoried. |
| Extract/re-extract | Current accessible input revision; successful canonical publication yields `needs_review` or `reviewed` after domain validation. Existing data cannot be overwritten by a result based on an old revision. |
| Review/recheck/source confirmation | Editable stages; whole-batch commands and current digests. Reviewed/exported data can be reopened through an explicit revision-changing command that immediately revokes outputs; retain the CLI's safe command constraints. |
| Export/delivery | Current revision, permitted financial/source gates and identity; stage all artifacts then publish the verified manifest as one result. A verified delivery package becomes `delivered`; downloading is not proof of client receipt/email dispatch. |
| Failed operation/retry | Record a safe stage error while preserving last committed data. Retry is a new fenced attempt on a retryable stage; never set lifecycle backward or silently repeat uncertain external work. Abandon remains possible for failed/corrupt jobs. |
| Remove/abandon | Owner explicitly confirms unfinished abandonment. Atomically revoke access, mark pending and fence/cancel operations first. Cleanup retries keep `partial` and issue no certificate. `closed`/`removed` only after all live inventory checks pass. |

## Queue, idempotency and crash recovery

API mutations requiring durable replay take an `Idempotency-Key`, scoped to workspace+actor+action+resource. Store a request fingerprint and accepted response atomically with the command/queued operation. Page reservations, exports and usage events have independent unique identifiers as well. Duplicate concurrent submissions cannot create multiple live operations for the same action/input revision.

Claim queued work in a short PostgreSQL transaction using bounded selection/row locks, for example `FOR UPDATE SKIP LOCKED`. Commit a lease token and generation before processing; heartbeat renews only that token. Never keep the transaction open during OCR. Each publication checks workspace/job/input revision, lease generation and deletion fence. An expired worker cannot publish even if it finishes late. A restarted worker uses a new fenced attempt, cleans orphan scratch and resumes only an idempotent stage.

Object upload and DB commit are not one transaction: stage objects with attempt IDs, verify checksums, then publish their pointers/manifest inside the fenced DB transaction. Unpublished versions are cleanup inventory, not downloadable outputs. A failure after publish is an idempotent recorded success on replay.

AI reservation happens before external send. Timeout or crash after send may leave external completion/charge uncertain; do not claim exactly-once provider billing or automatically resend. Reconcile provider-supported request IDs where available; otherwise retain reserved usage, show uncertainty and require an explicit informed retry. A new request still obeys consent, caps and endpoint policy. Local stages may be retried automatically within bounded attempts/time; paid calls follow the separate ledger.

Cancellation is cooperative and cannot guarantee cancelling a request already accepted by a provider. Immediately block new publication/sends with the deletion fence, terminate bounded parser subprocesses where safe, and clean scratch/artifacts only after worker acknowledgement or expiry/reap. UI shows actual queued/stage/page instrumentation, never invented percentage completion.

## Phase 0 review evidence

Checked contracts against the current order transitions, domain Decimal models, workbook digest/version logic, export gate/merge behavior, local close/abandon inventory and provider page binding. Hosted concurrency, repositories and revised command parity remain implementation/test work in Phases 1–4; none of this document claims those checks passed.
