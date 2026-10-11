"""Synthetic end-to-end HTTPS acceptance with real OIDC/OTP and the isolated worker."""

import argparse
import hashlib
import hmac
import importlib.util
import json
import re
import subprocess
import time
import traceback
from contextlib import ExitStack
from decimal import Decimal
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import UUID, uuid4
from zipfile import ZipFile

import httpx
import pypdfium2 as pdfium
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.demo import generate
from stmtconv.web.database import database
from stmtconv.web.models import CanonicalSnapshot
from stmtconv.web.staging import preflight
from stmtconv.web.tls import service_tls

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rehearsal", ROOT / "scripts/saas-rehearsal.py")
assert spec and spec.loader
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)
PRIVATE = rehearsal.PRIVATE
ORIGIN = rehearsal.ORIGIN
FORMATS = {"excel", "csv", "qb_csv3", "qb_csv4", "xero_csv", "ofx"}
checkpoint = "PREFLIGHT"
http_failure: dict[str, object] = {}


class Form(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.action = ""
        self.fields: dict[str, str] = {}
        self.inside = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and values.get("id") in {"kc-form-login", "kc-otp-login-form"}:
            self.action = values.get("action") or ""
            self.inside = True
        if tag == "input" and self.inside and values.get("name"):
            self.fields[str(values["name"])] = values.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.inside = False


def allowed(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "localhost"
        or parsed.port not in {8443, 8444}
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Synthetic login cannot leave its verified rehearsal origins")
    return url


def login(client: httpx.Client, user: dict[str, str], otp: str) -> dict[str, object]:
    response = client.get(ORIGIN + "/auth/login")
    for _ in range(12):
        if response.is_redirect:
            response = client.get(allowed(urljoin(str(response.url), response.headers["location"])))
        elif (
            response.url.host == "localhost"
            and response.url.port == 8443
            and response.url.path == "/app"
        ):
            session = client.get(ORIGIN + "/api/v1/session")
            assert session.status_code == 200
            cookie = next(c for c in client.cookies.jar if c.name == "dockling_session")
            assert cookie.secure and cookie.has_nonstandard_attr("HttpOnly")
            return session.json()
        else:
            assert response.status_code == 200
            form = Form(response.text)
            assert form.action
            if "username" in form.fields:
                form.fields.update(username=user["username"], password=user["password"])
            elif "otp" in form.fields:
                # Each genuine OTP is used once. No bypass or direct password grant.
                time.sleep(30 - time.time() % 30 + 0.2)
                counter = int(time.time() // 30).to_bytes(8, "big")
                digest = hmac.new(otp.encode(), counter, hashlib.sha1).digest()
                offset = digest[-1] & 15
                number = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % 1000000
                form.fields["otp"] = str(number).zfill(6)
            else:
                raise ValueError("Unexpected identity form; no fallback login is permitted")
            response = client.post(
                allowed(urljoin(str(response.url), form.action)), data=form.fields
            )
    raise ValueError("Synthetic OIDC login exceeded its bounded steps")


def post(
    client: httpx.Client, path: str, body: dict[str, object], *, status: int = 200
) -> dict[str, object]:
    response = client.post(ORIGIN + path, json=body, headers={"Idempotency-Key": str(uuid4())})
    if response.status_code != status:
        http_failure["http_status"] = response.status_code
        payload = response.json()
        code = payload.get("code") if isinstance(payload, dict) else None
        if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", code):
            http_failure["error_code"] = code
    assert response.status_code == status
    return response.json()


def operation(client: httpx.Client, jid: str, record: dict[str, object]) -> tuple[str, float]:
    start = time.monotonic()
    while time.monotonic() - start < 420:
        response = client.get(ORIGIN + f"/api/v1/jobs/{jid}/operations/{record['id']}")
        assert response.status_code == 200
        state = response.json()["state"]
        if state in {"succeeded", "awaiting_input"}:
            return state, round(time.monotonic() - start, 3)
        if state not in {"queued", "running"}:
            code = response.json().get("error_code")
            if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", code):
                http_failure["operation_error_code"] = code
        assert state in {"queued", "running"}
        time.sleep(0.5)
    raise ValueError("Synthetic operation did not finish within its deadline")


def samples(folder: Path) -> list[tuple[str, list[Path], list[dict[str, str]]]]:
    result = []
    for name, opts in [
        ("text", {}),
        ("different", {"count": 6}),
        ("scan", {"scanned": True}),
        ("encrypted", {"password": "fictional-rehearsal-password"}),
    ]:
        path, expected = generate(folder / name, **{"count": 2, **opts})
        result.append((name, [path], expected))
    path, expected = generate(folder / "photo", count=2)
    image = folder / "photo" / "photo.png"
    with pdfium.PdfDocument(path) as pdf:
        page = pdf[0]
        bitmap = page.render(scale=2)
        rendered = bitmap.to_pil()
        rendered.save(image, "PNG")
        rendered.close()
        bitmap.close()
        page.close()
    result.append(("photo", [image], expected))
    path, expected = generate(folder / "combined", count=2, rows_per_page=1)
    images = []
    with pdfium.PdfDocument(path) as pdf:
        for index in range(2):
            page = pdf[index]
            bitmap = page.render(scale=3)
            rendered = bitmap.to_pil()
            target = folder / "combined" / f"page-{index + 1}.png"
            rendered.save(target, "PNG")
            rendered.close()
            bitmap.close()
            page.close()
            images.append(target)
    result.append(("combined", images, expected))
    return result


def verify(case: str | None = None) -> dict[str, object]:
    global checkpoint
    config = rehearsal.rehearsal_config()
    assert preflight(config).status == "passed"
    fixture = json.loads((PRIVATE / "bootstrap.json").read_text())
    workspaces = rehearsal.verification_workspaces()
    outcomes = []
    folder = PRIVATE / "acceptance" / uuid4().hex
    folder.mkdir(parents=True, mode=0o700)
    with ExitStack() as stack:
        clients = {}
        for name in ["owner-a", "owner-b", "viewer-a", "operator"]:
            checkpoint = "VERIFIED_OIDC_" + name.upper().replace("-", "_")
            client = stack.enter_context(
                httpx.Client(
                    verify=service_tls(config), timeout=10, follow_redirects=False, trust_env=False
                )
            )
            user = next(u for u in fixture["users"] if u["username"] == name)
            session = login(client, user, fixture["otp_secret"])
            client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": str(session["csrf_token"])})
            if name != "operator":
                wid = workspaces[1 if name.endswith("-b") else 0]
                post(client, "/api/v1/session/workspace", {"workspace_id": wid})
            clients[name] = client
        checkpoint = "ADMIN_MFA_AND_VIEWER_WRITE_DENIAL"
        admin = clients["operator"].get(ORIGIN + "/api/v1/admin/operations")
        assert admin.status_code == 200
        owner = clients["owner-a"]
        job_body = {
            "name": "Fictional HTTPS acceptance",
            "currency": "USD",
            "date_order": "MDY",
            "outputs": sorted(FORMATS),
            "profile_id": "generic",
            "output_date_format": "MM/DD/YYYY",
        }
        denied = clients["viewer-a"].post(
            ORIGIN + "/api/v1/jobs", json=job_body, headers={"Idempotency-Key": str(uuid4())}
        )
        assert denied.status_code == 403
        for name, paths, expected in samples(folder):
            if case is not None and name != case:
                continue
            # Each independent document case has a fresh fictional scope; do not reset quotas.
            case_workspaces = rehearsal.verification_workspaces()
            for role in ["owner-a", "owner-b", "viewer-a"]:
                post(
                    clients[role],
                    "/api/v1/session/workspace",
                    {"workspace_id": case_workspaces[1 if role.endswith("-b") else 0]},
                )
            checkpoint = "UPLOAD_" + name.upper()
            started = time.monotonic()
            job = post(
                owner,
                "/api/v1/jobs",
                {**job_body, "name": "Fictional HTTPS " + name, "combine": name == "combined"},
                status=201,
            )
            jid = str(job["id"])
            revision = 1
            files = []
            for path in paths:
                data = path.read_bytes()
                response = owner.post(
                    ORIGIN + f"/api/v1/jobs/{jid}/files",
                    content=data,
                    headers={
                        "Idempotency-Key": str(uuid4()),
                        "Content-Type": "application/octet-stream",
                        "X-Expected-Revision": str(revision),
                        "X-File-Name": path.name,
                        "X-Synthetic-Confirmed": "true",
                    },
                )
                assert response.status_code == 200
                uploaded = response.json()
                files.append(uploaded["id"])
                revision = uploaded["revision"]
            checkpoint = "INTAKE_" + name.upper()
            queued = post(
                owner, f"/api/v1/jobs/{jid}/intake", {"expected_revision": revision}, status=202
            )
            state, intake_seconds = operation(owner, jid, queued)
            if name == "encrypted":
                assert state == "awaiting_input"
                current = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()
                unlocked = post(
                    owner,
                    f"/api/v1/jobs/{jid}/files/{files[0]}/unlock",
                    {
                        "expected_revision": current["revision"],
                        "password": "fictional-rehearsal-password",
                    },
                    status=202,
                )
                state, _ = operation(owner, jid, unlocked)
            assert state == "succeeded"
            source = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/files/{files[0]}/pages/1")
            assert source.status_code == 200 and source.content.startswith(b"\x89PNG")
            current = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()
            checkpoint = "CONVERSION_" + name.upper()
            queued = post(
                owner,
                f"/api/v1/jobs/{jid}/operations",
                {
                    "expected_revision": current["revision"],
                    "action": "extract",
                },
                status=202,
            )
            state, conversion_seconds = operation(owner, jid, queued)
            assert state == "succeeded"
            rows = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/rows").json()["items"]
            assert len(rows) == len(expected)
            # Observe only this generated case; emit missing-field names, never summary values.
            engine = database(config)
            try:
                with Session(engine) as db:
                    saved = db.scalar(
                        select(CanonicalSnapshot).where(
                            CanonicalSnapshot.job_id == UUID(jid),
                            CanonicalSnapshot.workspace_id == UUID(case_workspaces[0]),
                        )
                    )
                    assert saved
                    missing_summary = sorted(
                        {
                            field
                            for item in saved.statements
                            for field in ["period_start", "period_end", "account_mask", "closing"]
                            if item["domain"]["summary"][field] is None
                        }
                    )
            finally:
                engine.dispose()
            corrections = []
            mismatches: dict[str, int] = {}
            fields = ["date", "description", "debit", "credit", "balance"]
            for actual, original in zip(rows, expected, strict=True):
                changes = {}
                for field in fields:
                    same = (
                        Decimal(actual[field] or "0.00") == Decimal(original[field])
                        if field in {"debit", "credit"}
                        else actual[field] == original[field]
                    )
                    if not same:
                        changes[field] = original[field]
                        mismatches[field] = mismatches.get(field, 0) + 1
                if changes:
                    corrections.append(
                        {
                            "statement_id": actual["statement_id"],
                            "row_id": actual["id"],
                            "action": "fix",
                            "changes": changes,
                        }
                    )
            raw_exact_rows = len(rows) - len(corrections)
            if corrections:
                # Known fictional source values exercise the genuine review API.
                # Keep every raw extraction mismatch in evidence; this is not human review.
                checkpoint = "SYNTHETIC_GROUND_TRUTH_REVIEW_" + name.upper()
                current = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()
                response = owner.patch(
                    ORIGIN + f"/api/v1/jobs/{jid}/review",
                    json={
                        "expected_revision": current["revision"],
                        "edits": corrections,
                    },
                    headers={"Idempotency-Key": str(uuid4())},
                )
                assert response.status_code == 200 and not response.json()["source_checked"]
                rows = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/rows").json()["items"]
            for actual, original in zip(rows, expected, strict=True):
                for field in fields:
                    if field in {"debit", "credit"}:
                        # The unused debit/credit side is null in the canonical/API contract.
                        assert Decimal(actual[field] or "0.00") == Decimal(original[field])
                    else:
                        assert actual[field] == original[field]
            assert clients["owner-b"].get(ORIGIN + f"/api/v1/jobs/{jid}").status_code == 404
            assert (
                clients["owner-b"]
                .get(ORIGIN + f"/api/v1/jobs/{jid}/files/{files[0]}/pages/1")
                .status_code
                == 404
            )
            revision = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()["revision"]
            assert (
                owner.post(
                    ORIGIN + f"/api/v1/jobs/{jid}/exports",
                    json={"expected_revision": revision},
                    headers={"Idempotency-Key": str(uuid4())},
                ).status_code
                == 409
            )
            checkpoint = "SOURCE_CONFIRMATION_" + name.upper()
            account = post(
                owner,
                f"/api/v1/jobs/{jid}/account-group",
                {
                    "expected_revision": revision,
                    "confirmed": True,
                    "private_group": "Fictional HTTPS account",
                },
            )
            check = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/spotcheck").json()
            post(
                owner,
                f"/api/v1/jobs/{jid}/spotcheck",
                {
                    "expected_revision": account["revision"],
                    "row_ids": check["row_ids"],
                    "passed": True,
                },
            )
            revision = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()["revision"]
            checkpoint = "EXPORTS_" + name.upper()
            exports = post(
                owner, f"/api/v1/jobs/{jid}/exports", {"expected_revision": revision}, status=202
            )
            assert operation(owner, jid, exports)[0] == "succeeded"
            items = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/exports").json()["items"]
            assert {item["format"] for item in items} == FORMATS
            verified = {}
            for item in items:
                response = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/artifacts/{item['id']}/download")
                assert response.status_code == 200 and response.content
                assert hashlib.sha256(response.content).hexdigest() == item["sha256"]
                verified[item["name"]] = response.content
            checkpoint = "DELIVERY_" + name.upper()
            delivery = post(
                owner, f"/api/v1/jobs/{jid}/delivery", {"expected_revision": revision}, status=202
            )
            assert operation(owner, jid, delivery)[0] == "succeeded"
            zip_item = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/delivery").json()["items"][0]
            delivered = owner.get(
                ORIGIN + f"/api/v1/jobs/{jid}/artifacts/{zip_item['id']}/download"
            )
            assert delivered.status_code == 200
            with ZipFile(BytesIO(delivered.content)) as archive:
                assert not archive.testzip()
                for file, content in verified.items():
                    assert archive.read(file) == content
            current = owner.get(ORIGIN + f"/api/v1/jobs/{jid}").json()
            checkpoint = "REMOVAL_" + name.upper()
            post(
                owner,
                f"/api/v1/jobs/{jid}/close",
                {
                    "expected_revision": current["revision"],
                    "confirm_removal": True,
                },
                status=202,
            )
            assert (
                owner.get(
                    ORIGIN + f"/api/v1/jobs/{jid}/artifacts/{items[0]['id']}/download"
                ).status_code
                == 404
            )
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                privacy = owner.get(ORIGIN + f"/api/v1/jobs/{jid}/privacy").json()
                if privacy["deletion_state"] == "removed":
                    assert privacy["certificate"]
                    break
                assert privacy["deletion_state"] == "pending"
                time.sleep(0.5)
            else:
                raise ValueError("Synthetic live removal was not verified")
            outcomes.append(
                {
                    "case": name,
                    "raw_extraction_exact_rows": raw_exact_rows,
                    "raw_extraction_mismatches": mismatches,
                    "raw_summary_missing_fields": missing_summary,
                    "generated_image_dpi": 216
                    if name == "combined"
                    else 144
                    if name == "photo"
                    else None,
                    "synthetic_ground_truth_corrected_rows": len(corrections),
                    "reviewed_exact_rows": len(expected),
                    "outputs": len(items),
                    "intake_enqueue_to_finish_seconds": intake_seconds,
                    "conversion_enqueue_to_finish_seconds": conversion_seconds,
                    "total_flow_seconds": round(time.monotonic() - started, 3),
                    "live_removal": "verified",
                }
            )
        checkpoint = "WORKER_TLS_AND_MEMORY_PEAK"
        result = subprocess.run(
            [
                "docker",
                "exec",
                "dockling-staging-rehearsal-worker-1",
                "cat",
                "/sys/fs/cgroup/memory.peak",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        peak = int(result.stdout.strip())
        report = {
            "scope": "synthetic_loopback_https_acceptance",
            "status": "passed",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "launch_approval": "not_assessed",
            "real_accounting_imports": "not_run",
            "required_cases": "complete" if case is None else "partial",
            "observed_worker_peak_since_start_mib": round(peak / 1024**2, 1),
            "cases": outcomes,
        }
        path = folder / "summary.json"
        path.write_text(json.dumps(report, indent=2))
        path.chmod(0o600)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", choices=["text", "different", "scan", "encrypted", "photo", "combined"]
    )
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.case), indent=2))
    except Exception as error:
        frames = [
            frame
            for frame in traceback.extract_tb(error.__traceback__)
            if Path(frame.filename).name == Path(__file__).name
        ]
        # The fixed checkpoint is public; no exception values or private response body are printed.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "check": checkpoint,
                    "source_line": frames[-1].lineno if frames else None,
                    **http_failure,
                }
            )
        )
        raise SystemExit(2) from None
