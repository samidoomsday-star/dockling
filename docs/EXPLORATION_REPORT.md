# Phase 0 exploration report — partial; model downloads blocked

## Plain-language result
The starter is imported and Docling is installed. It can convert our fake Word, Excel and HTML tables correctly. The fake digital PDF text is accessible. However, the cloud currently blocks the sites hosting Docling's layout/table/OCR model files. We cannot yet judge Docling's main bank-statement extraction or call Phase 0 complete.

The next owner action is to review/save the model-source domain additions in cloud environment settings and publish the environment. Codex can then retry the downloads and remaining conversions. No API key, paid AI account or local installation is needed.

## 1. Setup
| Item | Observed value |
|---|---|
| Upstream reference | docling-project/docling tag v2.133.0; b0315ea356298e4659c9727e9f5191dd2001860a |
| Installed version | docling and docling-slim 2.133.0, matching PyPI release; not editable source |
| Python | 3.12.14 |
| Runtime | Linux x86_64; 4 CPU-equivalent quota; 32 GiB memory limit; no GPU used |
| CPU dependencies | torch 2.14.1+cpu and torchvision 0.29.1+cpu |
| Free path | Local libraries and synthetic inputs; no LLM key or paid API calls |
| Research helpers | research/phase0; Linux hash-locked dependencies; no product code |
| Required artifacts | Hugging Face layout/table models and RapidOCR English weights; unavailable so far |
| Reusable setup | PHASE0-SETUP.md and research/phase0/install-linux.sh |

### Problems and corrections
- Initial PyPI torchvision did not match CPU torch and failed with `operator torchvision::nms does not exist`. Replaced torchvision with the matching CPU wheel from PyTorch's official index; both imports now pass.
- `pip check` passes. The Linux install script was rerun successfully against the hash-locked dependencies.
- Upstream model-free confidence summaries have undefined numeric values and emit warnings. The research evidence records undefined confidence as null rather than inventing grades. JSON evidence serialization was corrected and the experiment rerun.
- Actual model download failed with ProxyError. A read-only request to Hugging Face returned HTTP 403 at the CONNECT proxy. An offline main-pipeline attempt fails because the layout model folder is absent. No verification was disabled and no model source was substituted.
- Network additions were saved as a draft; saving alone does not change runtime access. Runtime connectivity is still unresolved.

## 2. Feature walkthrough
| Feature | Synthetic input | Observed result |
|---|---|---|
| Digital text access via pdfplumber | Ruled, borderless and two-page PDFs | All 8/8, 8/8 and 12/12 expected date tokens present; not transaction extraction validation |
| Docling DOCX conversion | Word table | One table, all 8 ground-truth rows exact |
| Docling XLSX conversion | Excel table | One table, all 8 ground-truth rows exact |
| Docling HTML conversion | HTML table | All 8 ground-truth rows exact; 9 table rows include header, so header filtering is needed |
| Markdown/JSON/HTML export | Each successful Docling conversion | Files generated; native PDF export also succeeds |
| Tables to Excel | DOCX/XLSX/HTML results | Generated workbooks reopen with 8/8/9 rows respectively |
| Docling model-free native PDF | Digital PDF | Converts embedded text but produces zero structured tables; not a replacement for the planned ML pipeline |
| Alternate free OCR: Tesseract 5.5.0 | Rasterized scan and simulated photo | Commands succeed, 8/8 date tokens present in each; no Docling integration or complete row-accuracy claim |
| Docling ML PDF, ACCURATE tables | Digital PDF | Attempted offline; fails with missing layout artifacts |
| Docling ML OCR | Scanned PDF, simulated photo image | Unrun: model prerequisite failed |
| Docling ML borderless/multi-page tables | Two synthetic layouts | Unrun: model prerequisite failed |
| Model-dependent confidence grades | Main PDF/OCR pipeline | Unavailable until models download; model-free formats lack populated confidence |
| Real phone photo and laptop benchmark | Owner device | Unrun: must be tested on that device |
| Local API/UI server | Optional docling-serve research | Unrun; not necessary for the operator CLI |

