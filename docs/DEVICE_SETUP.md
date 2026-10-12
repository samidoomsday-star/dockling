# Set up this clone on another device

This receiving-assistant guide covers **`saas-phase-7`**, including Phase 8 worker security fixes (12 October 2026). Windows owners should start with [the beginner walkthrough](saas/WINDOWS-TESTING.md); [LOCAL-SETUP.md](saas/LOCAL-SETUP.md) is the authoritative real-app recipe. Historical phase notes are evidence, not instructions to install older branches. You do not need Kilo Code specifically; any assistant able to read files and run local commands can use it. A chat without filesystem/terminal access can explain the steps but cannot install software for you.

## What the owner should do

For the current SaaS review/download app plus the completed Python work, clone the SaaS branch:

```text
git clone --branch saas-phase-7 https://github.com/samidoomsday-star/dockling.git
```

On Windows, clone inside WSL 2 Ubuntu's Linux home folder and open it through your editor's WSL connection. Do not reuse a Windows `.venv` for the SaaS worker. Give your assistant the primary prompt below.

The primary setup prompt for the real app is:

> Set up the real web app from https://github.com/samidoomsday-star/dockling.git, branch saas-phase-7, including the Phase 8 worker security fixes. Read AGENTS.md, docs/DEVICE_SETUP.md, docs/saas/WINDOWS-TESTING.md when on Windows, and docs/saas/LOCAL-SETUP.md. Inspect existing work first. Use Linux x86_64/Python 3.12/Node 24.15+ within 24/Docker Compose v2; on Windows use WSL 2 Ubuntu 24.04 and Docker Desktop integration, with the clone and tools inside Ubuntu. Follow the SaaS installer, worker-build, worker and run commands. Generate fictional samples and verify actual sign-in, uploads/conversion, source review/corrections, six outputs, role/workspace isolation, owner/account/manual-billing/operations screens, worker restrictions and the strict worker scan. Run checks sequentially on dedicated test resources and report actual device results/failures. Preserve existing keys, credentials, volumes and jobs. No LLM key or paid inference is required. Do not deploy, merge main, enable checkout, send messages or reset data. Leave the ordinary API-mode website running, tell me its address and how to retrieve my generated login privately, then guide me through testing and stop/resume. Run the separate UI demo, fake-AI, HTTPS or recovery drills only when requested or needed for verification; always restore the API build/server afterward. Explain owner actions simply and continue routine setup without asking me about each step.

The assistant may need you to install Git/Python, approve an OS installer, or enter a private key later. Those device permissions and secrets cannot travel through GitHub. Normal statement processing needs no LLM key.

## Optional staging and customer pilot

For the new staging work, also tell the assistant:

> This is the saas-phase-7 branch. Read docs/saas/PHASE7-STAGING.md and deploy/staging/README.md. Set up the ordinary local app first. Optionally run the separate loopback HTTPS rehearsal and its verified TLS/OIDC/isolated-worker/browser checks using fictional documents only. Preserve .local-saas and .staging-saas credentials, vault/backup keys and Docker volumes. Keep staging model requests paused. Read docs/saas/PHASE8-SECURITY-REMEDIATION.md and run the strict scanner against the built worker: its verified Ubuntu runtime has zero high/critical findings; remaining independent review, licensing, selected-host and field gates still precede customer use. Report actual import/device/host tests separately; the cloud rehearsal does not provision a public host. Leave the API-mode UI ready for me to test.

For the subsequent controlled customer pilot, read [the Phase 8 guide](saas/PHASE8-PILOT.md). It includes a separate copyable assistant prompt, the owner choices required before hosting, and the invitation/billing/support/retention procedure. Preparation is available; the external pilot has not launched.

## Instructions for the receiving assistant

### Inspect before installing

