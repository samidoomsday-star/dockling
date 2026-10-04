"""Pinned setup artifacts; this module is not a processing-time network engine."""

import hashlib
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from stmtconv.config import Settings, model_download_environment
from stmtconv.errors import SetupError


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str
    files: list[Artifact] = Field(min_length=1)
    huggingface_commit_metadata: dict[str, str]


def load_manifest() -> Manifest:
    bundled = Path(__file__).parent / "_model-manifest.json"
    path = (
        bundled
        if bundled.is_file()
        else Path(__file__).resolve().parents[2] / "docs/PHASE0-MODEL-MANIFEST.json"
    )
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise SetupError(
            "MODEL_MANIFEST", "Model manifest is missing or invalid.", "Reinstall the project."
        ) from exc


def artifact_path(root: Path, artifact: Artifact) -> Path:
    path = (root / artifact.path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise SetupError("MODEL_PATH", "A model artifact path escapes the configured model folder.")
    return path


def missing_artifacts(root: Path, manifest: Manifest) -> list[str]:
    return [a.path for a in manifest.files if not artifact_path(root, a).is_file()]


def verify_artifacts(root: Path, manifest: Manifest) -> None:
    for artifact in manifest.files:
        path = artifact_path(root, artifact)
        try:
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError as exc:
            raise SetupError(
                "MODEL_MISSING",
                "A required model artifact could not be read.",
                "Run models download.",
            ) from exc
        if digest.hexdigest() != artifact.sha256 or path.stat().st_size != artifact.bytes:
            raise SetupError(
                "MODEL_CHECKSUM",
                "A model artifact differs from the pinned version.",
                "Stop using these models. Do not change expected hashes to make this pass.",
            )


class Downloader(Protocol):
    def __call__(
        self,
        *,
        output_dir: Path,
        with_code_formula: bool,
        with_picture_classifier: bool,
        with_rapidocr: bool,
        rapidocr_models: list[str],
        progress: bool,
    ) -> Path: ...


def download(settings: Settings, downloader: Downloader | None = None) -> Path:
    manifest = load_manifest()
    try:
        with model_download_environment(settings.artifacts_path / ".setup-cache"):
            if downloader is None:
                # Lazy import after the setup-only offline exception is active.
                from docling.utils.model_downloader import download_models

                downloader = download_models
            path = downloader(
                output_dir=settings.artifacts_path,
                with_code_formula=False,
                with_picture_classifier=False,
                with_rapidocr=True,
                rapidocr_models=["torch:iso:en"],
                progress=False,
            )
        verify_artifacts(path, manifest)
    except SetupError:
        raise
    except Exception as exc:
        # Upstream errors can include signed URLs or tokens; never echo them.
        raise SetupError(
            "MODEL_DOWNLOAD",
            "Model download failed.",
            "Check network access and retry models download.",
        ) from exc
    return path
