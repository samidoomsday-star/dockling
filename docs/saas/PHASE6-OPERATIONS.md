# Phase 6: security, monitoring and recovery

Engineering implementation is on `saas-phase-6`, including every earlier SaaS phase. **The production acceptance gate remains blocked.** This is a tested local development version, not permission to accept real statements or a promise of certified security.

## What changed

The administrator's Operations and recovery panel shows anonymous queue counts, failures, incomplete removals, uncertain AI outcomes and backup/restore dates. It requires fresh MFA on every read. Fixed alerts contain no customer names, document text, money, account IDs, secrets or object paths. The browser refreshes these signals every 15 seconds; someone must watch this panel or connect an approved host monitor later. No email or external alert delivery is enabled.

Public `/api/v1/health/live` reports only `alive`. `/api/v1/health/ready` returns `ready` or a 503 `unavailable`, checking database connectivity, private storage and the worker's recent heartbeat. These are technical availability signals; neither means production security approval, spare storage capacity, payment readiness or an OCR accuracy guarantee.

API admission is bounded to 16 concurrent requests by default. Further requests fail promptly with 503 rather than accumulating unbounded upload memory. Metadata bodies stay below 64 KiB, uploads use the configured bounded size, and body reading has an absolute 30-second deadline. Early errors now receive the same privacy/security headers as ordinary responses. HSTS is emitted in the configured HTTPS production mode. Limits are centrally validated configuration, not claims about a selected hosting plan.

Sessions refresh on focus and every 30 seconds, expire at the server's stated deadline, and hide private content immediately when a private request receives 401. User/workspace/role changes clear private query caches. Expired MFA hides administrator tools. Cached data never substitutes for a denied API response.

## Security findings and license scope

Observed 11 October 2026: OSV returned no known advisories for **147 installed Python packages** and npm audit returned zero for the locked frontend (**317 package records**). The observed pip/setuptools advisories were addressed using official SHA-256-pinned releases, pip 26.2.1 and setuptools 84.0.0. This is advisory-service coverage, not independent signoff.

The worker now uses digest-pinned Python 3.12.14 on Debian 13, signed HTTPS package updates, and a runtime package stage without pip, setuptools, wheel, their vendored bootstrap copies or ensurepip. The runtime still imports actual CPU Torch and Pydantic and retains its non-root/read-only/private-network/SQL restrictions.

Verified Trivy 0.75.0 found **59 high and one critical native-package findings**, all without a vendor fixed version in this scan. The critical finding is `libxml2` CVE-2026-6653. Its Python package result has no high/critical findings. [The public findings record](PHASE6-SECURITY-FINDINGS.json) identifies the exact image, scanner checksum and each package/advisory. There is no suppression or `ignore-unfixed` exemption. These findings **block production**, even though functional tests pass. Refresh the scan after vendor updates, rebuild the image, and rerun the strict gate; do not blindly change the pinned image or checksums.

Run `.venv/bin/python scripts/saas-security.py --audit` to recreate the private dependency/license inventory and public advisory checks. Run `.venv/bin/python scripts/check-worker-security.py` for the strict native gate: it exits nonzero on any high/critical finding or an unavailable scan. Development CI explicitly uses `--report-only` and records the blocked decision in its summary. The separate **Strict worker release security gate** workflow is manually run on the branch being considered for release and must pass before launch. A green development workflow does not override that gate.

No new runtime library was added for backup encryption; it uses the existing cryptography package. Installed package metadata includes 14 Python license fields marked `requires review`; inspect the actual upstream LICENSE/NOTICE files rather than treating missing metadata as permission. Debian native LGPL/GPL/component terms and redistribution notices require review too. Existing research observed Docling MIT, layout-model Apache-2.0, TableFormer bundle CDLA-Permissive-2.0 and RapidOCR package Apache-2.0; package terms do not settle OCR-weight terms. Keep the pinned model manifest and upstream notices. A complete transitive/model distribution review and an independent external security review are **uncompleted commercial release gates**.

## Local encrypted backup: receiving-assistant instructions

This utility accepts only the documented loopback synthetic stack. It refuses a running API, worker or identity writer and refuses unverified AI cleanup. It leaves PostgreSQL and storage running. It never replaces existing credentials or production resources. Do not overlap backup with installation, browser tests, migrations or another writer.

1. Stop the API with Ctrl+C in its terminal and verify that it exited. Stop the worker and identity with `docker compose --profile conversion -f compose.saas.yaml stop worker identity`.
2. Once on a new setup, run `.venv/bin/python scripts/saas-ops.py key-init`. It creates the ignored private `.local-saas/backup-key.bin` and refuses overwrite. Store an independent secure copy outside the archive/device. This is different from the BYOK vault key. Never send either key in chat or commit them.
3. Run `.venv/bin/python scripts/saas-ops.py backup`. Its JSON reports the archive's `file` path. The local example expiry is seven days, not an approved customer retention policy.
4. Run `.venv/bin/python scripts/saas-ops.py restore-drill --backup <reported-file>`. Substitute the actual reported path. The drill creates disposable PostgreSQL/private-S3 containers and volumes on random loopback ports, restores into those resources, verifies them, and removes only its own resources. It never restores over active volumes or the live bucket.
5. Run `.venv/bin/python scripts/saas-ops.py purge` for a dry run. Only an explicit `--apply` deletes expired, owned, authenticated archives within the backup directory. Run `expiry-drill` to verify deletion using separate temporary fictional archives, leaving source backups untouched.
6. Restart using `scripts/saas-local.py setup`, then `worker`, then `run`; use `.venv/bin/python` for each. Preserve vault material and all original volumes. A helper refusal is a failed check; follow its reason before proceeding.