1. Read root/scoped AGENTS.md, docs/PROGRESS.md and docs/saas/LOCAL-SETUP.md first for the real web app. ENVIRONMENT.md, OPERATOR_GUIDE.md and BYOK_GUIDE.md cover the separate Python workflow. Historical phase notes are not the current implementation status.
2. Identify OS, architecture, available disk/memory, Git, **Linux Python 3.12**, **Node 24.15+ within 24**, and working Docker/Compose v2. Record branch/commit and `git status --short`. Current branch `saas-phase-7` includes the complete synthetic SaaS features, staging/pilot preparation and Phase 8 worker security fixes. The latest observed worker gate passes; rescan the receiving device's newly built image. Independent review, licensing, selected-host/field acceptance and a real pilot remain production requirements. Earlier branches are historical; `main` remains the starter until a merge is explicitly authorized.
3. Reuse this clone. Preserve tracked changes, `.env`, ignored workspace/model files and private provider settings. Never reset, clean, overwrite settings or switch branches through conflicting local work. If the wrong branch is checked out, explain it and switch only when local work can be preserved safely.
4. Choose a project/workspace outside automatic cloud-sync folders. Do not print environment values or credential files. Check tool availability without dumping secrets. The offline CLI needs no GPU, Docker, Tesseract, LLM account or background server. The SaaS app needs Docker/Compose, the Linux CPU worker/models and a running web server; use its separate setup guide.

### Execute the real web-app setup first

Follow [LOCAL-SETUP.md](saas/LOCAL-SETUP.md), including its prerequisites, sequential verification and restoration of the API-mode build after demo checks. On Windows use [WINDOWS-TESTING.md](saas/WINDOWS-TESTING.md). Native Windows Python instructions below do not apply to the SaaS build. Check actual WSL forwarding, identity callbacks, mounts, broker permissions and Docker build behavior; Linux CI does not establish Windows readiness.

Latest Linux/GitHub evidence is 164 SaaS tests, 318 converter tests and the exact worker's zero-high/critical strict scan. Report fresh observations, not assumed counts/outcomes. PHASE8-SECURITY-REMEDIATION.md supersedes historical blocked Debian findings. Run the browser/worker checks in LOCAL-SETUP.md. Do not run backup, installation or OTP/browser writers concurrently. Deeper recovery follows PHASE6-OPERATIONS.md with quiesced writers and disposable matched restore resources. No private artifacts go into GitHub.

### Optional Python operator workflow

Use the following only if the owner also wants CLI/Excel operation. `run.bat` does not start the website.

- **Windows 10/11:** follow ENVIRONMENT.md section 3 using PowerShell and `.venv\Scripts\python.exe`. Create/reuse a compatible `.venv`, install the pinned CPU torch/torchvision packages, then `.[dev]`, and run pip check. Do not use the Linux hash lock on Windows. Check CPU wheel availability and resolved dependencies on this actual device; Windows is not yet validated by the cloud evidence.
- **Linux:** from the project root run `bash scripts/install-linux.sh`. It uses the tested Python 3.12 CPU hash lock and installs development tools. Call `.venv/bin/python` directly afterward. If Python/venv support is missing, use a supported OS installer/package manager with the device's permissions; report any remaining prerequisite precisely.
- **macOS or another platform:** there is no validated setup recipe. Inspect official Python/PyTorch/Docling compatibility before attempting installation. Do not apply Linux/Windows binary pins blindly or claim platform readiness from cloud results. Finish independent inspection and explain unsupported prerequisites.

Run the explicit `python -m stmtconv models download` with the chosen virtual-environment Python. This setup-only network operation verifies pinned hashes. Allow model hosts/package registries through the device's normal network settings if necessary. Never bypass TLS, hashes or package verification. Do not change dependency/model pins merely to get a pass; diagnose the failure first. If an actual compatibility fix is needed, preserve it as a reviewable change and record its checks.

Defaults work without `.env`. If creating personal overrides, copy `.env.example` only when `.env` does not exist; never overwrite it. Keep `STMTCONV_OFFLINE=true`. GitHub contains the recipes, not the installed environment or private configuration.

### Verify before reporting success

Run these from the project folder, using its virtual-environment Python:

```text
python -m pip check
python -m stmtconv doctor
python scripts/check.py
python -m stmtconv selftest
```

