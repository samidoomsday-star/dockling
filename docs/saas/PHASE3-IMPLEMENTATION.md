# Phase 3: review, outputs and live removal

This is the real local SaaS app, using PostgreSQL, private object storage and the restricted Linux worker. Use fictional documents only. It retains the Python CLI; hosted jobs never wrap CLI subprocesses or maintain a second authoritative `order.json`.

## Customer workflow

Open a converted job. Use **Correct** beside a transaction to fix fields, delete a row or add a missing row. Money stays exact text; blank amounts clear evidence rather than becoming zero. A complete batch is checked before anything is saved. Saving requires fresh source comparison and revokes earlier downloads. An open draft retains its original revision and rejects a conflicting save.

Compare every required row under **Compare with the source**. The deterministic sample includes all corrected rows. Confirm the comparison only after reading dates, descriptions and amounts on the actual source. Financial reconciliation alone does not establish source accuracy. AI rows have a separate all-row acknowledgement; hosted AI processing belongs to Phase 4.

Choose formats under **Prepare your downloads**, then save options. QuickBooks/Xero require an allowed import date format; CSV always uses ISO. OFX requires a known private account identity or explicit account confirmation. Grouping cannot override known conflicting identities. Monthly merging also requires matching currency/direction and continuous periods. Category rules match in order; job overrides precede workspace defaults. Literal matching and a limited regex subset are supported; repeated/grouped regex is rejected.

Generate real Excel, CSV, QuickBooks 3/4-column, Xero and OFX files. QuickBooks splits at the existing configured row limit. Workbook dates/money are real Excel cells. A delivery ZIP contains the complete verified current output set and truthful verification/data-handling notes, excluding originals. Availability/download does not imply email dispatch, client receipt or a successful accounting-software import.

Under Advanced, generate Excel review workbooks. Edit only Fix columns and Action (`fix`, `delete`, `insert_after`); use `clear` to remove evidence. Upload the edited workbook beside its matching download. Workspace/job/revision/statement digests must match. Formula/external/macro content and oversized expanded ZIP contents are rejected. The same pure commands serve the browser and Excel adapters, including the original CLI.

## Privacy and durable work

Owners can remove a delivered job, or explicitly abandon an unfinished one. Downloads/rows/source reads stop when cleanup is requested. Pending cleanup waits for parser scratch receipts; partial cleanup retains inventory and issues no certificate. Retry continues removal and verifies object versions and private database rows are gone. The certificate covers verified **live** removal, not backup expiry, customer-downloaded copies or a legal/compliance guarantee. Backup policy and automatic hosted retention are undecided.

The supported recovery topology is one worker container with its own PID namespace and a held PostgreSQL advisory lock. Parser cleanup receipts survive API restarts; container restart clears leftover scratch before acknowledgement. Host-launched workers cannot certify orphan scratch recovery. Multi-worker recovery remains a production hardening/scale gate. Leases, revision/generation/role/deletion fences still prevent old attempts from publishing.

Future uploads have a job-scoped opaque prefix so a failed database commit still leaves discoverable cleanup inventory. Legacy Phase 2 uploads are located by their recorded artifact keys; attempt prefixes cover unpublished worker objects. Pre-Phase-3 unreferenced legacy upload objects cannot be attributed to a job and remain the conservative sweeper's responsibility. No certificate promises recovery of an unknown historical object outside the inventoried job scope.

Local maintenance is opt-in, not a hosted retention promise:

```bash
.venv/bin/python scripts/saas-local.py retention --retention-days 7
```

This first reports eligible delivered jobs. Add `--apply-retention` only when intentionally scheduling their permanent cleanup. Certificates remain pending until the worker verifies removal. Credentials, volumes and unrelated jobs are preserved.

## API and limits

Current routes are marked `x-implementation: implemented` in OpenAPI; historical planned spellings are retained as design references. Main implemented routes: `PATCH /jobs/{job}/review`, `/checks`, `/recheck`, `/review-history`, `/spotcheck`, `/ai-source`, `/output-options`, `/account-group`, `/merge-preview`, `/categories`, `/review-workbooks`, `/review-workbooks/{artifact}/apply`, `/exports`, `/delivery`, `/artifacts/{artifact}/download`, `/privacy` and `/close`. Workbook apply sends raw bytes with expected-revision/CSRF/idempotency headers. Every read/write is workspace-scoped and role-checked.

Existing intake limits still apply. Each generated artifact is at most 8 MiB, aggregate parser output files at most 20 MiB and a manifest at most 100 files. Large cases fail without partially publishing a set. Customer financial/source bypasses are unavailable. Production limits, support exceptions and hosting must be reviewed through the later gates.

## Verification

See `docs/tasks/saas-phase-3.md` for the final evidence. Real PG/S3 tests cover browser/Excel commands, exact provenance, stale/foreign/role denial, all six writers and ZIP hashes, tampering, source invalidation, categories and partial deletion/retry. Real browser checks use Keycloak login, genuine uploaded PDF/OCR/image/protected/combined files and the actual restricted worker. Demo journeys are separate checks, never proof of hosted processing.
