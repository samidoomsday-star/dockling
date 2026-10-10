# Try the real SaaS foundation on your computer

Phases 1–2 provide real sign-in, customer separation, private uploads, queued text/OCR conversion and source-linked results. Review editing/final exports (Phase 3), hosted BYOK/model connections (Phase 4) and billing (Phase 5) remain later phases. Use synthetic information here. No hosting account or LLM key is needed.

## Before starting

Use **Linux x86_64, Python 3.12, Node 24.15+ within version 24, and Docker Engine/Compose v2**. On Windows, use **WSL 2 with Ubuntu 24.04** and Docker Desktop's Linux-container backend; enable Docker Desktop integration for that Ubuntu distribution. Run the commands below in the Ubuntu terminal, with the clone inside its Linux home folder. Your Windows browser can normally open the local service through WSL's localhost forwarding. This Windows/WSL route is documented but has not been tested on a Windows device; the receiving assistant must verify it there. The Phase 2 container copies Linux binary dependencies, so a native Windows virtual environment cannot build it.

Allow roughly **8 GB of Docker memory and 40 GB of available disk** for setup/builds, plus room for your test files. A machine with 16 GB RAM is a useful starting point. These are development allowances, not a production capacity promise. The OCR worker itself is capped at 4 GB RAM, two CPUs and 300 seconds per attempt. Docker's `vfs` driver can use much more temporary build space than ordinary desktop overlay storage. Do not clear data volumes to make room.

Clone `https://github.com/samidoomsday-star/dockling.git`, select **`saas-phase-2`**, and open that folder in your editor. A fresh clone does not contain installed programs, passwords, models or jobs. Ask your receiving assistant to follow this guide and `docs/DEVICE_SETUP.md`.

## Install and start (Linux x86_64 / Python 3.12)

From the repository folder:

```bash
bash scripts/install-saas-linux.sh
```

This installs hash-locked CPU Python/web dependencies and the locked React UI, starts PostgreSQL/Keycloak/private storage, applies migrations and creates two fictional workspaces. Existing matching credentials, memberships and volumes are preserved.

Then build the conversion worker:

```bash
.venv/bin/python scripts/saas-local.py worker-build
```

This rechecks the installation, downloads missing OCR models during setup and verifies their pinned SHA256 hashes, then builds the restricted Linux worker image. Package signatures and TLS remain enabled. It can take several minutes on the first run. The models require roughly 700 MB and no LLM key. Setup also creates a separate roughly 700 MB worker cache containing only manifest-approved public artifacts, readable by the container's fixed user even when your host uses a different user number. Your original model-cache permissions and private setup files are preserved. The worker cache is mounted read-only rather than downloaded during processing.

Then start that worker:

```bash
.venv/bin/python scripts/saas-local.py worker
```

Then start the website/API:

```bash
.venv/bin/python scripts/saas-local.py run
```

Keep this last terminal open. **On the same computer**, open `http://127.0.0.1:8000` and click **Sign in securely**. This is your device's address; it is not a remote link into this cloud task. The API and website use one origin. No `.bat` launcher is needed for the SaaS app.

## Signing in and trying the screens

Open the ignored **`.local-saas/bootstrap.json`** file in your editor. Under `users`, find `owner-a` and its generated `password`; use those to sign in. Do not upload or share that file. It contains local test credentials. `owner-a`, `editor-a` and `viewer-a` belong to Sample workspace A. Their `-b` counterparts belong to B. The `operator` account has service-health access after a real OTP sign-in and has no customer membership. Normal UI testing uses `owner-a`; an assistant can test the synthetic operator with `scripts/saas-browser.mjs`.

1. Create a job with a name and three-letter currency. **Conversion options** lets you choose text/Docling/automatic engines, a published layout, date order, page groups and ordered-image combination. The job is saved in PostgreSQL.
2. Generate fictional samples with `.venv/bin/python scripts/saas-fixtures.py`. Select `.local-saas/browser-fixtures/text.pdf` in the job, confirm the fictional-data checkbox, and click **Upload files → Inspect documents → Convert statements**. Compare the two extracted rows with **View source**. Try `scan.pdf`, `photo.png` and `encrypted.pdf` in separate jobs. The protected sample password is `fictional-browser-password` (only for this deliberately fictional fixture).
3. The worker shows actual queued/running stages and completed-page counts; no invented percentage. A password prompt uses memory once, expires after five minutes and is not persisted. A server restart/claim crash can require re-entry. You can cancel or retry a failed operation. Inputs are limited to 8 MB/file, 12 files and 40 pages/job by default; workspace storage/queue limits also apply. Financial verdicts do not certify dates/descriptions. Results stay **needs review** and read-only until Phase 3 editing/source checks/exports are implemented.
4. Open **Team** as an owner. Change editor/viewer permissions, or create an invitation link for another synthetic verified account (for example `owner-b@example.test`). No email is sent. A link expires after two days. The receiving user signs in first and reopens the link to accept it.
5. Use a separate browser/private window to sign in as `owner-b`; A's jobs must not appear. A viewer can read jobs and cannot create them.
6. Stop/restart the server and services; saved jobs stay. The last active owner cannot be removed. BYOK and preferences editing are not active yet.

