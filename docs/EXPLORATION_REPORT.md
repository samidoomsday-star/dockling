# Phase 0 exploration report — experiments complete, awaiting owner review

## Plain-language result
Docling is installed and the required models downloaded successfully. It ran offline on our fake digital PDF, scanned PDF and simulated photo, preserving all eight expected transaction rows in each. It also exported Markdown, JSON, HTML and raw-table Excel workbooks.

**Important limit:** our borderless and two-page borderless examples kept their text but produced no structured tables. Docling assigned them high confidence anyway. Therefore Docling alone is not a reliable statement converter. Keep the planned pdfplumber text-first engine and use Docling for OCR/fallback; always validate rows, balances and page coverage independently.

Cloud exploration is complete. The tool itself has not been built yet. The next step is owner review of these findings, then authorization to begin Phase 1 (foundation). Windows/laptop and real-camera acceptance remain separate, later checks. No API key or paid LLM was used.

## 1. Setup and provenance
| Item | Observed value |
|---|---|
| Upstream reference | docling-project/docling tag v2.133.0, commit b0315ea356298e4659c9727e9f5191dd2001860a |
| Installation | Matching PyPI docling/docling-slim 2.133.0, not editable source |
| Python | 3.12.14 |
| Runtime | Linux x86_64; 4 CPU-equivalent quota; 32 GiB memory limit; no GPU used |
| CPU pair | torch 2.14.1+cpu; torchvision 0.29.1+cpu |
| Main OCR | RapidOCR 3.9.2, torch backend, English via iso:en, full-page OCR for scan/photo |
| Table configuration | ACCURATE TableFormer; OCR off for digital PDFs |
| Local artifacts | 23 non-cache files, about 699.5 MiB; layout, table and selected RapidOCR files |
| Main run | a6db92287d9f4481bf0b39640c045614 |
| Required conversion gate | Runner exit 0; all three required conversions executed successfully |
| Evidence | PHASE0-EVIDENCE.json; separate PHASE0-ALTERNATE-OCR.json |
| Artifact record | PHASE0-MODEL-MANIFEST.json: observed SHA-256 hashes and Hugging Face commit metadata |

The model manifest records observed downloaded bytes, not independent publisher signatures. Artifacts were fetched through upstream mechanisms with TLS verification intact. Model binaries, generated statements/images/workbooks, installed dependencies and caches are ignored and excluded from Git.

### Setup problems resolved
- Replaced incompatible PyPI torchvision with matching CPU torchvision from PyTorch's official CPU index. Both imports and pip check pass.
- Public Hugging Face metadata became accessible after the first environment publication; model weights redirected to us.aws.cdn.hf.co. After allowing and publishing that exact host, downloads succeeded. No HF token was required; the unauthenticated rate-limit warning was informational.
- Hugging Face's standard Xet route is enabled. No TLS, checksum or signature verification was disabled.
- Linux dependencies are pinned with hashes. The install script was rerun successfully; model download was also repeated successfully, reusing retained artifacts.
- Model-free formats omit confidence values. Upstream emits warnings about undefined averages; evidence encodes unavailable scores as null, rather than making up grades.

## 2. Feature walkthrough
| Feature | Input | Result |
|---|---|---|
| Main digital PDF | Ruled synthetic statement with a wrapped description | One table, 8/8 exact rows |
| Main scanned PDF | Same fake page rasterized at 200 dpi | One table, 8/8 exact rows via RapidOCR |
| Main photo input | Same fake page, rotation/contrast/noise and JPEG compression | One table, 8/8 exact rows via RapidOCR; simulated, not a real camera photo |
| Borderless table | Same rows with ruled lines removed | Conversion succeeds, text retained, zero tables and 0/8 structured rows |
| Multi-page borderless table | 12 rows across two pages with repeated header | Conversion succeeds, text retained, zero tables and 0/12 structured rows |
| Docling DOCX/XLSX/HTML | Matching fake table in each format | 8/8 expected rows exact in all; HTML also exposes a header row |
| Markdown/JSON/HTML | All successful Docling conversions | Exports produced; saved document JSON parses |
| Tables to Excel | Detected tables | Workbooks written and reopened with expected data-row counts |
| Native model-free PDF pipeline | Fake digital PDF | Text conversion works but zero structured tables; not a replacement for the ML table path |
| Confidence grades | Main PDF/image conversions | Available layout/parse/OCR grades; table score remains unavailable; grades do not prove transaction correctness |
| Alternate OCR integrated with Docling | Tesseract 5.5.0 on the fake scanned PDF | One table, 8/8 exact rows, 9.412 seconds in a separate process |
| Standalone Tesseract | Fake scan and photo-like image | Commands execute successfully; 8/8 date tokens in each; token checks are not full transaction validation |
| Local server/UI | Optional docling-serve | Unrun; not needed for the operator CLI |
| Actual phone photo and Windows device | Owner hardware | Unrun; deferred device-specific acceptance |

