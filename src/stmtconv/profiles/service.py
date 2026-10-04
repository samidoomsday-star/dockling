"""Scaffold contains source data and stays confined to its order."""

from pathlib import Path

import pdfplumber
import yaml

from stmtconv.errors import StmtconvError
from stmtconv.orders import store
from stmtconv.profiles.schema import load_profiles


def scaffold(workspace: Path, order_id: str, file: str) -> Path:
    order = store.load(workspace, order_id)
    fact = next((f for f in order.files if f.name == file), None)
    if fact is None:
        raise StmtconvError("PROFILE_FILE", "Choose a file recorded by intake.")
    root = store.root(workspace, order_id)
    with pdfplumber.open(store.child(root, fact.work_file)) as document:
        words = document.pages[0].extract_words()
        text = document.pages[0].extract_text() or ""
    generic = next(p for p in load_profiles() if p.id == "generic")
    path = store.child(root, "work/profile-draft.yaml")
    store.atomic_text(
        path,
        yaml.safe_dump(
            {
                "profile": generic.model_dump(),
                "page_1_words": words,
                "summary_candidates": text.splitlines(),
            },
            sort_keys=False,
        ),
    )
    return path
