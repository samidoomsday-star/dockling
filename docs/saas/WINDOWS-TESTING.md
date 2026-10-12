# Test the current Dockling web app on Windows

This owner guide covers **`saas-phase-7`**, including the latest Phase 8 worker security fixes, as of **12 October 2026**. Setup has been verified on Linux and GitHub; Windows/WSL still needs verification on your PC. Start with fictional files.

## What you will get

Open Dockling in your Windows browser, sign in, upload a sample statement, convert it, review its source and download results. The database, sign-in service, private storage and document worker run on your PC in the background. Initial testing needs no hosting account, domain, payment account or LLM API key.

The app is available only on that computer. An internet link requires hosted staging separately. GitHub stores application code, not a running website or your private data.

## 1. Prepare your PC

Use an Intel/AMD **64-bit Windows PC** capable of WSL 2 and Docker Desktop. Windows ARM is not the validated target for the Linux x86_64 dependency lock. Allow about **40 GB free disk**, plus job space, and **8 GB memory for Docker**. A PC with 16 GB RAM is a useful starting point. First setup downloads large dependencies and approximately 700 MB of OCR models, then creates a separate approximately 700 MB worker model cache.

1. **Install WSL 2 with Ubuntu 24.04.** In Windows Terminal/PowerShell **as Administrator**:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

   Restart if Windows asks. Open **Ubuntu 24.04** from Start and finish its Linux username/password setup. This is your Ubuntu administration password, not a Dockling login. If WSL already exists, ask your assistant to inspect it rather than replace it.

