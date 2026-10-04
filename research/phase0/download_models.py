"""Setup-only network operation. Uses upstream downloads with TLS intact."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["HF_HOME"] = str(ROOT / "explore/hf-cache")

from docling.utils.model_downloader import download_models


def main():
    output = ROOT / "explore/model-download.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        path = download_models(
            output_dir=ROOT / "models",
            with_code_formula=False,
            with_picture_classifier=False,
            with_rapidocr=True,
            rapidocr_models=["torch:iso:en"],
            progress=True,
        )
        manifest = ROOT / "docs/PHASE0-MODEL-MANIFEST.json"
        if manifest.exists():
            for record in json.loads(manifest.read_text())["files"]:
                artifact = path / record["path"]
                digest = hashlib.sha256()
                with artifact.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != record["sha256"]:
                    raise ValueError(
                        "Downloaded artifacts differ from the recorded exploration version"
                    )
    except Exception as exc:  # noqa: BLE001 — record download failure without leaking URLs/keys.
        output.write_text(
            json.dumps({"status": "failed", "error_type": type(exc).__name__})
        )
        print("Model download failed:", type(exc).__name__)
        print("Check model-source access, retained files and recorded artifact hashes.")
        return 1
    output.write_text(json.dumps({"status": "downloaded", "path": str(path)}))
    print("Required models downloaded to", path)
    print(
        "Recorded artifact hashes match."
        if manifest.exists()
        else "No recorded manifest yet."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
