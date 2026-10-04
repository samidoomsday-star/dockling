from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from stmtconv.config import load_settings
from stmtconv.model_setup import load_manifest, missing_artifacts

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.slow
def test_pinned_models_convert_synthetic_table_offline(config_dir, monkeypatch, tmp_path):
    models = REPO / "models"
    if missing_artifacts(models, load_manifest()):
        pytest.skip("Download models first to run this optional installed-model integration check.")
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(models))
    settings = load_settings(config_dir)
    # All network sockets are blocked by conftest; config initializes offline before imports.
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    source = tmp_path / "synthetic.pdf"
    c = canvas.Canvas(str(source))
    c.setFont("Helvetica", 12)
    for row, values in enumerate(
        [
            ["Item", "Amount", "Balance"],
            ["Synthetic A", "10.00", "990.00"],
            ["Synthetic B", "20.00", "970.00"],
        ]
    ):
        y = 740 - row * 35
        for x, value in zip([50, 250, 400], values, strict=True):
            c.drawString(x, y, value)
        c.line(40, y - 10, 500, y - 10)
    c.save()
    options = PdfPipelineOptions(
        artifacts_path=settings.artifacts_path,
        do_ocr=False,
        accelerator_options=AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU),
    )
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    result = converter.convert(source)
    assert result.status.value == "success"
    assert result.document.tables
    rows = [
        row
        for table in result.document.tables
        for row in table.export_to_dataframe(doc=result.document).fillna("").values.tolist()
    ]
    assert ["Synthetic A", "10.00", "990.00"] in rows
    assert ["Synthetic B", "20.00", "970.00"] in rows
