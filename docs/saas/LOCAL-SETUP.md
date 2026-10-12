# Set up and test the current Dockling web app

**Current branch: `saas-phase-7`, including Phase 8 worker security fixes. Updated 12 October 2026.** Windows owners can start with [the beginner walkthrough](WINDOWS-TESTING.md), including its receiving-assistant prompt. This is the full Linux/WSL recipe for the actual app. Historical phase notes explain features without requiring switches to older branches.

Phases 1–7 provide real sign-in, customer separation, private uploads, queued text/OCR conversion, source review/corrections, six outputs, live removal, optional encrypted BYOK/model connections, owner tools, account/usage limits and manual invoice records. Phase 7 adds a separate HTTPS staging rehearsal, verified service TLS, paused staging inference and private field/import/cost validation; read `PHASE7-STAGING.md`. Online payments, external email, customer use and public deployment remain gated. Use synthetic information here. No hosting account or LLM key is needed.

## Before starting

Use **Linux x86_64, Python 3.12, Node 24.15+ within version 24, and Docker Engine/Compose v2**. On Windows, use **WSL 2 with Ubuntu 24.04** and Docker Desktop's Linux-container backend; enable Docker Desktop integration for that Ubuntu distribution. Run the commands below in the Ubuntu terminal, with the clone inside its Linux home folder. Your Windows browser can normally open the local service through WSL's localhost forwarding. This Windows/WSL route is documented but has not been tested on a Windows device; the receiving assistant must verify it there. The Phase 2 container copies Linux binary dependencies, so a native Windows virtual environment cannot build it.

Allow roughly **8 GB of Docker memory and 40 GB of available disk** for setup/builds, plus room for your test files. A machine with 16 GB RAM is a useful starting point. These are development allowances, not a production capacity promise. The OCR worker itself is capped at 4 GB RAM, two CPUs and 300 seconds per attempt. Docker's `vfs` driver can use much more temporary build space than ordinary desktop overlay storage. Do not clear data volumes to make room.

Clone `https://github.com/samidoomsday-star/dockling.git`, select **`saas-phase-7`**, and open that folder in your editor. A fresh clone does not contain installed programs, passwords, models or jobs. Ask your receiving assistant to follow this guide and `docs/DEVICE_SETUP.md`.

## Check prerequisites before installation

Use Git and native Linux libraries as well as the tools above. Ubuntu 24.04 packages include `python3-venv`, `libgl1`, `libgomp1` and `libglib2.0-0t64`; see WINDOWS-TESTING.md for prerequisite installation. Install Node inside Linux/WSL, not just Windows. Use a verified official Node 24 installation matching `frontend/.node-version` (currently 24.19.0); distro-default Node may be too old.

Run these separately in the Linux terminal:

```bash
python3 -c 'import platform,sys; print(sys.version,platform.machine()); assert sys.platform=="linux" and sys.version_info[:2]==(3,12) and platform.machine()=="x86_64"'
```

```bash
node -e 'console.log(process.version); if(+process.versions.node.split(".")[0]!==24 || +process.versions.node.split(".")[1]<15)throw Error("Node 24.15+ within 24 required")'
```

```bash
npm --version
```

```bash
docker info
```

```bash
docker compose version
```

Fix a failed prerequisite before installing. On Windows, verify Docker Desktop's Ubuntu integration and keep the clone in the Linux filesystem; a Windows virtual environment cannot supply Linux binary wheels. Do not dump environment variables or credential files into logs.

For a fresh clone (inspect existing folders before reusing them):

```bash
git clone --branch saas-phase-7 https://github.com/samidoomsday-star/dockling.git
```

```bash
cd dockling
```

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

This rechecks the installation, downloads missing OCR models during setup and verifies their pinned SHA256 hashes, then builds the digest-pinned Ubuntu 24.04 worker with vendor-maintained Python 3.12. The Dockerfile supplies the worker interpreter; you do not install its exact downstream patch version separately. Package signatures and TLS remain enabled. It can take several minutes on the first run. The models require roughly 700 MB and no LLM key. Setup also creates a separate roughly 700 MB worker cache containing only manifest-approved public artifacts, readable by the container's fixed user even when your host uses a different user number. Your original model-cache permissions and private setup files are preserved. The worker cache is mounted read-only rather than downloaded during processing.

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

