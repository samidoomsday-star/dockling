# Set up this clone on another device

This is the starting guide for an AI coding assistant with access to your local project folder and terminal. It covers the completed phases and additions. You do not need Kilo Code specifically; any assistant able to read files and run local commands can use it. A chat without filesystem/terminal access can explain the steps but cannot install software for you.

## What the owner should do

Clone the completed development branch:

```text
git clone --branch development-phases-2-10 https://github.com/samidoomsday-star/dockling.git
```

Open that `dockling` folder in your coding assistant/IDE. Give it this message:

> Set up this existing Dockling clone for development and synthetic testing on this device. Read AGENTS.md and docs/DEVICE_SETUP.md, then follow the appropriate OS instructions in docs/ENVIRONMENT.md. Install the required dependencies and local models, run doctor, the full checks and selftest, and complete the synthetic first-delivery workflow in docs/OPERATOR_GUIDE.md. Continue through routine setup without asking me about each step. Preserve my settings, keys and existing jobs. Keep optional AI off; guide me through private BYOK setup only if I request it. Report what passed, what remains untested and exactly how I can start using the app.

The assistant may need you to install Git/Python, approve an OS installer, or enter a private key later. Those device permissions and secrets cannot travel through GitHub. Normal statement processing needs no LLM key.

## Instructions for the receiving assistant

### Inspect before installing

1. Read root/scoped AGENTS.md, docs/PROGRESS.md and docs/ENVIRONMENT.md. OPERATOR_GUIDE.md describes daily operation; BYOK_GUIDE.md describes the optional additions. Historical phase notes are not the current implementation status.
2. Identify OS, architecture, available disk, Git, and **64-bit Python 3.12**. Record the checked-out branch/commit and `git status --short`. The complete version is on `development-phases-2-10`; `main` still contains the starter until a merge is explicitly authorized.
3. Reuse this clone. Preserve tracked changes, `.env`, ignored workspace/model files and private provider settings. Never reset, clean, overwrite settings or switch branches through conflicting local work. If the wrong branch is checked out, explain it and switch only when local work can be preserved safely.
4. Choose a project/workspace outside automatic cloud-sync folders. Do not print environment values or credential files. Check tool availability without dumping secrets. No GPU, Docker, Tesseract, LLM account or background server is needed for the default flow.

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

This release has a CLI, Excel review and a Windows batch launcher. **There is no browser/desktop graphical app or UI server to start.** Do not invent a URL, install a web stack or claim screen-based UI testing is available. Building that interface would be a separate requested development task.

### Handoff and future updates

Summarize the device/OS and commit tested, installation/model verification, CPU status, test counts, selftest, synthetic delivery/cleanup and any unrun checks. Give the owner one working command to start practice and the guide for the next action. Record actual device evidence without private data; do not mark pending checks passed.

For updates, inspect local changes, run `git pull --ff-only` on the development branch when safe, rerun the relevant dependency installer when declarations change, and repeat the appropriate checks. Preserve local `.env`, models, provider settings and jobs. A different device needs its own setup and key entry; GitHub updates code, not those private files.