All three required inputs derive from one known eight-row statement. This is three formats, not a broad corpus of independent bank layouts. Full row comparison checks date, description, debit, credit and balance after whitespace normalization. It does not exercise product parsers, reconciliation, flags, state changes or accounting imports, which do not exist yet.

## 3. Cloud timings and output quality
| Main input | Seconds | Tables | Exact expected rows | Mean grade |
|---|---|---|---|---|
| digital | 8.447 | 1 | 8/8 | good |
| scanned | 8.843 | 1 | 8/8 | good |
| photo | 9.252 | 1 | 8/8 | good |
| borderless | 1.134 | 0 | 0/8 | excellent |
| multipage | 2.222 | 0 | 0/12 | excellent |

Digital timing includes the first model initialization. Borderless/multi-page timings reuse the digital converter and are warm measurements. The photo follows the scan using the OCR converter. These are total conversion/export times, not isolated per-page inference measurements. The two-page conversion is about 1.11 seconds/page on this small warm example, but produces no tables.

Python-process RSS samples peaked at about 2,769 MiB across the sequential main runner. They include imported libraries, retained converters and prior operations; they are not isolated model memory measurements. The separate alternate-OCR process observed about 1,088 MiB. Standalone Tesseract child memory is excluded. Cloud hardware differs from the owner's i5-8250U laptop; do not use these timings for client quotes or promise Windows speed.

The ruled examples preserve all expected rows, including the wrapped description. Removing the rules causes table detection to disappear while body text remains. Borderless/multi-page grades are excellent even with zero tables, demonstrating why grade thresholds alone cannot choose extraction winners. Page coverage and whole-statement checks remain required.

Raw-table Excel workbooks are research outputs, not finished client workbooks: amounts remain strings, and there are no validated Summary/Issues sheets or accounting-specific formatting. Those are later product phases.

## 4. Readiness checks
- Actual offline experiments: Python socket connections are blocked and HF/Transformers offline settings are enabled. Main digital/scan/photo and additional layouts executed; runner exit 0 means required conversion execution completed, not that every layout extracted correctly.
- Exact known-row counts: 8/8 for required three formats and DOCX/XLSX/HTML; 0/8 and 0/12 for borderless layouts. The matched rows in the required examples equal all detected data rows, so no extra data rows were observed there.
- Model download repeatability: second download completed successfully using retained artifacts.
- Dependency consistency and repeat Linux install passed.
- Research ruff lint/format passed; exported document JSON parses and table workbooks reopen.
- No product tests/check.py/selftest were run: application code is not implemented yet.

## 5. Licenses, costs and remaining risks
Observed metadata: Docling code declares MIT; layout model cards declare Apache-2.0; the TableFormer/model bundle card declares CDLA-Permissive-2.0; RapidOCR package metadata declares Apache-2.0. These are separate code/model terms. This inspection is not a full transitive dependency or OCR-weight licensing audit; complete that before commercial distribution/reliance, and preserve required notices.

The local path uses no paid service. BYOK AI is a Phase 9 option, not needed for OCR. Current provider terms, accounting-import limits, competitor prices and other historical RESEARCH claims still need primary-source checking when relevant.

The corpus is small, clean and English-only. Real bank coverage, liability sign conventions, ambiguous dates, bad images, dropped/duplicated rows, reconciliation accuracy and Windows operation remain unproven. Financial balance matches cannot prove every date/description or detect all offsetting errors. Model confidence is diagnostic only.

## 6. Verdict and recommendation
**Needs real application work; core development environment now supports the planned exploration.** Docling is useful for ruled tables and clean synthetic OCR, but its failure to detect these borderless layouts validates the proposed hybrid architecture. Do not advertise general statement accuracy based on this experiment.

Keep original phases 1–10. In Phase 1 build the installable skeleton, settings, logging/redaction, health checks, model download command and quality gate; do not jump directly to a full converter. In Phases 2–4 build a substantially richer synthetic corpus, pure normalization/validation, and geometry-based text extraction. Phase 5 then integrates tested Docling APIs behind the same interface.

## 7. Owner review
The owner can review this plain-language report and authorize Phase 1. No API key or local installation is needed now. Later, on the other device, clone the selected GitHub version, install device-specific dependencies/models, and verify Windows/Excel/accounting-import behavior. Real client data stays on that device.

Reusable cloud instructions have been refreshed for the now-working model downloads. They must be reviewed/saved and the environment published to snapshot the prepared model files and latest settings; live processes are not retained. Saving a draft is not evidence of a new published snapshot.

The setup downloader now checks artifacts against the recorded model SHA-256 manifest and stops if a future upstream revision differs. Hash verification succeeded on a repeat download. It does not silently update expected hashes to accept changed files.