Open the ignored **`.local-saas/bootstrap.json`** file in your editor. Under `users`, find `owner-a` and its generated `password`; use those to sign in. Do not upload or share that file. It contains local test credentials. `owner-a`, `editor-a` and `viewer-a` belong to Sample workspace A. Their `-b` counterparts belong to B. The `operator` account has service-health access after a real OTP sign-in and has no customer membership. Normal UI testing uses `owner-a`. If verification workspaces also appear, choose **Sample workspace A** in the **Workspace** dropdown for your own walkthrough; an assistant can test the synthetic operator with `scripts/saas-browser.mjs`.

1. Create a job with a name and three-letter currency. **Conversion options** lets you choose text/Docling/automatic engines, a published layout, date order, page groups and ordered-image combination. The job is saved in PostgreSQL.
2. Generate fictional samples with `.venv/bin/python scripts/saas-fixtures.py`. Select `.local-saas/browser-fixtures/text.pdf` in the job, confirm the fictional-data checkbox, and click **Upload files → Inspect documents → Convert statements**. Compare the two extracted rows with **View source**. Try `scan.pdf`, `photo.png` and `encrypted.pdf` in separate jobs. The protected sample password is `fictional-browser-password` (only for this deliberately fictional fixture).
3. The worker shows actual queued/running stages and completed-page counts; no invented percentage. A password prompt uses memory once, expires after five minutes and is not persisted. A server restart/claim crash can require re-entry. You can cancel or retry a failed operation. Inputs are limited to 8 MB/file, 12 files and 40 pages/job by default; workspace storage/queue limits also apply. Financial verdicts do not certify dates/descriptions. Results stay **needs review** until you complete the Phase 3 corrections/source-check workflow described below.
4. Open **Team** as an owner. Change editor/viewer permissions, or ask the assistant to create a new fictional verification account using `scripts/saas-local.py verification-account` and invite that account. Keep `owner-b` uninvited so it remains the separate-workspace privacy baseline below. No email is sent. A link expires after two days. The receiving user signs in first and reopens the link to accept it; an accepted invitation deliberately grants the chosen workspace membership.
5. Use a separate browser/private window to sign in as `owner-b`; A's jobs must not appear. A viewer can read jobs and cannot create them.
6. Stop/restart the server and services; saved jobs stay. The last active owner cannot be removed. Optional BYOK connections, consent-bound AI assistance and owner preferences are implemented; inference needs explicit permission and suitable provider terms. Staging pauses requests by default. Synthetic fake-provider acceptance sends no paid requests.

The older interactive feature demo is still available with `npm run dev --prefix frontend` in its **explicit demo mode**. It uses fictional data and does not sign in or process files. `npm run build` creates that demo; `npm run build:api` creates the real app UI. The Python server refuses to serve a demo build as its real UI. Rebuild with `build:api` after running demo build checks, then restart the server.

## Stop, resume and update

Stop the Python server with **Ctrl+C**. In another terminal, use the relevant Python interpreter above with:

```bash
.venv/bin/python scripts/saas-local.py down
```

This stops containers and keeps volumes/credentials. Start Docker again if needed, enter the repository, then resume with these commands separately:

```bash
.venv/bin/python scripts/saas-local.py setup
```

```bash
.venv/bin/python scripts/saas-local.py worker
```

```bash
.venv/bin/python scripts/saas-local.py run
```

Keep the last terminal open. Setup is repeatable and preserves existing records and roles. Do not use `docker compose down -v` unless you deliberately intend to erase this development database and storage.

Before updating, preserve a matched private backup, inspect `git status --short`, and commit/stash your own code changes. Stop the API with Ctrl+C and stop services with `scripts/saas-local.py down` before changing dependencies or performing backup. On `saas-phase-7`, use `git pull --ff-only`; do not switch/reset branches over local work. Then repeat `install-saas-linux.sh`, `worker-build`, `worker` and `run` above sequentially. The installer builds the API frontend and setup applies forward migrations. Rescan the rebuilt worker. For documentation-only changes, dependencies/images need no rebuild; inspect the actual diff before deciding. Preserve all local keys, credentials and volumes. Your original CLI configuration and `workspace/orders` are separate; SaaS setup does not alter them.

If a PostgreSQL volume exists but `.local-saas/bootstrap.json` is missing, setup stops. Restore the matching credentials backup. Replacing passwords while keeping an old database will not recover it.

## Backups and recovery

Phase 6 provides an authenticated encrypted local backup/isolated restore drill; follow [PHASE6-OPERATIONS.md](PHASE6-OPERATIONS.md) with API, worker and identity writers quiesced. Preserve its independent backup key as well as matched vault/identity/database/storage material. The tool restores into disposable drill resources, not over an active stack, and is not a public-host backup procedure. Receiving assistants should use that tested protocol rather than invent a live restore. The underlying volume/private-file recovery requirements below remain applicable.

