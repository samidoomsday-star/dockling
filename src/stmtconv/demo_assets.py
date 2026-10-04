"""Generate a fully synthetic sample workbook and before/after gig images."""

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

from stmtconv.catalog import Catalog
from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.export.excel import write
from stmtconv.export.templates import render
from stmtconv.extract.base import PageSet
from stmtconv.extract.router import route
from stmtconv.profiles.schema import load_profiles


def assets(settings: Settings, catalog: Catalog, folder: Path) -> list[Path]:
    from stmtconv.demo import generate

    if folder.exists() and any(folder.iterdir()):
        raise StmtconvError("DEMO_EXISTS", "Choose an empty folder for generated demo assets.")
    path, truth = generate(folder, count=12)
    profile = next(p for p in load_profiles() if p.id == "synthetic_separate")
    statement = route(
        "demo",
        PageSet(path, path.name, [1, 2]),
        profile,
        "YMD",
        settings.balance_tolerance,
        settings.date_out_of_period_days,
        "text",
    )
    workbook = folder / "synthetic-sample.xlsx"
    write(statement, workbook, catalog.exports.formats["excel"])
    before = folder / "before.png"
    with pdfium.PdfDocument(path) as document:
        image = document[0].render(scale=1.5).to_pil()
        image.save(before)
        image.close()
    after = folder / "after.png"
    image = Image.new("RGB", (1200, 550), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (20, 20),
        render("demo_caption.md", {"rows": len(truth), "verdict": statement.verdict}),
        fill="black",
    )
    for index, row in enumerate(statement.transactions[:10]):
        draw.text(
            (20, 100 + 35 * index),
            f"{row.date}    {row.description}    debit {row.debit or ''}    credit {row.credit or ''}    balance {row.balance}",
            fill="black",
        )
    image.save(after)
    image.close()
    return [path, workbook, before, after]
