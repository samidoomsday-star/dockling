"""Content-sniffed local intake. Decrypted and normalized copies stay in work/."""

import hashlib
from pathlib import Path
from time import perf_counter

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageStat

from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.orders import store
from stmtconv.orders.models import FileFact, PageFact


def sniff(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(16)
    if header.startswith(b"%PDF-"):
        return "pdf"
    if header.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"II*\x00", b"MM\x00*")):
        return "image"
    raise StmtconvError(
        "INTAKE_UNSUPPORTED_TYPE",
        "Unsupported document content.",
        "Use PDF, JPEG, PNG or TIFF statements; invoices are outside V1.",
    )


def analyze_pdf(path: Path) -> list[PageFact]:
    facts: list[PageFact] = []
    with pdfplumber.open(path) as document, pdfium.PdfDocument(path) as render:
        for number, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            useful = sum(c.isalnum() for c in text)
            if useful >= 20 and text and useful / max(len(text), 1) > 0.35 and "\ufffd" not in text:
                kind = "text"
            else:
                rendered = render[number - 1].render(scale=0.25).to_pil().convert("L")
                stats = ImageStat.Stat(rendered)
                kind = "blank" if stats.mean[0] > 252 and stats.stddev[0] < 3 else "scanned"
                rendered.close()
            facts.append(PageFact(page=number, kind=kind, rotation=int(page.rotation or 0)))
    return facts


def inspect_file(path: Path, work: Path, index: int, password: str | None = None) -> FileFact:
    kind = sniff(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    target = work / f"source-{index:04d}.pdf"
    protected = False
    try:
        if kind == "pdf":
            try:
                document = pdfium.PdfDocument(path)
            except pdfium.PdfiumError:
                protected = True
                if not password:
                    raise StmtconvError(
                        "PDF_PASSWORD_REQUIRED",
                        "PDF cannot be opened without its password.",
                        "Run intake with --password to enter it privately.",
                    ) from None
                document = pdfium.PdfDocument(path, password=password)
            with document:
                # Import into a new document: never persist the source password/security dictionary.
                with pdfium.PdfDocument.new() as clean:
                    clean.import_pages(document)
                    clean.save(target)
        else:
            with Image.open(path) as image:
                pages = []
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    pages.append(ImageOps.exif_transpose(image).convert("RGB"))
                pages[0].save(target, "PDF", save_all=True, append_images=pages[1:], resolution=200)
                for page in pages:
                    page.close()
        facts = analyze_pdf(target)
    except StmtconvError:
        raise
    except Exception as exc:
        raise StmtconvError(
            "INTAKE_READ", "Document is damaged or its password is incorrect."
        ) from exc
    return FileFact(
        name=path.name,
        sha256=digest.hexdigest(),
        pages=facts,
        kind="pdf" if kind == "pdf" else "image",
        password_protected=protected,
        work_file=f"work/{target.name}",
    )


def intake(
    settings: Settings,
    order_id: str,
    password: str | None = None,
    combine: bool = False,
    force: bool = False,
) -> list[FileFact]:
    started = perf_counter()
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"created", "intake_done"})
        if order.document_type != "statement":
            raise StmtconvError("INTAKE_DOCUMENT_TYPE", "Invoices are outside V1.")
        directory = store.root(settings.workspace, order_id)
        input_dir = store.child(directory, "input")
        paths = [
            store.child(directory, f"input/{p.name}")
            for p in sorted(input_dir.iterdir())
            if p.is_file()
        ]
        if not paths:
            raise StmtconvError(
                "INTAKE_EMPTY", "Put statement files in the order's input folder first."
            )
        if not force and any(p.stat().st_size > settings.max_file_mb * 1024**2 for p in paths):
            raise StmtconvError(
                "INTAKE_LIMIT",
                "A file exceeds the configured size limit.",
                "Review the job before using --force.",
            )
        work = store.child(directory, "work")
        files = [inspect_file(path, work, index, password) for index, path in enumerate(paths, 1)]
        if not force and sum(len(f.pages) for f in files) > settings.max_pages_per_order:
            raise StmtconvError("INTAKE_LIMIT", "The order exceeds the page limit.")
        if combine:
            if any(f.kind != "image" for f in files):
                raise StmtconvError(
                    "INTAKE_COMBINE",
                    "--combine accepts image files only, in filename order.",
                    "Number the files 001, 002, and so on.",
                )
            with pdfium.PdfDocument.new() as combined:
                for file in files:
                    with pdfium.PdfDocument(store.child(directory, file.work_file)) as document:
                        combined.import_pages(document)
                combined.save(work / "combined.pdf")
            files = [
                FileFact(
                    name="combined-images",
                    sha256=hashlib.sha256("".join(f.sha256 for f in files).encode()).hexdigest(),
                    pages=analyze_pdf(work / "combined.pdf"),
                    kind="image",
                    work_file="work/combined.pdf",
                )
            ]
        order.files = files
        order.pages_by_kind = {
            kind: sum(p.kind == kind for f in files for p in f.pages)
            for kind in ["text", "scanned", "blank"]
        }
        order.timings["intake"] = perf_counter() - started
        if order.status == "created":
            store.transition(order, "intake_done")
    return files
