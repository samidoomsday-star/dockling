# Phase 0 setup and rerun guide

This is a research environment, not the finished converter. No client documents or API keys are needed. Commands below run from the Dockling checkout root.

## In this Codex cloud workspace

Codex performs these steps. The owner only needs to change environment network settings if model downloads are blocked.

1. Install the hash-locked Linux Python 3.12 dependencies:

   ```bash
   bash research/phase0/install-linux.sh
   ```

2. Download the local layout, table and English RapidOCR models. This setup step uses the network, keeps TLS verification enabled, and does not call an LLM:

   ```bash
   .venv/bin/python research/phase0/download_models.py
   ```

3. Run the synthetic experiment with Python network connections blocked:

   ```bash
   .venv/bin/python research/phase0/run.py
   ```

   Results appear in a new ignored `explore/output/<run-id>/results.json`; `explore/latest-run.txt` points to the current run. Return code 1 means required Docling conversions are incomplete. Read the result statuses; successful optional conversions do not make Phase 0 complete.

4. Check the research helper files:

   ```bash
   .venv/bin/ruff check research/phase0
   .venv/bin/ruff format --check research/phase0
   ```

The Tesseract comparison runs only if the system already supplies `tesseract` and English language data. Its child-process memory is not included in the Python-process RSS samples. It is an alternate standalone OCR experiment, not the proposed product's primary OCR dependency. A photo-like input is generated, not taken with a real camera.

The pinned upstream source used for API reference is Docling tag `v2.133.0`, commit `b0315ea356298e4659c9727e9f5191dd2001860a`. To restore the optional ignored reference clone:

```bash
git clone --depth 1 --branch v2.133.0 https://github.com/docling-project/docling.git vendor/docling
```

The actual environment installs the matching PyPI release, not an editable source copy. Current upstream packaging splits `docling` (meta-package) and `docling-slim` (implementation); both versions are locked.

## Required model-download network access

Package-manager presets already cover PyPI, GitHub and the CPU PyTorch index. Additional model sources are Hugging Face (`huggingface.co`, its `*.xethub.hf.co` and `cdn-lfs.huggingface.co` and `us.aws.cdn.hf.co` download destinations) and RapidOCR's ModelScope artifacts (`www.modelscope.cn` and its download subdomains). These are public artifacts; no account key is required for the selected models.

A saved environment draft is not a runtime update. When blocked, review/save the network additions in environment settings and publish the environment, then rerun the download and affected experiments. Preserve any existing custom domains. If a new redirect destination is denied, add only the required domain after diagnosing it.

## On your other device later

You will clone the repository, create a Python 3.12 environment, install dependencies for that device, download models, and run checks. The Linux lock is not a Windows lock. Windows dependency resolution, PowerShell instructions, Excel behavior and actual laptop timings remain unverified; the device guide and Windows validation are tracked in the original phase plan. Do not copy `.venv` from the cloud onto Windows.

GitHub keeps these scripts, the lock and documentation. Installed packages, generated PDFs/images/workbooks, model weights, personal settings and keys remain outside Git. Keep client documents on your local device when the finished application is ready.
