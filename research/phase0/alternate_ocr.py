"""Optional Docling/Tesseract comparison on the current synthetic scan."""

import json
import shutil
import socket
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TesseractCliOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from run import ROOT, block_connection, convert, json_safe, measured


def main():
    if not shutil.which("tesseract"):
        print("Optional comparison skipped: Tesseract is not installed.")
        return 2
    out = Path((ROOT / "explore/latest-run.txt").read_text())
    truth = json.loads((ROOT / "explore/inputs/truth.json").read_text())
    socket.create_connection = block_connection
    socket.socket.connect = block_connection
    socket.socket.connect_ex = block_connection
    options = PdfPipelineOptions(
        artifacts_path=ROOT / "models",
        do_ocr=True,
        do_table_structure=True,
        ocr_options=TesseractCliOcrOptions(lang=["eng"], force_full_page_ocr=True),
        accelerator_options=AcceleratorOptions(
            num_threads=4, device=AcceleratorDevice.CPU
        ),
    )
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    result = measured(
        lambda: convert(
            converter,
            ROOT / "explore/inputs/scanned.pdf",
            truth["scanned"],
            out / "alternate",
        )
    )
    evidence = {
        "parent_run_id": out.name,
        "input": "scanned.pdf",
        "python_network_blocked": True,
        "result": result,
    }
    (out / "alternate-ocr.json").write_text(
        json.dumps(json_safe(evidence), indent=2, allow_nan=False)
    )
    print("Docling Tesseract:", result["status"], result.get("exact_truth_rows"))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
