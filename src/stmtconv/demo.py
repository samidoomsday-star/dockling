"""Seeded synthetic statements and ground truth; never uses client data."""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen.canvas import Canvas


def generate(
    folder: Path,
    layout: str = "separate",
    count: int = 12,
    rows_per_page: int = 8,
    scanned: bool = False,
    password: str | None = None,
    reverse: bool = False,
    borderless: bool = False,
    month: int = 1,
    year: int = 2026,
    opening: Decimal = Decimal("1000.00"),
    corrupt_index: int | None = None,
) -> tuple[Path, list[dict[str, str]]]:
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{layout}-{year}-{month:02d}-{'scan' if scanned else 'text'}"
    path = folder / f"{name}.pdf"
    liability = layout == "card"
    rows: list[dict[str, str]] = []
    balance = opening
    for index in range(count):
        debit = Decimal(index + 1).quantize(Decimal("0.01")) if index % 3 else Decimal("0.00")
        credit = Decimal("20.00") if index % 3 == 0 else Decimal("0.00")
        balance += debit - credit if liability else credit - debit
        rows.append(
            {
                "date": (date(year, month, 1) + timedelta(days=index % 27)).isoformat(),
                "description": f"Synthetic purchase {index:03d} continued detail",
                "debit": str(debit),
                "credit": str(credit),
                "balance": str(balance) if not liability else "",
            }
        )
    closing = balance
    canvas = Canvas(
        str(path), pagesize=(612, 792), encrypt=StandardEncryption(password) if password else None
    )
    sequence = list(reversed(rows)) if reverse else rows
    for offset in range(0, count, rows_per_page):
        canvas.setFont("Helvetica", 10)
        canvas.drawString(40, 760, f"Synthetic {layout} statement")
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
        canvas.drawString(40, 744, f"Period: {year}-{month:02d}-01 to {end.isoformat()}")
        canvas.drawString(40, 728, "Account: XXXX1234")
        canvas.drawString(40, 712, f"Opening balance: {opening} Closing balance: {closing}")
        canvas.drawString(
            40,
            696,
            f"Total debits: {sum((Decimal(r['debit']) for r in rows), Decimal(0))} Total credits: {sum((Decimal(r['credit']) for r in rows), Decimal(0))}",
        )
        headers = [(40, "Date"), (130, "Description")]
        headers += (
            [(370, "Amount")] if layout in {"signed", "card"} else [(350, "Debit"), (430, "Credit")]
        )
        if not liability:
            headers.append((510, "Balance"))
        for x, value in headers:
            canvas.drawString(x, 670, value)
        if not borderless:
            canvas.line(35, 658, 590, 658)
            for x in (
                [35, 125, 345, 425, 505, 590] if layout == "separate" else [35, 125, 345, 505, 590]
            ):
                canvas.line(x, 675, x, 658 - 38 * len(sequence[offset : offset + rows_per_page]))
        for index, row in enumerate(sequence[offset : offset + rows_per_page]):
            row = dict(row)
            if offset + index == corrupt_index:
                row["debit"] = "9.00"
            y = 640 - index * 38
            canvas.drawString(40, y, row["date"])
            canvas.drawString(130, y, row["description"].removesuffix(" continued detail"))
            canvas.drawString(130, y - 12, "continued detail")
            if layout in {"signed", "card"}:
                amount = (
                    Decimal(row["debit"]) - Decimal(row["credit"])
                    if liability
                    else Decimal(row["credit"]) - Decimal(row["debit"])
                )
                canvas.drawString(370, y, f"({abs(amount)})" if amount < 0 else str(amount))
            else:
                canvas.drawString(350, y, row["debit"] if Decimal(row["debit"]) else "")
                canvas.drawString(430, y, row["credit"] if Decimal(row["credit"]) else "")
            if not liability:
                canvas.drawString(510, y, row["balance"])
            if not borderless:
                canvas.line(35, y - 21, 590, y - 21)
        canvas.drawString(40, 40, f"Page {offset // rows_per_page + 1}")
        canvas.showPage()
    canvas.save()
    if scanned:
        images: list[Image.Image] = []
        with pdfium.PdfDocument(path, password=password) as document:
            for page in document:
                image = page.render(scale=200 / 72).to_pil().convert("RGB")
                image = image.rotate(0.2, fillcolor="white")
                draw = ImageDraw.Draw(image)
                for index in range(30):
                    draw.point(
                        ((index * 83 + 17) % image.width, (index * 71 + 23) % image.height),
                        fill=(210, 210, 210),
                    )
                images.append(image)
        images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=200)
        for image in images:
            image.close()
    (folder / f"{name}.json").write_text(
        json.dumps(
            {"layout": layout, "opening": str(opening), "closing": str(closing), "rows": rows},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path, rows