Back up **both** Docker volumes (`dockling-saas_saas-postgres` and `dockling-saas_saas-storage`) plus `.local-saas/`, with services stopped for a consistent local snapshot. Treat the archive as private, keep it outside Git, and protect/encrypt it. Restore those matching pieces together with the same image digests and migrate forward. See Docker's [volume backup/restore guide](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes). Keycloak's identity database is in the PostgreSQL volume; a CLI job backup does not back up SaaS jobs.

Before future schema upgrades, retain a tested backup and the preceding code version. The first migration's downgrade drops SaaS tables; Phase 2 downgrades stop and require a matching backup instead of weakening tenant/lease constraints. Use forward migrations for ordinary updates. These upgrades preserve Phase 1 job metadata. Keep code/schema backups together. Production backup/restore drills and secrets rotation are later release gates.

## Verification for a receiving assistant

Run checks **sequentially**, without competing install/build/browser/OTP/backup writers. Latest Linux/GitHub evidence is 164 SaaS tests, 318 converter tests, 42 frontend units/19 demo journeys, real ordinary/HTTPS browser checks and the exact worker's zero-high/critical advisory gate. This is prior evidence, not a promised receiving-device count or result. Windows/WSL remains unverified until observed there.

1. After setup, run `.venv/bin/python -m pytest tests_saas -q`. Its dedicated **dockling_test** database and separate `-test` object bucket are disposable test resources. Never point it at a customer database or the ordinary main bucket. Run the original converter gate separately with `.venv/bin/python scripts/check.py`; do not combine `tests` and `tests_saas` in one pytest invocation because their conftest fixtures conflict. `.venv/bin/python -m stmtconv doctor` and selftest check offline model setup.
2. Install Chromium with `npm exec --prefix frontend -- playwright install chromium` (Linux system libraries may also be required; `--with-deps` only when OS installation is permitted). Run `npm run check --prefix frontend` for the separate demo gate, then **`npm run build:api --prefix frontend`** to restore the actual app build. Running npm check leaves a demo bundle, which the API refuses. Restart the ordinary API afterward if it had been running.
3. Generate fixtures with `.venv/bin/python scripts/saas-fixtures.py`, start worker and ordinary API, then run `node scripts/saas-browser.mjs --phase3 --phase4 --phase4-owner --phase5 --phase6`. This exercises actual sign-in, text/OCR/image/protected/combined files, corrections/source checks, six outputs/delivery/removal, encrypted fictional connection setup, owner/account/manual-billing/operations screens, role/workspace isolation, MFA and mobile checks. It makes no paid AI requests. Operator OTP/browser writers must not run concurrently; credentials/screenshots remain ignored. Browser installation and fixtures are prerequisites, not outcomes to assume.
4. Run `.venv/bin/python scripts/check-worker-isolation.py` against the running worker, then `.venv/bin/python scripts/check-worker-security.py` against its built image. The strict scan preserves unfixed findings and requires exact image/OS/Python coverage; missing evidence is a failure. A previously clean image or report-only CI does not clear a newly built image. See [the remediation guide](PHASE8-SECURITY-REMEDIATION.md).
5. If deeper recovery verification is part of the device handoff, run `node scripts/saas-recovery.mjs` separately with the ordinary API/worker for actual synthetic SIGKILL/reclaim, then the quiesced encrypted backup/isolated restore/expiry procedure in PHASE6-OPERATIONS.md. Never interrupt customer jobs or run backups with writers active. Optional HTTPS and fake-AI journeys use their own guides below. Stop their harnesses and restore ordinary API/worker readiness afterward.

Finally, check `/api/v1/health/live`, `/api/v1/health/ready` and `/api/v1/version` locally for actual HTTP 200 responses, explain any failures, and leave the ordinary API-mode website ready for the owner. Give exact local start/stop commands and private login retrieval instructions. These availability checks do not certify security, OCR accuracy or production capacity.

Each browser or recovery run provisions a new fictional verification workspace for the existing A test accounts using the local setup helper, then uses genuine sign-in and the authorized workspace-switch API. Original workspaces, jobs and quotas are preserved. This allows repeat checks without hitting the original workspace's 30-operations/hour test limit. These workspaces remain local test data; the helper refuses production mode. B accounts and the operator receive no membership in them.

Failures must be reported as failures. Do not substitute demo fixtures, bypass authentication, publish test credentials or claim the Windows path/GitHub workflow passed unless actually run. Model downloads and the separate original converter gate follow the separate device instructions.

## Abandoned staging-object cleanup

