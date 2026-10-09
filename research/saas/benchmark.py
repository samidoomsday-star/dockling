"""Offline synthetic cold/process-warm capacity probe; no hosting guarantees."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, perf_counter, sleep

import psutil

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("digital-two-page", "separate", 12, False, False, False, "text"),
    ("digital-eight-page", "separate", 64, False, False, False, "text"),
    ("digital-card", "card", 12, False, False, False, "text"),
    ("digital-borderless", "signed", 12, False, True, False, "text"),
    ("scan-one-page", "separate", 5, True, False, False, "docling"),
    ("scan-two-page", "separate", 12, True, False, False, "docling"),
    ("simulated-photo", "separate", 5, True, False, True, "docling"),
]


def blocked(*args, **kwargs):
    raise RuntimeError("Benchmark processing must remain offline")


def offline():
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


def byte_count(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def worker(args):
    offline()
    from stmtconv.config import load_settings
    from stmtconv.extract.service import extract
    from stmtconv.intake.service import intake
    from stmtconv.orders import store

    settings = load_settings(ROOT / "config").model_copy(
        update={
            "workspace": args.scratch,
            "artifacts_path": ROOT / "models",
            "num_threads": 4,
            "offline": True,
        }
    )
    truth = json.loads(args.truth.read_text())
    runs = []
    for index in range(2):
        order = store.create(settings.workspace, platform="test")
        destination = store.root(settings.workspace, order.order_id) / "input" / args.fixture.name
        shutil.copyfile(args.fixture, destination)
        start = perf_counter()
        facts = intake(settings, order.order_id)
        intake_seconds = perf_counter() - start
        extract_start = perf_counter()
        statements = extract(
            settings, order.order_id, profile_id="synthetic_" + args.layout, engine=args.engine
        )
        extract_seconds = perf_counter() - extract_start
        actual = [
            {
                "date": row.date.isoformat() if row.date else "",
                "description": row.description,
                "debit": str(row.debit or "0.00"),
                "credit": str(row.credit or "0.00"),
                "balance": str(row.balance) if row.balance is not None else "",
            }
            for statement in statements
            for row in statement.transactions
        ]
        matched = sum(a == b for a, b in zip(actual, truth, strict=False))
        mismatched_fields = {
            key: sum(a[key] != b[key] for a, b in zip(actual, truth, strict=False))
            for key in ("date", "description", "debit", "credit", "balance")
        }
        pages = sum(len(f.pages) for f in facts)
        runs.append(
            {
                "mode": "process_cold" if index == 0 else "process_warm",
                "pages": pages,
                "rows_expected": len(truth),
                "rows_found": len(actual),
                "rows_exact": matched,
                "mismatched_fields": mismatched_fields,
                "verdicts": [s.verdict for s in statements],
                "source_check_required": any(
                    "SOURCE_CHECK_REQUIRED" in row.flags
                    for statement in statements
                    for row in statement.transactions
                ),
                "intake_seconds": round(intake_seconds, 4),
                "extract_seconds": round(extract_seconds, 4),
                "seconds_per_page": round((intake_seconds + extract_seconds) / pages, 4),
                "work_bytes_after_run": byte_count(args.scratch),
                "passed": actual == truth
                and all(s.verdict in {"VERIFIED", "VERIFIED_BY_TOTALS"} for s in statements),
            }
        )
    high_water = None
    if sys.platform == "linux":
        import resource

        high_water = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    args.report.write_text(json.dumps({"runs": runs, "worker_high_water_mib": high_water}))


def main(args):
    offline()
    from stmtconv.demo import generate
    from stmtconv.model_setup import load_manifest, verify_artifacts

    models = ROOT / "models"
    manifest = load_manifest()
    verify_artifacts(models, manifest)
    results = []
    cases = CASES if not args.text_only else [case for case in CASES if case[-1] == "text"]
    if args.case:
        cases = [case for case in cases if case[0] in args.case]
    if not cases:
        raise ValueError("No benchmark cases selected")
    with tempfile.TemporaryDirectory(prefix="dockling-saas-capacity-") as temp:
        temporary = Path(temp)
        for name, layout, count, scanned, borderless, photo, engine in cases:
            folder = temporary / name
            fixture, truth = generate(
                folder, layout=layout, count=count, scanned=scanned, borderless=borderless
            )
            if photo:
                import pypdfium2 as pdfium

                with pdfium.PdfDocument(fixture) as document:
                    image = document[0].render(scale=200 / 72).to_pil().convert("RGB")
                    fixture = folder / "simulated-photo.jpg"
                    image.save(fixture, quality=92)
                    image.close()
            truth_file = folder / "truth.json"
            truth_file.write_text(json.dumps(truth))
            report = folder / "worker.json"
            scratch = folder / "work"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--fixture",
                str(fixture),
                "--truth",
                str(truth_file),
                "--layout",
                layout,
                "--engine",
                engine,
                "--scratch",
                str(scratch),
                "--report",
                str(report),
            ]
            peak_rss = 0
            start = monotonic()
            timed_out = False
            with (folder / "worker.log").open("w") as log:
                child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
                process = psutil.Process(child.pid)
                while child.poll() is None:
                    try:
                        tree = [process, *process.children(recursive=True)]
                        rss = sum(p.memory_info().rss for p in tree if p.is_running())
                        peak_rss = max(peak_rss, rss)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    if monotonic() - start > args.timeout_seconds:
                        timed_out = True
                        try:
                            descendants = process.children(recursive=True)
                            for descendant in descendants:
                                descendant.kill()
                        except psutil.NoSuchProcess:
                            pass
                        child.kill()
                        break
                    sleep(0.05)
                exit_code = child.wait()
            payload = json.loads(report.read_text()) if report.exists() else {"runs": []}
            result = {
                "case": name,
                "engine": engine,
                "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                "input_bytes": fixture.stat().st_size,
                "subprocess_wall_seconds": round(monotonic() - start, 3),
                "sampled_process_tree_peak_rss_mib": round(peak_rss / 2**20, 2),
                "exit_code": exit_code,
                "timed_out": timed_out,
                **payload,
            }
            result["passed"] = (
                exit_code == 0
                and len(payload["runs"]) == 2
                and all(r["passed"] for r in payload["runs"])
            )
            results.append(result)
            print(
                f"{name}: {'PASS' if result['passed'] else 'FAIL'}; sampled peak {result['sampled_process_tree_peak_rss_mib']} MiB; wall {result['subprocess_wall_seconds']}s",
                flush=True,
            )
    versions = {
        name: importlib.metadata.version(name)
        for name in ("docling", "torch", "pdfplumber", "pypdfium2", "reportlab", "psutil")
    }
    report = {
        "scope": "Synthetic isolated current CLI extraction capacity; not hosted load, field accuracy or a production guarantee",
        "recorded_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": psutil.cpu_count(),
        "memory_total_mib": round(psutil.virtual_memory().total / 2**20),
        "threads": 4,
        "case_selection": [case[0] for case in cases],
        "versions": versions,
        "model_manifest_sha256": hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(),
        "model_bytes_verified": sum(a.bytes for a in manifest.files),
        "model_hashes_verified": True,
        "network": "Python socket connect/connect_ex blocked in parent and workers; not a kernel egress sandbox",
        "memory_method": "50ms sampled process-tree RSS sum; shared pages may be double-counted and short peaks missed. Linux worker ru_maxrss supplements sampling. Fixture generation runs outside measured worker.",
        "warm_method": "Second order in the same process; imports/page cache warm. Existing extraction recreates Docling converters per command, so this is not a retained-converter worker benchmark.",
        "timing_method": "Intake+extraction per page exclude Python import/startup and fixture generation; subprocess wall includes cold imports and both runs. Scratch figures are post-run totals, not peak filesystem use.",
        "passed": all(r["passed"] for r in results),
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--layout")
    parser.add_argument("--engine")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--case", choices=[case[0] for case in CASES], action="append")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.worker:
        worker(arguments)
    else:
        if arguments.output is None:
            name = (
                "CAPACITY-SUBSET-EVIDENCE.json"
                if arguments.case or arguments.text_only
                else "CAPACITY-EVIDENCE.json"
            )
            arguments.output = ROOT / "docs/saas" / name
        raise SystemExit(main(arguments))