## 3. Performance on this cloud machine
Run ID: 27acb1b6eaac438e90be5043a4c7448c. Raw current-run evidence is saved in PHASE0-EVIDENCE.json. The runner returns 1 because required ML conversions are incomplete; this is not a passing Phase 0 gate.

| Check | Status | Seconds | Exact rows or accessible date tokens* |
|---|---|---|---|
| pdfplumber_digital | passed | 0.022 | 8 |
| pdfplumber_borderless | passed | 0.015 | 8 |
| pdfplumber_multipage | passed | 0.025 | 12 |
| docling_docx | success | 0.106 | 8 |
| docling_xlsx | success | 0.019 | 8 |
| docling_html | success | 0.025 | 8 |
| docling_native_pdf | success | 0.087 | 0 |
| tesseract_scanned | passed | 0.777 | 8 |
| tesseract_photo | passed | 0.571 | 8 |
| docling_ml_digital | failed | 1.64 | — |
| docling_ml_scanned | unrun | — | — |
| docling_ml_photo | unrun | — | — |
| docling_ml_borderless | unrun | — | — |
| docling_ml_multipage | unrun | — | — |

*DOCX/XLSX/HTML numbers compare full rows, including date, description, debit, credit and balance, with ground truth. pdfplumber/Tesseract numbers check date-token presence only. Native PDF produced no tables. These tests do not yet exercise a product parser, router, reconciliation or financial verdict.

Python-process RSS samples were approximately 485–555 MiB across the warmed research process. They include imports and prior operations and exclude Tesseract child memory. They are not isolated per-engine peak benchmarks. Times exclude dependency installation/import startup, model loading where blocked, and future operator review. CPU limits, documents and environment differ from the owner's laptop; do not use these numbers to quote real jobs.

## 4. Output quality
The structured Word/Excel/HTML examples preserve every expected fake row, including the long description. HTML header handling differs. Digital PDFs expose the expected text quickly, supporting the planned geometry-based text engine, but date-token accessibility alone says nothing about correct column grouping.

Docling's native PDF path exports text without reconstructing financial tables. The standalone OCR reads the date tokens in clean scans and simulated photos, but we have not measured amounts, missing/extra rows, or coupled validation for these images. Bank-statement ML table quality, OCR quality and confidence grades remain unknown.

## 5. Limits and risks
- This synthetic set is intentionally small and clean; it cannot establish general bank coverage or real-camera performance.
- The full ML prerequisite is externally blocked. Do not replace required tests with optional conversions or report sellable extraction.
- PyPI/installed APIs show upstream changes from historical research: docling is now a meta-package, PDF OCR defaults to auto, and RapidOCR options support multiple backends. Explicit configuration/version pins are necessary.
- Product code and its check/selftest commands are not implemented yet. We checked research lint/format and real research conversions only.
- Package/code licenses and model-weight licenses are separate. Docling code declares MIT; a complete selected-weight/transitive-license review is outstanding before commercial reliance.
- Third-party prices/provider terms/import limits in RESEARCH are historical and were not independently verified here.
- Financial reconciliation cannot prove every date/description or detect all offsetting errors. Preserve conservative flags and operator review in later phases.

## 6. First verdict
**Needs real work; main feasibility verdict still pending.** This is a documentation starter, not a usable service tool. Successful structured-input conversion and text accessibility are encouraging, but do not prove bank-statement extraction. Keep the hybrid text-first/Docling-fallback architecture provisionally; confirm it after the blocked ML experiments.

## 7. Owner action and next steps
1. In this cloud environment's settings, review/save the network draft adding Hugging Face and ModelScope model-download destinations, then publish the environment.
2. Codex retries model downloads, runs digital/scanned/photo-like and borderless/multi-page ML conversions, and updates this report with real row comparisons, grades, timings and limits.
3. Owner reviews completed exploration; only then confirm/adjust Phase 1. No local setup or BYOK key is needed for Phase 0.
4. Windows installation, actual phone photos and hardware timings remain device-specific checks later.