Replace `python` above with `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on Linux. The full quality gate includes real offline model tests. Report failures, warnings and skipped/unrun tests separately; `--quick` alone does not establish full readiness. The latest converter milestone passed 318 tests and nine selftest cases; a later commit may change that count. Doctor's encryption warning means encryption is unverified, not that it is enabled.

Then follow OPERATOR_GUIDE.md's fake-data walkthrough with the actual CLI: `demo`, `order new --platform test --date-order YMD`, copy only the generated PDF into the new job's input folder, `intake`, `extract`, `spotcheck`, `run`, inspect the ZIP, and `close` that synthetic job after checking the results. Use a new empty demo folder when needed. Compare sampled rows to the generated source before confirming the spot-check; do not automatically approve source checks for real documents. Close asks for removal confirmation and must target only the synthetic job created for this test. Never clean up existing owner jobs during setup.

On Windows, also test `run.bat` with synthetic inbox files and the review workbook in the available spreadsheet application. Actual Excel/QuickBooks/Xero/OFX import checks may need the owner to interact with those applications; give exact steps and keep them pending until observed. The permitted real-document checklist and laptop/camera accuracy checks remain separate from synthetic setup checks.

### Optional BYOK and interface expectations

Do not ask for an API key as a prerequisite for offline setup. If the owner requests AI setup, use BYOK_GUIDE.md and `python -m stmtconv ai setup` with hidden local entry. Configure the owner's custom OpenAI-compatible URL, model discovery/manual entry, and model-specific effort choices. The picker defaults to the highest supported effort; offer Max only when metadata or documented capabilities support it. Never silently lower effort or switch models. Model discovery is separate from paid inference, which requires explicit owner authorization. Preserve consent, terms and page-budget gates.

Keys/provider settings live in the ignored local workspace; they are not cloned. Do not request keys in chat or commit them. Local key storage is plaintext with private permissions where supported, so device protection matters.

The current `saas-phase-7` clone also has an explicit **synthetic browser preview**. Follow [frontend/README.md](../frontend/README.md): Node 24.15+ within 24, `npm ci` in `frontend`, then `npm run dev -- --open`; `run-web.bat` starts only this demo on Windows. It needs no Python/models/key and does not sign in or process files. `npm run check` overwrites frontend output with a demo build: afterward rebuild with `npm run build:api --prefix frontend` and leave the real app ready. Real BYOK/consent testing without paid requests follows PHASE4-IMPLEMENTATION.md's explicit fake-provider recipe. If the owner wants only screens, use the demo workflow and label it. No historical branch switch is needed.

### Handoff and future updates

Summarize the device/OS and commit tested, installation/model verification, CPU status, test counts, selftest, synthetic delivery/cleanup and any unrun checks. Give the owner one working command to start practice and the guide for the next action. Record actual device evidence without private data; do not mark pending checks passed.

For updates, inspect local changes, run `git pull --ff-only` on the development branch when safe, rerun the relevant dependency installer when declarations change, and repeat the appropriate checks. Preserve local `.env`, models, provider settings and jobs. A different device needs its own setup and key entry; GitHub updates code, not those private files.


On the current `saas-phase-7` branch, also read `docs/saas/PHASE4-CONNECTIONS.md` for the implemented connection workflow; no older branch switch is needed. Preserve `.local-saas/ai-key.env` with the private database backup. Local setup generates it once, refuses to replace a lost key for encrypted connections, and does not require a real provider credential.

The complete Phase 4 guide covers per-job consent, conservative AI reservations, preferences, private profile tools, versioned configuration, service selftests and expiring MFA support grants. Receiving assistants must preserve the vault/database pair and use the explicit loopback fake-AI harness for AI tests. Restore the ordinary server afterward; do not infer production readiness from a local pass.


For the Phase 6 branch read `docs/saas/PHASE6-OPERATIONS.md` before backup/recovery. Keep the independently stored backup key separate from the matched vault key/database. Only the explicit local fake-AI harness may use `--phase4-ai`; stop it and restore the ordinary API afterward. Run the strict worker scan and report high/critical findings honestly; passing app tests does not authorize production. The local restore helper uses disposable resources only and never restores over active volumes.