Archives contain matched application and identity database dumps, all private bucket objects, private configuration and the matching BYOK vault key. A separate 256-bit AES-GCM backup key authenticates and encrypts the whole bounded bundle and expiry header. The archive inventory records hashes and sizes. Restore rejects corruption, truncation, wrong keys, unsafe paths, links, duplicates and unlisted files before starting an API. Temporary plaintext is private and removed, but file unlink is not a promise of physical SSD erasure; production encrypted storage and key management remain necessary.

Backup/restore receipts are immutable operator-written evidence. The API can read but cannot forge or erase them; the worker cannot write them. A restore receipt is written only after successful checks and removal of the disposable resources. Restored sessions/invitations/AI consent are revoked, queued/running work is cancelled, sending AI attempts become uncertain, and existing reservations remain held. SQL changes never manufacture an AI memory-cleanup acknowledgement.

A stale snapshot cannot undo a newer deletion: the local drill reads the quiesced current source's deletion journal and replays exact workspace/job pairs in the isolated restore. Files remain fenced and receive no inherited complete-deletion certificate. The observed matched snapshot needed zero newer tombstones; separate real-storage tests exercise successful replay, wrong-tenant denial and failed verification. A production disaster requires an independently retained, verified current deletion journal, membership/billing reconciliation and provider-outcome review before intake resumes. **Do not repurpose this local drill as a production restore command.**

## Operating and incident procedure

Run `.venv/bin/python scripts/saas-ops.py check` for the same anonymous operating signals; exit 2 means attention is needed. Defaults alert after 120 seconds queued, 24 hours without a current backup or seven days without a verified drill. A receipt attached to an expired backup cannot count as current restore evidence.

| Signal | Immediate action |
| --- | --- |
| Component unavailable or storage failure | Pause intake at the selected host, inspect sanitized service status and capacity, preserve volumes; do not reset credentials or claim healthy from a port alone. |
| Queue delay or repeated failure | Check heartbeat, worker resource limits and private broker; inspect the scoped operation as an authorized owner. Ordinary idempotent worker recovery is separate from a paid provider retry. |
| Uncertain AI or missing cleanup receipt | Hold the reservation, stop further sends for the affected job, reconcile the provider outcome and verify old process/container teardown. Never infer memory erasure from a database lock/state change. |
| Incomplete removal | Keep previews/downloads fenced, verify each inventory item and scratch/process receipt, retry within the exact job scope; issue no complete-removal certificate on partial failure. |
| Stale backup or unverified restore | Quiesce the synthetic local stack and complete a backup/drill; investigate expiry and independent key availability. A saved archive alone is insufficient. |
| Suspected exposure | Disable affected intake/provider sends at the selected host, revoke sessions/support grants/connections, preserve minimal authorized evidence, rotate the affected secret with matched vault/backup recovery, and follow the approved notification policy. Do not paste private logs into a support request. |

Support requires a named, expiring, revision/scoped customer grant and fresh administrator MFA. Help messages grant no document access. Record action/time and sanitized error code, tell the customer the concrete observed effect, and distinguish a recorded manual refund from an actual external transfer. Customer notification, breach timelines and responsible contacts require the chosen jurisdictions/policies before launch; nothing sends external messages automatically.

## Migration and rollback

Upgrade with forward migrations through `0012_operations`. Keep the preceding source/image pins and a verified matched snapshot before upgrading. Repeat upgrades safely; never use SQL downgrade to delete billing evidence. The drill creates a separate prior-schema database, records a fictional paid USD 25.00 invoice and immutable evidence, upgrades from 0011 to 0012, then drops **only that disposable probe database**, restores its 0011 snapshot, verifies exact ledger values and upgrades forward again. Production rollback needs coordinated database/object/vault/identity restoration plus newer deletion/membership/payment reconciliation, not a code checkout alone.

## Observed acceptance and remaining gates

Local checks pass: **128 PostgreSQL/private-storage/API tests**, **315 original converter tests**, strict lint/format/types, OpenAPI 0.6.0 (**150 operations, 160 schemas, seven examples, all 33 feature mappings**), **42 frontend unit tests**, **19 demo browser journeys**, and API build. Parser-abuse, role/tenant/CSRF/MFA, bounded slow-body admission, quota/manual-ledger replay, partial removal and archive-abuse checks remain active.

A real isolated restore verified **352 objects**, identity/application records, one fictional encrypted BYOK key, API evidence-write denial, session/work quarantine, repeat forward migrations and prior-schema rollback. It completed in **15 seconds** on this machine; this is not a hosted recovery-time or recovery-point promise. The expiry drill preserved a valid archive and removed exactly its expired synthetic archive. Private archives, configs, statements, traces and screenshots remain ignored and are never uploaded as CI artifacts.

A local liveness baseline made **100 successful requests at concurrency eight**, p50 **8.22 ms**, p95 **14.63 ms**. This measures only a small public endpoint, not customer metadata, OCR throughput, sustained load, storage write capacity, cost or selected-host limits. The tested worker remains limited to four GiB, two CPUs and 128 processes. The measured OCR description mismatch still requires source review.

Full browser/crash-recovery and pushed-source CI evidence is recorded in `docs/tasks/saas-phase-6.md` as observed. Automated axe/keyboard/phone checks do not replace first-time-user and manual screen-reader review. Production remains blocked by the native findings, independent review, complete license/model review, selected HTTPS host/region and identity setup, monitored capacity/cost targets, verified teardown/recovery/deletion journals, retention/backup policies, merchant eligibility and any enabled real provider/payment/email/import integrations. Main remains unmerged; no public deployment or real customer processing occurred.
