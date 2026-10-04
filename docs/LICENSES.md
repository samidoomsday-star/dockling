# Dependency and model license inventory

Checked against installed distribution metadata and downloaded model cards on 2026-10-04. [PHASE10-DEPENDENCY-LICENSES.json](PHASE10-DEPENDENCY-LICENSES.json) records exact direct/dev and selected native/model dependency versions and their advertised licenses. This is an inventory, not complete legal clearance or a full transitive SBOM.

Runtime direct Python dependencies advertise MIT (Typer, Rich, Pydantic, settings, PyYAML, pdfplumber, Docling, openpyxl), BSD-3-Clause (python-dotenv, HTTPx), MIT-CMU (Pillow), and BSD-3-Clause/Apache-2.0 plus bundled dependency notices (pypdfium2). PDFium binaries include separate component notices under the installed pypdfium2 distribution's `licenses/data/linux_x64/BUILD_LICENSES` directory; retain the relevant platform notices if packaging those binaries. No PyMuPDF/AGPL runtime dependency was added.

Torch's installed metadata lists Apache-2.0/LLVM exception, BSD variants, BSL-1.0 and MIT components; torchvision advertises BSD. RapidOCR code advertises Apache-2.0 and docling-ibm-models code MIT. Development tools mostly advertise MIT/BSD/Apache-2.0; **Hypothesis is MPL-2.0**, inherited as a development-only test dependency. Do not treat every transitive package as MIT or assume a tool's license covers its model weights.

| Downloaded model family | Evidence inspected | Advertised terms |
|---|---|---|
| docling-project/docling-layout-heron | Local pinned README model card | Apache-2.0 |
| docling-project/docling-layout-heron-onnx | Local pinned README model card | Apache-2.0; derived from Heron |
| docling-project/docling-models (TableFormer) | Local pinned README model card | CDLA-Permissive-2.0 |
| RapidAI/RapidOCR PP-OCRv6 detection/recognition and v2 classification | Installed default_models.yaml identifies versioned ModelScope v3.9.2 artifacts; versioned repository README fetched over verified HTTPS | Repository metadata advertises Apache License 2.0; individual model conversion/training provenance and any additional artifact terms still require confirmation before redistribution |

Source references: [Docling](https://github.com/docling-project/docling), [Heron](https://huggingface.co/docling-project/docling-layout-heron), [Docling models](https://huggingface.co/docling-project/docling-models), [RapidOCR model repository](https://www.modelscope.cn/models/RapidAI/RapidOCR), [RapidOCR code](https://github.com/RapidAI/RapidOCR), [pypdfium2](https://github.com/pypdfium2-team/pypdfium2).

Models, dependency binaries and downloaded cards remain ignored and are **not redistributed in Git or the Dockling wheel**. The model manifest pins observed artifact hashes; these are integrity records, not independent upstream signatures or licensing proof. Preserve upstream notices when distributing a packaged environment. Review the remaining model/transitive obligations and each actual BYOK provider's current terms before commercial distribution or real client use.
