"""Setup-only network operation. Uses upstream downloads with TLS intact."""

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
    except Exception as exc:  # noqa: BLE001 — record download failure without leaking URLs/keys.
        output.write_text(
            json.dumps({"status": "failed", "error_type": type(exc).__name__})
        )
        print("Model download failed:", type(exc).__name__)
        print("Check access to Hugging Face and RapidOCR's ModelScope artifact hosts.")
        return 1
    output.write_text(json.dumps({"status": "downloaded", "path": str(path)}))
    print("Required models downloaded to", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
