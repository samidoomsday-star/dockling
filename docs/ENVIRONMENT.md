# Installation and updates

For an assistant to perform setup on your other device, start with [DEVICE_SETUP.md](DEVICE_SETUP.md). It provides a copyable request and the checks to complete automatically using the commands below.

Phases 1–10 are implemented and checked in the Codex Linux cloud environment. The Windows steps below are the handoff recipe and still need verification on a Windows device. GitHub stores the project files; Python, installed dependencies and about 700 MiB of local models are installed separately on each device.

## 1. What you need

Use 64-bit Python 3.12, Git, and at least 5 GB free disk space. Windows 10/11 is the target. No GPU, CUDA, Docker, Tesseract or LLM key is required for offline statement processing. Later review work needs Excel or LibreOffice.

## 2. Cloud setup (verified)

From `/workspace/dockling`, run each command separately:

```bash
bash scripts/install-linux.sh
```

This installs the hash-locked Linux dependencies and editable project. The lock retains its historical `requirements/phase1-linux.txt` name; it also contains every dependency used by phases 2–10, including HTTPx. No additional runtime dependency was needed for those phases. Then:

```bash
.venv/bin/python -m stmtconv models download
```

This explicit setup command uses public model hosts and verifies recorded artifact hashes. Processing defaults to offline. An upstream artifact change must fail verification; never change hashes just to bypass a mismatch.

```bash
.venv/bin/python -m stmtconv doctor
```

Expect Python, workspace and model checks to pass. The disk-encryption warning is a reminder, not proof that encryption was checked. Finally:

```bash
.venv/bin/python scripts/check.py
```

The full gate includes a real offline Docling test. `--quick` omits formatting and slow model tests. A skipped model test means models were missing and full integration was not verified.

## 3. On your other Windows device (not yet run on Windows)

Install Python 3.12 (64-bit, with PATH enabled) and Git for Windows. Open **PowerShell**. These steps use the virtual environment's Python directly, so no activation or execution-policy change is needed. Choose a folder outside OneDrive/Dropbox. The following example uses `C:\work\dockling`.

Clone the development branch:

```powershell
git clone --branch development-phases-2-10 https://github.com/samidoomsday-star/dockling.git C:\work\dockling
```

Enter the project folder:

```powershell
cd C:\work\dockling
```

Create its separate Python environment:

```powershell
py -3.12 -m venv .venv
```

Update its installer:

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
```

Install the CPU PyTorch packages first, to avoid installing GPU packages:

```powershell
.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.14.1+cpu" "torchvision==0.29.1+cpu"
```

Install Dockling and development tools:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The Linux hash lock must not be used as a Windows lock. Direct dependencies are pinned; Windows transitive resolution and CPU wheel availability still need testing. If installation fails, stop and share the error text with secrets removed.

Check installed dependencies:

```powershell
.venv\Scripts\python.exe -m pip check
```

Optional: copy the defaults only if `.env` does not already exist; preserve any personal settings:

```powershell
Copy-Item .env.example .env -NoClobber
```

Download local models (first run needs Internet):

```powershell
.venv\Scripts\python.exe -m stmtconv models download
```

Check setup:

```powershell
.venv\Scripts\python.exe -m stmtconv doctor
```

Run development checks:

```powershell
.venv\Scripts\python.exe scripts\check.py
```

Expect a passing test count and “All requested development checks passed.” Report failures or skipped tests. Run `.venv\Scripts\python.exe -m stmtconv selftest` next, then the fake first-delivery walkthrough in [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md). Keep real client files out of this development checkout.

## 4. Personal settings and BYOK

Defaults work without `.env`. Optional overrides use this priority: process environment, personal `.env`, YAML, built-in defaults. Relative paths start from the folder where you run the command; run from the project folder consistently. Root options `--config-dir` and `--env-file` select alternatives.

| Variable | Default | Purpose |
|---|---|---|
| `STMTCONV_WORKSPACE` | `workspace` | Local logs, order files and private provider settings |
| `STMTCONV_LOG_LEVEL` | `INFO` | Logging detail |
| `STMTCONV_NUM_THREADS` | `4` | Validated thread setting, used by the extraction engines |
| `STMTCONV_OFFLINE` | `true` | Keep enabled; model download handles its own exception |
| `DOCLING_ARTIFACTS_PATH` | `models` | Local model files; setup cache remains inside this folder |
| `STMTCONV_AI_PROVIDER` | empty | Optional configured provider nickname |
| `STMTCONV_AI_MODEL` | empty | Optional model override |
| `STMTCONV_AI_EFFORT` | `provider_default` | Optional effort override; Max only when supported |
| `STMTCONV_AI_API_KEY` | empty | Optional private key override |
| `STMTCONV_AI_TERMS_CONFIRMED` | `false` | Optional terms gate; not sufficient by itself |

Use [BYOK_GUIDE.md](BYOK_GUIDE.md) for guided custom endpoint/model/effort setup, consent and privacy. No real model inference call was made in development. Never paste keys into chat or commit them.

## 5. Shared config files

| File | Contents |
|---|---|
| `config/settings.yaml` | Typed operational defaults; monetary tolerance is the quoted string `"0.01"` |
| `config/pricing.yaml` | Validated original package ranges and surcharges; quotes use these values |
| `config/categories.yaml` | Ordered category rules; add only synthetic keywords to shared defaults |
| `config/exports.yaml` | Validated output columns and date formats |
| `profiles/*.yaml` | Validated extraction layouts, without client data |
| `templates/*.md` | Delivery, verification, deletion and demo text |

YAML structure is validated at startup. Money settings use Decimal; float money inputs are rejected. Keep settings, schemas, `.env.example` and this guide in sync when adding fields. Installed wheels include default YAML, profiles, templates and the model manifest, so they work outside the repository folder.

## 6. Getting later versions

Once this branch is cloned, run this from its folder to download changes without overwriting conflicting local work:

```powershell
git pull --ff-only
```

Then repeat the dependency-install command and checks from Section 3 when dependencies change. Your ignored `.env`, workspace and models remain local. Cloud users repeat `bash scripts/install-linux.sh`. The cloud Linux lock captures the tested dependency set; Windows gets its own resolved lock after Windows validation.

Do not switch to `main` expecting current features until the development branch is merged. Each phase result will identify its branch. Before eventual real client work, confirm Windows device encryption and a workspace outside cloud-sync folders. Automated log masking helps reduce exposure; do not intentionally log raw documents or keys.
