"""Bounded document computation. No hosted/local persistence or network clients here."""

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID, uuid4

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.extract.base import PageSet
from stmtconv.extract.docling_engine import DoclingExtractor
from stmtconv.extract.router import route
from stmtconv.extract.service import page_groups, version
from stmtconv.intake.service import inspect_file, sniff
from stmtconv.profiles.schema import detect, load_profiles


class PipelineFile(BaseModel):
    id: UUID
    name: str
    kind: str
    original_id: UUID
    normalized_id: UUID | None
    pages: list[dict[str, object]]
    previews: dict[str, str] = Field(default_factory=dict)
    sha256: str = ""


class PipelineTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    workspace_id: UUID
    job_id: UUID
    generation: int
    revision: int
    page_limit: int = Field(default=40, ge=1, le=100)
    action: str
    options: dict[str, object]
    files: list[PipelineFile] = Field(max_length=30)
    payload: dict[str, object] = Field(default_factory=dict)
    statements: list[dict[str, object]] = Field(default_factory=list)
    review_state: dict[str, object] = Field(default_factory=dict)
    runtime_config: dict[str, object] = Field(default_factory=dict)


@dataclass
class ArtifactBundle:
    id: UUID
    kind: str
    data: bytes


@dataclass
class PipelineResult:
    record: dict[str, object]
    artifacts: list[ArtifactBundle] = field(default_factory=list)


class PipelineArtifacts(Protocol):
    def read(self, artifact: UUID) -> bytes: ...
    def stage(self, artifact: ArtifactBundle) -> None: ...


class PipelineOperations(Protocol):
    def claim(self, token: str) -> PipelineTask | None: ...
    def heartbeat(self, task: PipelineTask, token: str, stage: str, pages: int) -> bool: ...
    def publish(self, task: PipelineTask, token: str, result: dict[str, object]) -> bool: ...


