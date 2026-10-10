# Try the real SaaS foundation on your computer

This is Phase 1: real sign-in, customer separation, saved job records, invitations and permissions. Upload/conversion (Phase 2), review/export (Phase 3), hosted BYOK/model connections (Phase 4) and billing (Phase 5) are still being connected. Use synthetic information here. No hosting account or LLM key is needed.

## Before starting

Install Git, **Python 3.12**, **Node 24.15 or newer within version 24**, and **Docker Desktop with Compose v2**. Open Docker Desktop and wait until its engine is running. On Windows, enable its Linux containers/WSL 2 backend; reboot if Docker asks. Allow roughly 8 GB of memory and 10 GB of disk for this development setup; OCR tests need additional model space. Those are development allowances, not measured production capacity.

Clone `https://github.com/samidoomsday-star/dockling.git`, select the `saas-phase-1` branch, and open that folder in Kilo Code or another editor. A fresh clone does not contain installed programs, passwords or your jobs. Ask the receiving assistant to follow this guide and `docs/DEVICE_SETUP.md`.

## Linux x86_64 / Python 3.12 (tested in the cloud)

From the repository folder, run:

```bash
bash scripts/install-saas-linux.sh
```

This installs the locked Python dependencies and React UI, starts PostgreSQL, Keycloak and private SeaweedFS storage, creates the schema and creates two fictional workspaces. It does not download OCR models. Expect `Identity, PostgreSQL and authenticated private storage are ready` and `Two synthetic workspaces ... are ready`.

Then run:

```bash
.venv/bin/python scripts/saas-local.py run
```

Keep this terminal open. **On this same computer**, open `http://127.0.0.1:8000` in a browser and click **Sign in securely**. This address belongs to the machine running the command; it is not a link to the cloud session from another device.

## Windows PowerShell (instructions provided; not yet tested on Windows)

First complete the Python device setup in `docs/ENVIRONMENT.md` to create `.venv` with the CPU dependencies. Do not run `.bat` files to open the web UI. From PowerShell in the repository folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,web]"
```

Then:

```powershell
npm ci --prefix frontend
```

Then:

```powershell
npm run build:api --prefix frontend
```

Then:

```powershell
.\.venv\Scripts\python.exe scripts/saas-local.py setup
```

Then:

```powershell
.\.venv\Scripts\python.exe scripts/saas-local.py run
```

Open `http://127.0.0.1:8000` on your Windows PC. The Linux SHA256 wheel lock is not a Windows/ARM lock; the Windows recipe uses reviewed exact top-level extras, and its resolved binaries still need device verification. WSL Ubuntu with Python 3.12 on x86_64 can use the tested Linux recipe.

## Signing in and trying the screens

Open the ignored **`.local-saas/bootstrap.json`** file in your editor. Under `users`, find `owner-a` and its generated `password`; use those to sign in. Do not upload or share that file. It contains local test credentials. `owner-a`, `editor-a` and `viewer-a` belong to Sample workspace A. Their `-b` counterparts belong to B. The `operator` account has service-health access after a real OTP sign-in and has no customer membership. Normal UI testing uses `owner-a`; an assistant can test the synthetic operator with `scripts/saas-browser.mjs`.

1. Create a job with a name and three-letter currency. Open it again; the record is stored in PostgreSQL.
2. Open **Team** as an owner. Change editor/viewer permissions, or create an invitation link for another synthetic verified account (for example `owner-b@example.test`). No email is sent. A link expires after two days. The receiving user signs in first and reopens the link to accept it.
3. Use a separate browser/private window to sign in as `owner-b`; A's jobs must not appear. A viewer can read jobs and cannot create them.
4. Stop/restart the server and services; saved jobs stay. The last active owner cannot be removed. BYOK and preferences editing are not active yet.

The older interactive feature demo is still available with `npm run dev --prefix frontend` in its **explicit demo mode**. It uses fictional data and does not sign in or process files. `npm run build` creates that demo; `npm run build:api` creates the real foundation UI. The Python server refuses to serve a demo build as its real UI. Rebuild with `build:api` after running demo build checks, then restart the server.

## Stop, resume and update

Stop the Python server with **Ctrl+C**. In another terminal, use the relevant Python interpreter above with:

```bash
.venv/bin/python scripts/saas-local.py down
```

This stops the containers and keeps their volumes and local credentials. To resume, run `scripts/saas-local.py setup` and then `scripts/saas-local.py run` with the same interpreter. Setup is repeatable and preserves existing records and roles. Do not use `docker compose down -v` unless you deliberately intend to erase this development database and storage.

Before updating, commit or stash your own code changes, stop the server, pull your chosen branch, reinstall its pinned dependencies and rebuild its API frontend. Run setup to apply migrations, then run the server. Your original CLI configuration and `workspace/orders` are separate; SaaS setup does not alter them.

If a PostgreSQL volume exists but `.local-saas/bootstrap.json` is missing, setup stops. Restore the matching credentials backup. Replacing passwords while keeping an old database will not recover it.

## Backups and recovery

Back up **both** Docker volumes (`dockling-saas_saas-postgres` and `dockling-saas_saas-storage`) plus `.local-saas/`, with services stopped for a consistent local snapshot. Treat the archive as private, keep it outside Git, and protect/encrypt it. Restore those matching pieces together with the same image digests and migrate forward. See Docker's [volume backup/restore guide](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes). Keycloak's identity database is in the PostgreSQL volume; a CLI job backup does not back up SaaS jobs.

Before future schema upgrades, retain a tested backup and the preceding code version. This first migration's downgrade drops its SaaS tables and is destructive; never use it for normal updates. Later migrations must preserve data and document compatibility. Production backup/restore drills and secrets rotation are later release gates.

## Verification for a receiving assistant

After setup, run `.venv/bin/python -m pytest tests_saas -q` against the dedicated **dockling_test** database. These tests clear only that synthetic test database. It is created during fresh setup. Never point it at a customer database. Run `npm run check --prefix frontend` for demo regression checks, then `npm run build:api --prefix frontend`. Install Chromium with `npm exec --prefix frontend -- playwright install chromium`, start the API, and run `node scripts/saas-browser.mjs` for real login, cookie/logout, A/B isolation, saved-job UI, mobile accessibility and actual OTP admin. This script waits for a fresh authenticator code; do not run it concurrently against the same operator. Its screenshots and credentials remain ignored.

Failures must be reported as failures. Do not substitute demo fixtures, bypass authentication, publish test credentials or claim the Windows path/GitHub workflow passed unless actually run. Model downloads and the original 314-test CLI gate follow the separate device instructions.

## Hosting later

This Compose file is a loopback-only **local development** setup. Keycloak runs in development mode; its S3 volume size and count are deliberately small. It is not a public SaaS deployment. Production needs HTTPS, a chosen identity service with MFA, PostgreSQL with verified TLS/backups, durable private S3-compatible storage, an isolated OCR worker, domain/routing, quotas, monitoring and the release gates in `docs/PRODUCTION-SAAS-PLAN.md`. Customer region and business country are still undecided. Free tiers have limits, particularly for OCR memory and persistent storage; those must be measured before selecting staging hosting.
