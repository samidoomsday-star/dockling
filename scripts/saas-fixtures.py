"""Generate only fictional Phase 2 browser fixtures under the ignored local directory."""

from pathlib import Path

import pypdfium2 as pdfium

from stmtconv.demo import generate

root = Path(__file__).resolve().parents[1] / ".local-saas" / "browser-fixtures"
for case, options in {
    "text": {"count": 2},
    "different": {"count": 6},
    "scan": {"count": 2, "scanned": True},
    "encrypted": {"count": 2, "password": "fictional-browser-password"},
}.items():
    path, _ = generate(root / case, **options)
    (root / f"{case}.pdf").write_bytes(path.read_bytes())
with pdfium.PdfDocument(root / "text.pdf") as document:
    page = document[0]
    bitmap = page.render(scale=2)
    image = bitmap.to_pil()
    image.save(root / "photo.png", "PNG")
    image.close()
    bitmap.close()
    page.close()
print("Fictional text, scan, protected PDF and image browser fixtures generated.")
split, _ = generate(root / "combined", count=2, rows_per_page=1)
with pdfium.PdfDocument(split) as document:
    for number in range(2):
        page = document[number]
        bitmap = page.render(scale=2)
        image = bitmap.to_pil()
        if number == 0:
            image.save(root / "page-1.png", "PNG")
        else:
            rotated = image.rotate(90, expand=True)
            exif = rotated.getexif()
            exif[274] = 6
            rotated.save(root / "page-2-exif.jpg", "JPEG", quality=95, exif=exif)
            rotated.close()
        image.close()
        bitmap.close()
        page.close()
