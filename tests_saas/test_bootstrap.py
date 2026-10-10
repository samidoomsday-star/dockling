"""Catch host-file permissions that prevent fresh Docker initialization."""

import hashlib
import importlib.util
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from stmtconv.model_setup import Artifact, Manifest


def test_worker_model_mount_is_public_artifacts_only(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("saas_local", Path("scripts/saas-local.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    private = tmp_path / ".local-saas"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(module, "LOCAL", private)
    source = tmp_path / "models" / "nested"
    source.mkdir(parents=True, mode=0o700)
    original = source / "weights.bin"
    original.write_bytes(b"approved public model")
    original.chmod(0o600)
    (source / "credentials.json").write_bytes(b"must never be mounted")
    manifest = Manifest(
        note="Synthetic public artifact",
        files=[
            Artifact(
                path="nested/weights.bin",
                bytes=original.stat().st_size,
                sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
            )
        ],
        huggingface_commit_metadata={},
    )
    monkeypatch.setattr("stmtconv.model_setup.load_manifest", lambda: manifest)
    module.stage_worker_models()
    staged = private / "worker-models" / "nested" / "weights.bin"
    assert staged.read_bytes() == original.read_bytes()
    assert staged.stat().st_mode & 0o777 == 0o644
    assert staged.parent.stat().st_mode & 0o777 == 0o755
    assert original.stat().st_mode & 0o777 == 0o600
    assert source.stat().st_mode & 0o777 == 0o700
    assert private.stat().st_mode & 0o777 == 0o700
    assert not (staged.parent / "credentials.json").exists()
    # A differently numbered Docker user can read the mount; private originals are unchanged.
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--user",
            "1001:1001",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--mount",
            f"type=bind,source={staged.parent.parent},target=/models,readonly",
            "python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258",
            "python",
            "-c",
            "from pathlib import Path; assert Path('/models/nested/weights.bin').read_bytes()==b'approved public model'",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, "A different container user could not read public worker models."
    modified = staged.stat().st_mtime_ns
    module.stage_worker_models()
    assert staged.stat().st_mtime_ns == modified
    (staged.parent / "unexpected").write_bytes(b"not on manifest")
    with pytest.raises(SystemExit, match="Unexpected worker cache entry"):
        module.stage_worker_models()


def test_fresh_postgres_bootstrap_reads_private_mounts(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("saas_local", Path("scripts/saas-local.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder = tmp_path / "private"
    monkeypatch.setattr(module, "LOCAL", folder)
    original = subprocess.run

    def absent_volume(args, **kwargs):
        if args[:3] == ["docker", "volume", "inspect"]:
            return subprocess.CompletedProcess(args, 1)
        return original(args, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", absent_volume)
    module.initialize()
    assert folder.stat().st_mode & 0o777 == 0o700
    assert (folder / "bootstrap.json").stat().st_mode & 0o777 == 0o600
    assert (folder / "init.sql").stat().st_mode & 0o777 == 0o644
    name = "dockling-bootstrap-test-" + uuid4().hex[:12]
    image = "postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
    try:
        result = original(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--env-file",
                str(folder / "postgres.env"),
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=256m",
                "--mount",
                f"type=bind,source={folder / 'init.sql'},target=/docker-entrypoint-initdb.d/10-dockling.sql,readonly",
                image,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Could not start the isolated synthetic bootstrap probe."
        for attempt in range(90):
            check = original(
                [
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-U",
                    "postgres",
                    "-Atc",
                    "SELECT count(*) FROM pg_database WHERE datname IN ('dockling','dockling_test','keycloak')",
                ],
                capture_output=True,
                text=True,
            )
            if check.returncode == 0 and check.stdout.strip() == "3":
                break
            if attempt == 89:
                raise AssertionError(
                    "Fresh PostgreSQL bootstrap failed; inspect local private logs."
                )
            time.sleep(0.2)
    finally:
        original(["docker", "rm", "-f", name], capture_output=True, check=False)