def digest(value: object) -> str:
    """Versioned stable JSON representation; financial values enter as exact strings."""
    return hashlib.sha256(
        json.dumps({"v": 1, "data": value}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def bounded_pdf(path: Path, limit: int, password: str | None = None) -> None:
    """Inspect page count/dimensions before rendering or extracting a page."""
    if sniff(path) == "image":
        Image.MAX_IMAGE_PIXELS = 20_000_000
        with Image.open(path) as image:
            count = getattr(image, "n_frames", 1)
            if count > limit:
                raise StmtconvError("PAGE_LIMIT", "Too many document pages.")
            for frame in range(count):
                image.seek(frame)
                if image.width * image.height > 20_000_000:
                    raise StmtconvError("IMAGE_LIMIT", "The image is too large.")
        return
    try:
        document = pdfium.PdfDocument(path, password=password)
    except pdfium.PdfiumError as error:
        # PDFium's documented password error is 4; malformed PDFs are not password waits.
        if error.err_code == 4:
            raise StmtconvError("PDF_PASSWORD_REQUIRED", "A PDF password is required.") from None
        raise StmtconvError("INTAKE_READ", "The document cannot be opened.") from None
    with document:
        if not 0 < len(document) <= limit:
            raise StmtconvError("PAGE_LIMIT", "Too many document pages.")
        for page in document:
            width, height = page.get_size()
            if width <= 0 or height <= 0 or width * height > 8_000_000:
                raise StmtconvError("PAGE_SIZE_LIMIT", "The document page is too large.")
            page.close()


def compute(
    task: PipelineTask,
    documents: dict[str, bytes],
    passwords: dict[str, str],
    scratch: Path,
    settings: Settings,
    max_pages: int,
    progress: Callable[[int], None] | None = None,
) -> PipelineResult:
    """Disposable scratch only. No Order UUID bypass or authoritative order.json."""
    from stmtconv.web.owner_config import Processing

    if task.runtime_config.get("processing"):
        policy = Processing.model_validate(task.runtime_config["processing"])
        settings = settings.model_copy(
            update={
                "balance_tolerance": policy.balance_tolerance,
                "date_out_of_period_days": policy.date_out_of_period_days,
                "qb_csv_max_rows": policy.qb_csv_max_rows,
            }
        )
    if task.action in {"profile_scaffold", "profile_test", "selftest"}:
        from stmtconv.web.utilities import compute_utility

        return compute_utility(task, documents, scratch, settings, max_pages)
    if task.action not in {"intake", "extract"}:
        from stmtconv.web.workflow import compute_workflow

        return compute_workflow(task, documents, scratch, settings)
    settings.offline = True
    max_pages = min(max_pages, task.page_limit)
    paths: list[Path] = []
    for source in task.files:
        path = scratch / (str(source.id) + ".source")
        path.write_bytes(documents[str(source.id)])
        path.chmod(0o600)
        paths.append(path)
    if task.action == "intake":
        results: list[dict[str, object]] = []
        artifacts: list[ArtifactBundle] = []
        total = 0
        for index, (source, path) in enumerate(zip(task.files, paths, strict=True), 1):
            if source.normalized_id and source.pages:
                total += len(source.pages)
                if total > max_pages:
                    raise StmtconvError("PAGE_LIMIT", "Too many document pages.")
                results.append(
                    {
                        "id": str(source.id),
                        "normalized_id": str(source.normalized_id),
                        "pages": source.pages,
                        "previews": source.previews,
                    }
                )
                continue
            try:
                bounded_pdf(path, max_pages - total, passwords.get(str(source.id)))
                fact = inspect_file(path, scratch, index, passwords.get(str(source.id)))
            except StmtconvError as error:
                if error.code == "PDF_PASSWORD_REQUIRED":
                    return PipelineResult(
                        {
                            "state": "awaiting_input",
                            "code": error.code,
                            "file_id": str(source.id),
                            "files": results,
                        },
                        artifacts,
                    )
                raise
            normalized = scratch / f"source-{index:04d}.pdf"
            bounded_pdf(normalized, max_pages - total)
            with pdfplumber.open(normalized) as document:
                header = "\n".join((document.pages[0].extract_text() or "").splitlines()[:15])
            if any(re.search(p, header) for p in settings.invoice_markers) and not any(
                re.search(p, header) for p in settings.statement_markers
            ):
                raise StmtconvError("INTAKE_DOCUMENT_TYPE", "Use financial statements.")
            total += len(fact.pages)
            normalized_id = uuid4()
            artifacts.append(ArtifactBundle(normalized_id, "normalized", normalized.read_bytes()))
            previews: dict[str, str] = {}
            with pdfium.PdfDocument(normalized) as document:
                for page_index in range(len(document)):
                    page = document[page_index]
                    scale = min(1.5, 1280 / max(page.get_size()))
                    bitmap = page.render(scale=scale)
                    picture = bitmap.to_pil()
                    from io import BytesIO

                    buffer = BytesIO()
                    picture.save(buffer, "PNG")
                    preview_id = uuid4()
                    artifacts.append(ArtifactBundle(preview_id, "page", buffer.getvalue()))
                    previews[str(page_index + 1)] = str(preview_id)
                    picture.close()
                    bitmap.close()
                    page.close()
            results.append(
                {
                    "id": str(source.id),
                    "normalized_id": str(normalized_id),
                    "pages": [p.model_dump() for p in fact.pages],
                    "previews": previews,
                }
            )
            if progress:
                progress(total)
        if task.options.get("combine") and any(f.kind != "image" for f in task.files):
            raise StmtconvError("INTAKE_COMBINE", "Combine accepts images only.")
        return PipelineResult(
            {
                "state": "succeeded",
                "files": results,
                "digest": digest([task.options, [f.sha256 for f in task.files]]),
            },
            artifacts,
        )
    if task.runtime_config.get("profiles"):
        from stmtconv.profiles.schema import Profile

        profiles = [
            Profile.model_validate(p)
            for p in cast(list[dict[str, object]], task.runtime_config["profiles"])
        ]
    else:
        profiles = load_profiles()
    statements: list[dict[str, object]] = []
    sources = [(path, [source]) for path, source in zip(paths, task.files, strict=True)]
    if task.options.get("combine"):
        combined = scratch / "combined.pdf"
        with pdfium.PdfDocument.new() as document:
            for path in paths:
                with pdfium.PdfDocument(path) as source_document:
                    document.import_pages(source_document)
            document.save(combined)
        sources = [(combined, task.files)]
    docling = DoclingExtractor(settings.artifacts_path, settings.num_threads)
    completed = 0
    for path, source_group in sources:
        with pdfplumber.open(path) as document:
            profile = detect(
                document.pages[0].extract_text() or "",
                profiles,
                str(task.options["profile_id"]) if task.options.get("profile_id") else None,
            )
            count = len(document.pages)
        page_map = [(source, p) for source in source_group for p in source.pages]
        if len(page_map) != count:
            raise StmtconvError("INVENTORY_INVALID", "The page inventory cannot be verified.")
        for group in page_groups(
            str(task.options["pages"]) if task.options.get("pages") else None, count
        ):
            statement = route(
                f"s{len(statements) + 1:04d}",
                PageSet(
                    path,
                    str(source_group[0].id),
                    group,
                    any(page_map[n - 1][1]["kind"] == "scanned" for n in group),
                    [n for n in group if page_map[n - 1][1]["kind"] == "blank"],
                ),
                profile,
                str(task.options["date_order"]),
                settings.balance_tolerance,
                settings.date_out_of_period_days,
                str(task.options.get("engine", "auto")),
                docling,
                mismatch_ratio=settings.fallback_mismatch_ratio,
            )
            if len(statement.transactions) > 10000:
                raise StmtconvError("ROW_LIMIT", "Too many transaction rows.")
            for row in statement.transactions:
                if len(row.description) > 2000 or any(
                    amount is not None
                    and (
                        amount != amount.quantize(Decimal("0.01"))
                        or len(format(amount, ".2f")) > 60
                    )
                    for amount in (row.debit, row.credit, row.balance)
                ):
                    raise StmtconvError(
                        "ROW_INVALID", "A transaction exceeds the supported field limits."
                    )
                source, page_fact = page_map[row.page - 1]
                row.source_file = str(source.id)
                row.page = int(str(page_fact["page"]))
            statement.summary.currency = str(task.options["currency"])
            statements.append(
                {
                    "profile_id": profile.id,
                    "file_ids": [str(s.id) for s in source_group],
                    "version": version([statement]),
                    "domain": statement.model_dump(mode="json"),
                }
            )
            completed += len(group)
            if progress:
                progress(completed)
    return PipelineResult(
        {
            "state": "succeeded",
            "statements": statements,
            "digest": digest(
                {
                    "sources": [{"id": str(f.id), "sha256": f.sha256} for f in task.files],
                    "options": task.options,
                    "profiles": {p.id: p.model_dump(mode="json") for p in profiles},
                    "policy": {
                        "balance_tolerance": str(settings.balance_tolerance),
                        "date_out_of_period_days": settings.date_out_of_period_days,
                        "fallback_mismatch_ratio": settings.fallback_mismatch_ratio,
                    },
                    "statements": [
                        {
                            **s,
                            "domain": {
                                k: v
                                for k, v in cast(dict[str, object], s["domain"]).items()
                                if k not in {"timings", "diagnostics"}
                            },
                        }
                        for s in statements
                    ],
                }
            ),
        }
    )
