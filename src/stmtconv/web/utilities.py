"""Offline bounded owner tools. Private source scaffolds never publish global profiles."""

import hashlib
import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import pdfplumber

from stmtconv.config import Settings
from stmtconv.web.pipeline import (
    ArtifactBundle,
    PipelineFile,
    PipelineResult,
    PipelineTask,
    compute,
    digest,
)


def compute_utility(
    task: PipelineTask,
    documents: dict[str, bytes],
    scratch: Path,
    settings: Settings,
    max_pages: int,
) -> PipelineResult:
    metadata: dict[str, object] = {}
    if task.action == "profile_scaffold":
        from stmtconv.profiles.schema import load_profiles

        path = scratch / "source.pdf"
        path.write_bytes(documents["source"])
        with pdfplumber.open(path) as document:
            words = document.pages[0].extract_words()
            text = document.pages[0].extract_text() or ""
        value: dict[str, object] = {
            "profile": next(p for p in load_profiles() if p.id == "generic").model_dump(
                mode="json"
            ),
            "page_1_words": words[:5000],
            "summary_candidates": text.splitlines()[:500],
            "warning": "Private source data. Do not publish these words/fingerprints globally; use a permitted synthetic fixture.",
        }
        kind, name = "profile_scaffold", "private-profile-scaffold.json"
    elif task.action == "selftest":
        from stmtconv.selftest import run

        value = run(settings)
        kind, name = "diagnostic", "synthetic-selftest.json"
    else:
        from stmtconv.demo import generate
        from stmtconv.profiles.schema import Profile, load_profiles

        profile = Profile.model_validate(task.payload["profile"])
        path, truth = generate(scratch / "fixture", layout="separate", count=5)
        identifier = uuid4()
        with pdfplumber.open(path) as doc:
            facts = [{"page": i + 1, "kind": "text"} for i in range(len(doc.pages))]
        profiles = {p.id: p.model_dump(mode="json") for p in load_profiles()}
        profiles[profile.id] = profile.model_dump(mode="json")
        trial = task.model_copy(
            update={
                "action": "extract",
                "options": {
                    **task.options,
                    "profile_id": profile.id,
                    "engine": "text",
                    "pages": None,
                },
                "files": [
                    PipelineFile(
                        id=identifier,
                        name="synthetic.pdf",
                        kind="pdf",
                        original_id=identifier,
                        normalized_id=identifier,
                        pages=facts,
                    )
                ],
                "runtime_config": {**task.runtime_config, "profiles": list(profiles.values())},
            }
        )
        output = compute(
            trial, {str(identifier): path.read_bytes()}, {}, scratch, settings, max_pages
        )
        from stmtconv.core.models import Statement

        statement = Statement.model_validate(
            cast(list[dict[str, object]], output.record["statements"])[0]["domain"]
        )
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
        value = {
            "passed": passed,
            "matched": actual == truth,
            "verdict": statement.verdict,
            "rows": len(actual),
            "profile_digest": digest(profile.model_dump(mode="json")),
            "scope": "built-in fictional separate-column fixture; permitted bank/layout field tests still required",
        }
        metadata = {"profile_digest": value["profile_digest"], "profile_passed": passed}
        kind, name = "diagnostic", "synthetic-profile-test.json"
    data = json.dumps(value, allow_nan=False).encode()
    if len(data) > 8 * 1024**2:
        raise ValueError("Utility output limit")
    artifact = ArtifactBundle(uuid4(), kind, data)
    manifest = {
        "revision": task.revision,
        "items": [
            {
                "id": str(artifact.id),
                "name": name,
                "kind": kind,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
    }
    return PipelineResult(
        {"state": "succeeded", "digest": digest(manifest), "manifest": manifest, **metadata},
        [artifact],
    )
