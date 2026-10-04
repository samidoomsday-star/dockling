"""Lazy CPU Docling integration; one converter per OCR mode per command."""

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from stmtconv.core.models import RawRow
from stmtconv.errors import StmtconvError
from stmtconv.extract.base import ExtractionResult, PageSet
from stmtconv.extract.text_engine import summary_from_text
from stmtconv.profiles.schema import Profile

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter


class DoclingExtractor:
    def __init__(self, artifacts_path: Path, threads: int) -> None:
        self.artifacts_path = artifacts_path
        self.threads = threads
        self.converters: dict[bool, DocumentConverter] = {}

    def extract(self, pages: PageSet, profile: Profile) -> ExtractionResult:
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            OcrMode,
            PdfPipelineOptions,
            RapidOcrOptions,
            TableFormerMode,
            TableStructureOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        scanned = pages.scanned
        if scanned not in self.converters:
            options = PdfPipelineOptions(
                artifacts_path=self.artifacts_path,
                do_ocr=scanned,
                do_table_structure=True,
                accelerator_options=AcceleratorOptions(
                    num_threads=self.threads, device=AcceleratorDevice.CPU
                ),
            )
            options.table_structure_options = TableStructureOptions(mode=TableFormerMode.ACCURATE)
            if scanned:
                options.ocr_options = RapidOcrOptions(
                    backend="torch", lang=["iso:en"], mode=OcrMode.DEFAULT
                )
            self.converters[scanned] = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
            )
        start = perf_counter()
        try:
            converted = self.converters[scanned].convert(
                pages.path, page_range=(min(pages.pages), max(pages.pages))
            )
        except Exception as exc:
            raise StmtconvError(
                "DOCLING_FAILED",
                "Local OCR/layout conversion failed.",
                "Check model setup and review this layout manually.",
            ) from exc
        rows: list[RawRow] = []
        for table in converted.document.tables:
            if not table.prov:
                continue
            number = table.prov[0].page_no
            if number not in pages.pages:
                continue
            # Avoid attributing a multi-page table's rows to a guessed page.
            if len({p.page_no for p in table.prov}) > 1:
                continue
            grid = [["" for _ in range(table.data.num_cols)] for _ in range(table.data.num_rows)]
            for cell in table.data.table_cells:
                for row in range(cell.start_row_offset_idx, cell.end_row_offset_idx):
                    for column in range(cell.start_col_offset_idx, cell.end_col_offset_idx):
                        if row < len(grid) and column < len(grid[row]):
                            grid[row][column] = cell.text
            mapping: dict[int, str] = {}
            for values in grid:
                detected = {
                    index: key
                    for index, value in enumerate(values)
                    for key, aliases in profile.header_aliases.items()
                    if value.strip().lower() in {alias.lower() for alias in aliases}
                }
                if {"date", "description"} <= set(detected.values()):
                    mapping = detected
                    continue
                if not mapping:
                    continue
                cells = {key: values[index].strip() for index, key in mapping.items()}
                content = " | ".join(values)
                rows.append(
                    RawRow(
                        **cells,
                        source_file=pages.source_file,
                        page=number,
                        engine="docling",
                        raw_text=content,
                    )
                )
        markdown = converted.document.export_to_markdown()
        summary, flags = summary_from_text(markdown, profile)
        confidence = converted.confidence.model_dump(mode="json")
        seconds = perf_counter() - start
        diagnostics = {
            str(number): {
                "engine": "docling",
                "rows": sum(r.page == number and bool(r.date) for r in rows),
                "seconds": seconds / len(pages.pages),
                "confidence": confidence.get("pages", {}).get(str(number), {}),
                "source_check_required": True,
            }
            for number in pages.pages
        }
        return ExtractionResult(rows, summary, flags, diagnostics)
