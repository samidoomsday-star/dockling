"""Reproducible 15-case synthetic supplement; never substitutes for field samples."""

import json
import platform
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import pypdfium2 as pdfium
from reportlab.pdfgen.canvas import Canvas

from stmtconv.config import load_settings
from stmtconv.demo import generate
from stmtconv.errors import StmtconvError
from stmtconv.extract.service import extract
from stmtconv.intake.service import intake
from stmtconv.orders import store

REPO = Path(__file__).resolve().parents[1]


def blocked(*args, **kwargs):
    raise AssertionError("Acceptance processing must stay offline")


def main():
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    results = []
    cases = [
        ("separate", 12, False, False, False, False),
        ("signed", 12, False, False, False, False),
        ("card", 12, False, False, False, False),
        ("separate", 12, False, True, False, False),
        ("separate", 12, False, False, True, False),
        ("separate", 5, True, False, False, False),
        ("signed", 5, True, False, False, False),
        ("separate", 5, True, False, False, True),
        ("separate", 176, False, False, False, False),
        ("signed", 168, False, False, False, False),
        ("signed", 9, False, False, False, False),
        ("card", 9, False, False, False, False),
    ]
    with TemporaryDirectory(prefix="dockling-acceptance-") as temp:
        settings = load_settings(REPO / "config")
        settings.workspace = Path(temp) / "workspace"
        settings.artifacts_path = REPO / "models"
        for index, (layout, count, scanned, borderless, reverse, photo) in enumerate(cases, 1):
            order = store.create(settings.workspace, platform="test")
            folder = store.root(settings.workspace, order.order_id) / "input"
            pdf, truth = generate(
                folder,
                layout=layout,
                count=count,
                scanned=scanned,
                borderless=borderless,
                reverse=reverse,
            )
            pdf.with_suffix(".json").unlink()
            if photo:
                with pdfium.PdfDocument(pdf) as document:
                    image = document[0].render(scale=200 / 72).to_pil().convert("RGB")
                    image.save(folder / "simulated-photo.jpg", quality=92)
                    image.close()
                pdf.unlink()
            start = perf_counter()
            files = intake(settings, order.order_id)
            statement = extract(settings, order.order_id, profile_id="synthetic_" + layout)[0]
            elapsed = perf_counter() - start
            actual = [
                {
                    "date": row.date.isoformat() if row.date else "",
                    "description": row.description,
                    "debit": str(row.debit or "0.00"),
                    "credit": str(row.credit or "0.00"),
                    "balance": str(row.balance) if row.balance is not None else "",
                }
                for row in statement.transactions
            ]
            matched = sum(a == b for a, b in zip(actual, truth, strict=False))
            balances = sum(
                a["balance"] == b["balance"] for a, b in zip(actual, truth, strict=False)
            )
            pages = sum(len(f.pages) for f in files)
            passed = len(actual) == len(truth) == matched and statement.verdict in {
                "VERIFIED",
                "VERIFIED_BY_TOTALS",
            }
            results.append(
                dict(
                    case=index,
                    layout=layout,
                    rows_expected=count,
                    rows_found=len(actual),
                    rows_matched=matched,
                    balances_matched=balances if layout != "card" else None,
                    balance_basis="totals" if layout == "card" else "printed balances",
                    pages=pages,
                    scanned=scanned,
                    simulated_photo=photo,
                    borderless=borderless,
                    reverse=reverse,
                    bracket_negatives=layout in {"signed", "card"},
                    verdict=statement.verdict,
                    mismatches=sum(t.check.status == "MISMATCH" for t in statement.transactions),
                    flags=statement.flags,
                    seconds_per_page=round(elapsed / pages, 4),
                    passed=passed,
                )
            )
            print(
                f"Case {index}: {matched}/{count} rows; {pages} pages; {statement.verdict}; {elapsed / pages:.3f}s/page",
                flush=True,
            )
        for index, title in enumerate(
            ["Invoice #FAKE1", "Tax Invoice: FAKE2", "INVOICE FAKE3"], 13
        ):
            order = store.create(settings.workspace, platform="test")
            folder = store.root(settings.workspace, order.order_id) / "input"
            path = folder / "fake-invoice.pdf"
            canvas = Canvas(str(path))
            canvas.drawString(40, 750, title)
            canvas.drawString(40, 730, "Synthetic services subtotal 20.00 tax 2.00 total 22.00")
            canvas.save()
            start = perf_counter()
            code = None
            try:
                intake(settings, order.order_id)
            except StmtconvError as error:
                code = error.code
            results.append(
                dict(
                    case=index,
                    document_type="invoice",
                    outcome="out of scope V1",
                    rejection_code=code,
                    passed=code == "INTAKE_DOCUMENT_TYPE",
                    seconds_per_page=round(perf_counter() - start, 4),
                )
            )
    report = dict(
        scope="15 synthetic cloud cases, not owner/public field acceptance",
        platform=platform.platform(),
        python=platform.python_version(),
        threads=4,
        network="socket connections blocked",
        passed=all(r["passed"] for r in results),
        cases=results,
        pending=[
            "Windows run.bat and installation",
            "Excel and accounting imports",
            "15 owner/anonymized/public field documents and real camera samples",
            "actual BYOK provider capability/terms/connection checks",
        ],
    )
    destination = REPO / "docs/PHASE10-SYNTHETIC-ACCEPTANCE.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit("Synthetic acceptance failed; inspect report")


if __name__ == "__main__":
    main()