Run `.venv/bin/python scripts/saas-local.py reap` for a bounded maintenance pass. It deletes only abandoned opaque pipeline/upload objects older than one hour, preserves all active/original/referenced objects and live attempts, and frees their staged inventory quota. Repeat passes to cover a large bucket; the private continuation checkpoint is retained. A storage/database failure reports an incomplete pass and can be retried. This sweeper is separate from Phase 3 owner close/abandon and its verified live-removal certificate. Authenticated local expiry verification is implemented in Phase 6; an actual host's backup retention/expiry policy still needs configuration and observation.

## Hosting later

This Compose file is a loopback-only **local development** setup. Keycloak runs in development mode; its S3 volume size and count are deliberately small. It is not a public SaaS deployment. Production needs HTTPS, a chosen identity service with MFA, PostgreSQL with verified TLS/backups, durable private S3-compatible storage, an isolated OCR worker, domain/routing, quotas, monitoring and the release gates in `docs/PRODUCTION-SAAS-PLAN.md`. Customer region and business country are still undecided. Free tiers have limits, particularly for OCR memory and persistent storage; those must be measured before selecting staging hosting.


## Phase 3 review and downloads

Use [the Phase 3 guide](PHASE3-IMPLEMENTATION.md) after conversion. Run the real browser verification with `node scripts/saas-browser.mjs --phase3`; it exercises corrections, six formats, delivery and live removal as well as genuine OCR inputs. Keep the API-mode build while running this journey; run demo builds/journeys separately, then rebuild with `npm run build:api --prefix frontend`. Preserve all credentials and volumes when updating; run setup for forward migrations and worker-build/worker for the new image.


## Phase 4 connection setup

On the current `saas-phase-7` branch, setup applies all forward migrations, including connections, and preserves/creates the dedicated ignored `.local-saas/ai-key.env`. Restart the API after upgrading. Keep this key file with the matching private database backup; never regenerate it for existing encrypted credentials. Read [the connection guide](PHASE4-CONNECTIONS.md). The real browser check is `node scripts/saas-browser.mjs --phase3 --phase4`; it saves/revokes fictional keys without contacting a provider. Per-job consent, reserved AI correction requests and owner tools are implemented; read [the complete Phase 4 guide](PHASE4-IMPLEMENTATION.md). Real provider inference is separately authorized; use the explicit fake-AI harness for synthetic browser tests. Optional keys are never prerequisites for offline conversion.


## Phase 4 upgrade and owner testing

Read [PHASE4-IMPLEMENTATION.md](PHASE4-IMPLEMENTATION.md). Run setup for all current forward migrations (`0010_owner_tools` is an earlier milestone, not the current stopping point); rebuild/restart the worker and API frontend, then restart the API. The gateway starts with the API; use one Linux API process. Do not reset database/storage volumes or regenerate the vault key. Production interrupted AI runs withhold cleanup acknowledgement pending verified process teardown recovery in the deployment phase.

`--phase4-owner` adds real preference, private scaffold, expiring support, versioned configuration, isolated nine-case selftest and worker-health UI checks. `--phase4-ai` requires `scripts/saas-fake-ai-server.py` instead of the ordinary API; it makes only fictional model requests. Run OTP browser and crash-recovery checks sequentially. Stop the harness afterward and leave the ordinary API ready. Advanced shared profile activation requires an exact passing synthetic test plus a separate confirmation that no private customer fingerprints are being published.


## Phase 6 operating and recovery upgrade

Use `saas-phase-7`, which contains Phases 1–7 plus Phase 8 worker security fixes and pilot preparation. Read [PHASE6-OPERATIONS.md](PHASE6-OPERATIONS.md). Preserve credentials/volumes, run setup for all forward migrations (`0012_operations` is the operations milestone), rebuild/start the worker and API build, and restart the ordinary API. The admin Operations and recovery panel requires fresh MFA. The independently encrypted backup utility requires quiesced writers and never overwrites active resources. Its new backup key is not the vault key.

Full fictional AI/account/operations verification uses the explicit fake-AI server plus `node scripts/saas-browser.mjs --phase3 --phase4 --phase4-ai --phase4-owner --phase5 --phase6`. Ordinary-server testing omits `--phase4-ai`. Run the strict native scan separately against each new image. The latest verified Ubuntu image passes with zero high/critical findings and populated OS/Python coverage; older Phase 6/7 blocked Debian reports are historical. New findings or missing coverage still block the gate. No suppression is used. Independent review, other-service scans, model/license terms, selected-host/field/import/cost tests and the external pilot remain pending.
