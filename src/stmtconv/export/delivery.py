"""Archive only a complete, unchanged export revision and factual disclosures."""

import hashlib
from pathlib import Path
from time import perf_counter
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.export.templates import render
from stmtconv.extract.service import read_statements, version
from stmtconv.orders import store


def deliver(settings: Settings, order_id: str) -> Path:
    started = perf_counter()
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"exported", "delivered"})
        if order.deletion_pending:
            raise StmtconvError("DELETION_PENDING", "Finish close before any other operation.")
        statements = read_statements(settings, order_id)
        if version(statements) != order.export_revision:
            raise StmtconvError("DELIVERY_STALE", "Statements changed after export.")
        directory = store.root(settings.workspace, order_id)
        output = store.child(directory, "output")
        files = sorted(output.iterdir())
        if not order.export_hashes or {p.name for p in files} != set(order.export_hashes):
            raise StmtconvError("DELIVERY_OUTPUT", "The export file set changed; export again.")
        for path in files:
            store.child(directory, "output/" + path.name)
            if (
                not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != order.export_hashes[path.name]
            ):
                raise StmtconvError("DELIVERY_OUTPUT", "An exported file changed; export again.")
        data: dict[str, object] = {
            "order_id": order_id,
            "rows": sum(len(s.transactions) for s in statements),
            "mismatches": sum(
                t.check.status == "MISMATCH" for s in statements for t in s.transactions
            ),
            "fixes": order.manual_fixes,
            "verdict": ", ".join(s.verdict for s in statements),
            "disclosure": "not fully verified"
            if order.exported_unverified
            else "financial reconciliation passed",
            "spotcheck_skipped": order.spot_check.skipped,
            "ai_pages": order.ai_pages_used,
            "retention_days": settings.retention_days_after_delivery,
            "merge_issues": ", ".join(str(i["code"]) for i in order.merge_issues),
            "credit_card": any(s.summary.direction == "liability" for s in statements),
        }
        texts = {
            "DELIVERY-NOTE.txt": render("delivery_note.md", data),
            "VERIFICATION-SUMMARY.txt": render("verification_summary.md", data),
            "DATA-HANDLING.txt": render("data_handling.md", data),
        }
        path = store.child(directory, f"delivery/{order_id}.zip")
        temporary = path.with_suffix(".tmp")
        try:
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
                for name, content in [("output/" + p.name, p.read_bytes()) for p in files] + [
                    (name, text.encode("utf-8")) for name, text in texts.items()
                ]:
                    info = ZipInfo(name, date_time=order.created_at.timetuple()[:6])
                    info.compress_type = ZIP_DEFLATED
                    archive.writestr(info, content)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        order.timings["delivery"] = perf_counter() - started
        if order.status == "exported":
            store.transition(order, "delivered")
    return path
