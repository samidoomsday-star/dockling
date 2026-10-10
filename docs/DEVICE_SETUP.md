# Set up this clone on another device

This is the starting guide for an AI coding assistant with access to your local project folder and terminal. It covers the completed phases and additions. You do not need Kilo Code specifically; any assistant able to read files and run local commands can use it. A chat without filesystem/terminal access can explain the steps but cannot install software for you.

## What the owner should do

For the current SaaS review/download app plus the completed Python work, clone the SaaS branch:

```text
git clone --branch saas-phase-4 https://github.com/samidoomsday-star/dockling.git
```

Open that `dockling` folder in your coding assistant/IDE. Give it this message:

> First read docs/saas/LOCAL-SETUP.md and set up the real SaaS app through Linux x86_64/Python 3.12 (WSL 2 Ubuntu on Windows), Docker Desktop/Compose, PostgreSQL, Keycloak, private storage, the restricted conversion worker and API-mode React build. Hash-verify models during setup and test genuine fictional text/scanned/image/protected PDFs, source pages and worker public TCP/DNS denial. Preserve .local-saas credentials/volumes; never use demo fixtures as an API fallback. Run the SaaS integration and real OIDC browser checks (scripts/saas-browser.mjs --phase3 --phase4), including corrections, six output formats, delivery and partial cleanup/retry, then leave the API build ready and give me the exact local start command. Next, set up this existing Dockling clone for development and synthetic testing on this device. If frontend/package.json exists, start with frontend/README.md and set up the browser preview with Node 24, npm ci and the frontend checks; explain its synthetic-only limits. Also set up the Python converter as described below. Read AGENTS.md and docs/DEVICE_SETUP.md, then follow the appropriate OS instructions in docs/ENVIRONMENT.md. Install the required dependencies and local models, run doctor, the full checks and selftest, and complete the synthetic first-delivery workflow in docs/OPERATOR_GUIDE.md. Continue through routine setup without asking me about each step. Preserve my settings, keys and existing jobs. Keep optional AI off; guide me through private BYOK setup only if I request it. Report what passed, what remains untested and exactly how I can start using the app.

The assistant may need you to install Git/Python, approve an OS installer, or enter a private key later. Those device permissions and secrets cannot travel through GitHub. Normal statement processing needs no LLM key.

## Instructions for the receiving assistant

### Inspect before installing

1. Read root/scoped AGENTS.md, docs/PROGRESS.md and docs/ENVIRONMENT.md. OPERATOR_GUIDE.md describes daily operation; BYOK_GUIDE.md describes the optional additions. Historical phase notes are not the current implementation status.
2. Identify OS, architecture, available disk, Git, and **64-bit Python 3.12**. Record the checked-out branch/commit and `git status --short`. The latest development milestone is `saas-phase-4` (secure connections, consent/dispatch pending); the completed Phase 3 app remains on `saas-phase-3`; the earlier demo plus completed Python version is on `web-frontend`; the Python-only milestone remains on `development-phases-2-10`; `main` still contains the starter until a merge is explicitly authorized.
3. Reuse this clone. Preserve tracked changes, `.env`, ignored workspace/model files and private provider settings. Never reset, clean, overwrite settings or switch branches through conflicting local work. If the wrong branch is checked out, explain it and switch only when local work can be preserved safely.
4. Choose a project/workspace outside automatic cloud-sync folders. Do not print environment values or credential files. Check tool availability without dumping secrets. The offline CLI needs no GPU, Docker, Tesseract, LLM account or background server. The SaaS app needs Docker/Compose, the Linux CPU worker/models and a running web server; use its separate setup guide.

### Execute the documented setup

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

Replace `python` above with `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on Linux. The full quality gate includes real offline model tests. Report failures, warnings and skipped/unrun tests separately; `--quick` alone does not establish full readiness. The previous cloud milestone passed 314 tests and nine selftest cases; a later commit may change that count. Doctor's encryption warning means encryption is unverified, not that it is enabled.

Then follow OPERATOR_GUIDE.md's fake-data walkthrough with the actual CLI: `demo`, `order new --platform test --date-order YMD`, copy only the generated PDF into the new job's input folder, `intake`, `extract`, `spotcheck`, `run`, inspect the ZIP, and `close` that synthetic job after checking the results. Use a new empty demo folder when needed. Compare sampled rows to the generated source before confirming the spot-check; do not automatically approve source checks for real documents. Close asks for removal confirmation and must target only the synthetic job created for this test. Never clean up existing owner jobs during setup.

On Windows, also test `run.bat` with synthetic inbox files and the review workbook in the available spreadsheet application. Actual Excel/QuickBooks/Xero/OFX import checks may need the owner to interact with those applications; give exact steps and keep them pending until observed. The permitted real-document checklist and laptop/camera accuracy checks remain separate from synthetic setup checks.

### Optional BYOK and interface expectations

Do not ask for an API key as a prerequisite for offline setup. If the owner requests AI setup, use BYOK_GUIDE.md and `python -m stmtconv ai setup` with hidden local entry. Configure the owner's custom OpenAI-compatible URL, model discovery/manual entry, and model-specific effort choices. The picker defaults to the highest supported effort; offer Max only when metadata or documented capabilities support it. Never silently lower effort or switch models. Model discovery is separate from paid inference, which requires explicit owner authorization. Preserve consent, terms and page-budget gates.

Keys/provider settings live in the ignored local workspace; they are not cloned. Do not request keys in chat or commit them. Local key storage is plaintext with private permissions where supported, so device protection matters.

The existing converter has a CLI, Excel review and `run.bat`. The `web-frontend` branch additionally has an interactive **synthetic browser preview**. Follow [frontend/README.md](../frontend/README.md): Node 24 LTS (24.15 or newer within major 24), `npm ci` in `frontend`, then `npm run dev -- --open`, or use `run-web.bat` on Windows. This preview needs no Python/models/key. Install Playwright Chromium and run `npm run check` for its independent gate. The `saas-phase-3` branch connects real synthetic uploads/OCR/sign-in, corrections, exports and live removal. `saas-phase-4` adds secure hosted connection setup. AI consent/dispatch and public hosting remain later work. The separate demo does not perform those real operations. Do not collect real keys/documents or claim the preview performs real conversions. The frontend setup guide contains a receiving-assistant prompt. If the owner requests only the browser preview, do this Node workflow first and skip the separate Python/model setup unless requested.

### Handoff and future updates

Summarize the device/OS and commit tested, installation/model verification, CPU status, test counts, selftest, synthetic delivery/cleanup and any unrun checks. Give the owner one working command to start practice and the guide for the next action. Record actual device evidence without private data; do not mark pending checks passed.

For updates, inspect local changes, run `git pull --ff-only` on the development branch when safe, rerun the relevant dependency installer when declarations change, and repeat the appropriate checks. Preserve local `.env`, models, provider settings and jobs. A different device needs its own setup and key entry; GitHub updates code, not those private files.


On `saas-phase-4`, also read `docs/saas/PHASE4-CONNECTIONS.md`. Preserve `.local-saas/ai-key.env` with the private database backup. Local setup generates it once, refuses to replace a lost key for encrypted connections, and does not require a real provider credential.
