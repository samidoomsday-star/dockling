"""Executable ground-truth checks, including installed-package portability."""

import tempfile
from pathlib import Path

from stmtconv.config import Settings
from stmtconv.extract.service import extract
from stmtconv.intake.service import intake
from stmtconv.orders import store


def run(settings: Settings) -> dict[str, object]:
    from stmtconv.demo import generate

    results = []
    with tempfile.TemporaryDirectory(prefix="stmtconv-selftest-") as temporary:
        local = settings.model_copy(update={"workspace": Path(temporary) / "workspace"})
        for layout in ["separate", "signed", "card"]:
            for count in [5, 12, 19]:
                order = store.create(local.workspace, platform="test")
                folder = store.root(local.workspace, order.order_id) / "input"
                path, truth = generate(folder, layout=layout, count=count)
                path.with_suffix(".json").unlink()
                intake(local, order.order_id)
                statement = extract(local, order.order_id, engine="text")[0]
                actual = [
                    {
                        "date": t.date.isoformat() if t.date else "",
                        "description": t.description,
                        "debit": str(t.debit or "0.00"),
                        "credit": str(t.credit or "0.00"),
                        "balance": str(t.balance) if t.balance is not None else "",
                    }
                    for t in statement.transactions
                ]
                passed = actual == truth and statement.verdict in {"VERIFIED", "VERIFIED_BY_TOTALS"}
                results.append(
                    {
                        "layout": layout,
                        "rows": count,
                        "matched": actual == truth,
                        "verdict": statement.verdict,
                        "passed": passed,
                    }
                )
    return {"passed": all(bool(r["passed"]) for r in results), "results": results}