2. **Install Docker Desktop** using [Docker's official Windows guide](https://docs.docker.com/desktop/setup/install/windows-install/). Use the **WSL 2 / Linux-container backend**. Enable **Settings → Resources → WSL Integration → Ubuntu-24.04 → Apply & restart**. Keep Docker Desktop running. Menu names may vary. WSL memory settings may control Docker's allowance; inspect existing settings before changing them. Check Docker Desktop's applicable license for your business before commercial use.

3. **Connect your coding assistant to Ubuntu.** For VS Code, install Microsoft's **WSL extension**, then use **WSL: Connect to WSL using Distro → Ubuntu-24.04**. Open Kilo Code or another assistant with access to that Linux folder and terminal. A normal browser chat cannot install software on your PC.

Inside Ubuntu, you need **Git, Python 3.12 with venv, Node 24.15+ within version 24, npm and native Linux libraries**. The tested Node version is in `frontend/.node-version` (currently 24.19.0). Your assistant can install/check these. Windows installations of Node/Python do not install them inside Ubuntu. A Windows `.venv` cannot build the real web worker.

If installing Linux prerequisites yourself, run these separately **in Ubuntu**, not PowerShell:

```bash
sudo apt update
```

```bash
sudo apt install -y git python3 python3-venv python3-pip libgl1 libgomp1 libglib2.0-0t64
```

Ubuntu 24.04 supplies Python 3.12. For **Node 24**, follow [the official Node download instructions](https://nodejs.org/en/download) for **Linux**, or let your assistant install verified official artifacts. Ubuntu's default `apt install nodejs` may provide an incompatible version. Do not bypass checksums or TLS to make installation pass.

## 2. Copy this prompt into your local assistant

> Set up the real Dockling web app on this Windows PC from https://github.com/samidoomsday-star/dockling.git, branch `saas-phase-7`, including the Phase 8 worker security fixes. Inspect any existing clone first and preserve its changes/private files. Read AGENTS.md, docs/DEVICE_SETUP.md, docs/saas/WINDOWS-TESTING.md and docs/saas/LOCAL-SETUP.md. Use WSL 2 Ubuntu 24.04, a clone in its Linux home folder, Docker Desktop's Linux backend with WSL integration, Python 3.12, Node 24.15+ within 24 and npm. Verify Docker/Compose, disk/memory and required Linux libraries; Windows Node/Python installations are insufficient. Follow the installer, build the hash-verified Ubuntu worker, start the real API-mode UI and generate fictional test files. Verify actual local sign-in, uploads, text/scanned/image/protected-PDF processing, source review/corrections, exports, workspace/role restrictions, worker isolation and the strict image scan. Run checks sequentially with the dedicated test database; leave the ordinary API-mode app ready afterward. Optional deeper recovery/HTTPS/fake-AI checks follow their specific guides and must not overwrite active data or run concurrently. No LLM key or paid requests are needed for initial testing. Preserve .local-saas/.staging-saas credentials, vault/backup keys and volumes; never upload them. Do not reset data, merge main, deploy publicly, enable checkout or send messages. Explain required owner actions simply. Report actual Windows/WSL results and failures separately from previous Linux/GitHub evidence. Give me the browser address, how to retrieve my generated owner-a login privately, sample-file locations and exact stop/resume commands.

The assistant can complete routine setup. You may need to approve an OS installer, restart Windows, enter your Ubuntu password locally or enable Docker integration. Do not paste passwords/API keys into chat.

## 3. Exact app setup commands

The assistant should follow [LOCAL-SETUP.md](LOCAL-SETUP.md). To do it yourself, run these **one at a time in Ubuntu**, after prerequisites are installed.

For a fresh clone:

```bash
cd ~
```

```bash
git clone --branch saas-phase-7 https://github.com/samidoomsday-star/dockling.git
```

```bash
cd ~/dockling
```

If that folder exists, inspect it with your assistant instead of cloning over it. Keep the clone in Ubuntu's Linux filesystem, not `/mnt/c`, OneDrive or another synced Windows folder. Each fresh clone needs its own dependencies, models and credentials.

Install/build the app and create local services:

```bash
bash scripts/install-saas-linux.sh
```

Build the worker and verify/download its pinned models:

```bash
.venv/bin/python scripts/saas-local.py worker-build
```

Start the worker:

```bash
.venv/bin/python scripts/saas-local.py worker
```

Generate fictional documents:

```bash
.venv/bin/python scripts/saas-fixtures.py
```

Start the website:

```bash
.venv/bin/python scripts/saas-local.py run
```

Keep this terminal open. WSL's local forwarding normally lets the **Windows browser on this same PC** reach the app. Type **`http://127.0.0.1:8000`** into its address bar. This is your PC's address, not a cloud-task link or public staging site. Use the exact host `127.0.0.1`; the local identity callbacks match it. No `.bat` launcher is needed for the real web app.

First setup/build can take several minutes or longer depending on downloads and the PC. If a command fails, stop the sequence and diagnose the failing step before continuing.

## 4. Sign in and test

1. Click **Sign in securely**. Privately open `.local-saas/bootstrap.json` in your editor. Under `users`, find username **`owner-a`** and its generated `password`; enter those in the browser. Do not share/upload the file or print it into an assistant transcript. Choose **Sample workspace A** if a workspace selector appears.
2. Open a second Ubuntu terminal in `~/dockling`. To view the generated sample folder in Windows Explorer:

   ```bash
   explorer.exe "$(wslpath -w "$PWD/.local-saas/browser-fixtures")"
   ```

   This opens only the sample folder. If Windows interoperation is unavailable, use File Explorer's Linux/Ubuntu entry to reach the same folder; your assistant can identify its path.

3. Create a job with currency **USD**, select `text.pdf`, confirm the fictional-data checkbox, then choose **Upload files → Inspect documents → Convert statements**. Expect real queued/running/completed stages and two sample rows.
4. Use **View source** to compare rows with the statement. Try a correction and complete required source checks. Downloads can stay blocked until financial/source/page checks pass; diagnose the reason rather than bypass it.
5. Prepare/download outputs and the delivery ZIP. Some formats need date/account/period options. Test Excel/accounting imports separately; downloading a file does not prove every accounting tool accepts it.
6. Try `scan.pdf`, `photo.png` and `encrypted.pdf` in **separate jobs**. Only the deliberately fictional protected sample uses password **`fictional-browser-password`**. Compare OCR with source: the verified synthetic sweep still has a known raw scan-description mismatch that requires correction.
7. Explore **Team**, **Account and usage**, connection/model settings and owner tools. Manual invoices are records, not online checkout. The separate service operator uses MFA and has no customer membership; ask the assistant to verify that route with the existing harness rather than weaken MFA.
8. In a private browser window, sign in with the generated **`owner-b`** login. Its Sample workspace B must not show A's jobs. A viewer can read but cannot create jobs. Try removal only on a disposable fictional job after checking its outputs.

Basic text/OCR conversion needs no LLM key. Real customer statements and paid AI requests need separate permission/terms and release checks.

## 5. Stop and resume

Press **Ctrl+C** in the website terminal. In another Ubuntu terminal, from the repository:

```bash
.venv/bin/python scripts/saas-local.py down
```

This stops services and preserves data. Do not use `docker compose down -v`; it removes database/storage volumes.

Next time, start Docker Desktop, open Ubuntu and run these separately:

```bash
cd ~/dockling
```

```bash
.venv/bin/python scripts/saas-local.py setup
```

```bash
.venv/bin/python scripts/saas-local.py worker
```

```bash
.venv/bin/python scripts/saas-local.py run
```

Open the same browser address and use your existing login. Setup preserves matching credentials and jobs. Preserve `.local-saas/` with matching database/storage backups; new passwords or encryption keys cannot unlock old data. [LOCAL-SETUP.md](LOCAL-SETUP.md) covers safe updates/backups.

## 6. If something goes wrong

| What you see | What to check with your assistant |
|---|---|
| Docker unavailable | Desktop is running, Linux backend selected, Ubuntu WSL integration enabled |
| Python/Node rejected | Versions inside Ubuntu must be Python 3.12 and Node 24.15+ within 24 |
| Installation/model download fails | Read the failing step; check disk/network without bypassing hashes/TLS |
| Website unavailable | Website terminal running; API health passes inside Ubuntu; WSL forwarding works; port 8000 free |
| Sign-in fails | Identity service on port 8085 reachable; exact 127.0.0.1 host; matching generated credentials |
| Job stays queued | Both API and worker running; worker heartbeat and private broker reachable |
| Downloads blocked | Financial/source checks complete; export options supplied |
| Data exists but credential file is missing | Restore its matched private backup; don't reset data or generate new passwords |

Share relevant error text with secrets removed. Never upload private credentials, keys or raw logs.

## Later: optional AI and hosted testing

For your own AI provider, follow [the connection guide](PHASE4-CONNECTIONS.md) and [consent/owner workflow](PHASE4-IMPLEMENTATION.md). Enter keys privately in the real authenticated connection screen. Custom OpenAI-compatible URL/model entry and effort selection are implemented; **Max appears only when the model's capabilities support it**. Inference requires terms, per-job consent and spending limits. Initial testing and the fictional AI harness make no paid requests; staging pauses inference by default.

For an internet test link, follow [the staging handoff](../../deploy/staging/README.md). Choose hosting/domain/region and provision the API, identity, private database/storage and restricted worker. The optional [local HTTPS rehearsal](PHASE7-STAGING.md) does not create a public server. Independent security/licensing review, selected-host tests and the real pilot remain separate from this walkthrough.