The older interactive feature demo is still available with `npm run dev --prefix frontend` in its **explicit demo mode**. It uses fictional data and does not sign in or process files. `npm run build` creates that demo; `npm run build:api` creates the real foundation UI. The Python server refuses to serve a demo build as its real UI. Rebuild with `build:api` after running demo build checks, then restart the server.

## Stop, resume and update

Stop the Python server with **Ctrl+C**. In another terminal, use the relevant Python interpreter above with:

```bash
.venv/bin/python scripts/saas-local.py down
```

This stops the containers and keeps their volumes and local credentials. To resume, run `scripts/saas-local.py setup`, `scripts/saas-local.py worker` and then `scripts/saas-local.py run` with the same interpreter. Setup is repeatable and preserves existing records and roles. Do not use `docker compose down -v` unless you deliberately intend to erase this development database and storage.

Before updating, commit or stash your own code changes, stop the server, pull your chosen branch, reinstall its pinned dependencies and rebuild its API frontend. Run setup to apply migrations, rebuild the worker after code/dependency changes, then start the worker and server. Your original CLI configuration and `workspace/orders` are separate; SaaS setup does not alter them.

If a PostgreSQL volume exists but `.local-saas/bootstrap.json` is missing, setup stops. Restore the matching credentials backup. Replacing passwords while keeping an old database will not recover it.

## Backups and recovery

Back up **both** Docker volumes (`dockling-saas_saas-postgres` and `dockling-saas_saas-storage`) plus `.local-saas/`, with services stopped for a consistent local snapshot. Treat the archive as private, keep it outside Git, and protect/encrypt it. Restore those matching pieces together with the same image digests and migrate forward. See Docker's [volume backup/restore guide](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes). Keycloak's identity database is in the PostgreSQL volume; a CLI job backup does not back up SaaS jobs.

Before future schema upgrades, retain a tested backup and the preceding code version. The first migration's downgrade drops SaaS tables; Phase 2 downgrades stop and require a matching backup instead of weakening tenant/lease constraints. Use forward migrations for ordinary updates. These upgrades preserve Phase 1 job metadata. Keep code/schema backups together. Production backup/restore drills and secrets rotation are later release gates.

## Verification for a receiving assistant

After setup, run `.venv/bin/python -m pytest tests_saas -q` against the dedicated **dockling_test** database. These tests clear only that synthetic test database and use a separate `-test` object bucket. Never run them against the main bucket/database. It is created during fresh setup. Never point it at a customer database. Run `npm run check --prefix frontend` for demo regression checks, then `npm run build:api --prefix frontend`. Install Chromium with `npm exec --prefix frontend -- playwright install chromium`, generate fixtures, start the API **and worker**, and run `node scripts/saas-browser.mjs` for real login, upload/text/OCR/image/protected-PDF results, source pages, A/B isolation, viewer restrictions, mobile accessibility and actual OTP admin. Run `.venv/bin/python scripts/check-worker-isolation.py` to verify actual public TCP/DNS denial, read-only mounts, CPU/RAM/process limits and restricted SQL permissions. Run `node scripts/saas-recovery.mjs` separately for an actual worker SIGKILL/lease reclaim; it restarts only this synthetic worker and waits up to about two minutes. Tests must not share OTP/browser report writers concurrently. This script waits for a fresh authenticator code; do not run it concurrently against the same operator. Its screenshots and credentials remain ignored.

Failures must be reported as failures. Do not substitute demo fixtures, bypass authentication, publish test credentials or claim the Windows path/GitHub workflow passed unless actually run. Model downloads and the original 314-test CLI gate follow the separate device instructions.

## Abandoned staging-object cleanup

Run `.venv/bin/python scripts/saas-local.py reap` for a bounded maintenance pass. It deletes only abandoned opaque pipeline/upload objects older than one hour, preserves all active/original/referenced objects and live attempts, and frees their staged inventory quota. Repeat passes to cover a large bucket; the private continuation checkpoint is retained. A storage/database failure reports an incomplete pass and can be retried. This is **not** customer close/retention/deletion certification; those workflows and backup expiry belong to later release phases.

## Hosting later

This Compose file is a loopback-only **local development** setup. Keycloak runs in development mode; its S3 volume size and count are deliberately small. It is not a public SaaS deployment. Production needs HTTPS, a chosen identity service with MFA, PostgreSQL with verified TLS/backups, durable private S3-compatible storage, an isolated OCR worker, domain/routing, quotas, monitoring and the release gates in `docs/PRODUCTION-SAAS-PLAN.md`. Customer region and business country are still undecided. Free tiers have limits, particularly for OCR memory and persistent storage; those must be measured before selecting staging hosting.
