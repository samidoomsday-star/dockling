"""Catch host-file permissions that prevent fresh Docker initialization."""

import importlib.util
import subprocess
import time
from pathlib import Path
from uuid import uuid4


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
